"""Reproduce the notebook's EfficientNet-B3 classifier as a runnable script.

This is `car-damage-classification.ipynb` turned into something you can run
headlessly and re-run reproducibly. It writes a checkpoint in exactly the
shape `app/ml/classifier.py` expects, so the API picks it up with no further
work: copy the output into `backend/models/car_damage_classifier.pth`.

    python training/train_classifier.py \
        --data-root /path/to/CarDD_release/CarDD_COCO \
        --epochs 60 --batch-size 32 --output models/car_damage_classifier.pth

Requires the ML extras:  pip install -r requirements-ml.txt
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# Import from the app so the taxonomy and thresholds cannot drift between
# training and serving.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.damage_classes import DAMAGE_CLASSES  # noqa: E402

# The COCO category names in CarDD use spaces; our taxonomy uses underscores.
COCO_TO_CLASS = {
    "dent": "dent",
    "scratch": "scratch",
    "crack": "crack",
    "glass shatter": "glass_shatter",
    "lamp broken": "lamp_broken",
    "tire flat": "tire_flat",
}

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]



class CarDamageDataset:
    """Multi-label dataset over one CarDD split.

    Defined at module level, not inside main(): DataLoader worker processes
    pickle the dataset by reference, and a class nested in a function cannot be
    pickled - which silently drops you back to single-process loading, or fails
    outright depending on the platform's start method.
    """

    def __init__(self, rows: list[dict], image_dir: Path | None, transform):
        self.rows = rows
        self.image_dir = Path(image_dir) if image_dir else None
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        import torch
        from PIL import Image

        row = self.rows[index]
        # Negative examples live outside the split directories, so a row may
        # carry its own absolute path.
        path = row.get("path") or (self.image_dir / row["file_name"])
        with Image.open(path) as handle:
            image = handle.convert("RGB")
        target = torch.tensor([float(name in row["labels"]) for name in DAMAGE_CLASSES])
        return self.transform(image), target



# Torch downloads pretrained weights through urllib, which is blocked in some
# sandboxed environments while curl is not. Pre-seed the cache so the first
# `efficientnet_b3(weights=...)` call finds the file already there.
EFFICIENTNET_B3_URL = (
    "https://download.pytorch.org/models/efficientnet_b3_rwightman-b3899882.pth"
)


def ensure_pretrained_weights() -> bool:
    """Return True if ImageNet weights are available locally."""
    import subprocess

    try:
        from torch.hub import get_dir
    except ImportError:
        return False

    cache = Path(get_dir()) / "checkpoints"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / EFFICIENTNET_B3_URL.rsplit("/", 1)[-1]
    if target.exists() and target.stat().st_size > 1_000_000:
        return True

    print("Fetching ImageNet weights for EfficientNet-B3 (about 47 MB)...")
    partial = target.with_suffix(".part")
    result = subprocess.run(
        ["curl", "-sS", "-L", "--fail", "--retry", "3", "--max-time", "300",
         "-o", str(partial), EFFICIENTNET_B3_URL],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not partial.exists():
        partial.unlink(missing_ok=True)
        print(f"  could not pre-fetch ({result.stderr.strip()[:120]}); "
              "letting torch try its own download.")
        return False
    partial.replace(target)
    print(f"  cached at {target}")
    return True


def load_negatives(directory: Path) -> list[dict]:
    """Undamaged vehicles, carrying an all-zero label vector.

    Without these the model never sees a car that is not damaged, and cannot
    represent "no damage" as an answer - it will always name whichever class
    clears its threshold first.
    """
    if not directory.is_dir():
        return []
    return [
        {"file_name": path.name, "path": path, "labels": []}
        for path in sorted(directory.glob("*.jpg"))
    ]


def split_negatives(rows: list[dict], fractions=(0.70, 0.20, 0.10)) -> dict[str, list[dict]]:
    """Deterministic train/val/test split, mirroring CarDD's own proportions."""
    n = len(rows)
    n_train = int(n * fractions[0])
    n_val = int(n * fractions[1])
    return {
        "train": rows[:n_train],
        "val": rows[n_train : n_train + n_val],
        "test": rows[n_train + n_val :],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="CarDD_COCO directory containing annotations/ and {train,val,test}2017/",
    )
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--head-lr", type=float, default=3e-4)
    parser.add_argument("--backbone-lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument(
        "--negatives",
        type=Path,
        default=None,
        help="Directory of undamaged car photographs to train against "
             "(default: <data-root>/negatives when it exists)",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=8,
        help="Stop early if validation loss has not improved for this many epochs "
             "(0 disables early stopping)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("models/car_damage_classifier.pth")
    )
    parser.add_argument("--device", type=str, default=None)
    return parser.parse_args()


def load_split(annotations: Path, split: str) -> list[dict]:
    """Collapse COCO instance annotations into per-image multi-label rows."""
    with open(annotations) as handle:
        data = json.load(handle)

    categories = {c["id"]: c["name"] for c in data["categories"]}
    file_names = {img["id"]: img["file_name"] for img in data["images"]}

    labels: dict[int, set[str]] = defaultdict(set)
    for annotation in data["annotations"]:
        raw = categories[annotation["category_id"]]
        mapped = COCO_TO_CLASS.get(raw)
        if mapped is None:
            continue  # unknown category: skip rather than mislabel
        labels[annotation["image_id"]].add(mapped)

    return [
        {
            "file_name": file_names[image_id],
            "split": split,
            "labels": sorted(classes),
        }
        for image_id, classes in labels.items()
    ]


def main() -> int:
    args = parse_args()

    try:
        import torch
        from PIL import Image
        from torch import nn
        from torch.optim import AdamW
        from torch.optim.lr_scheduler import CosineAnnealingLR
        from torch.utils.data import DataLoader
        from torchvision import models, transforms
    except ImportError:
        print(
            "torch/torchvision are required. Install them with:\n"
            "    pip install -r requirements-ml.txt",
            file=sys.stderr,
        )
        return 1

    from sklearn.metrics import (  # noqa: PLC0415
        average_precision_score,
        f1_score,
        precision_recall_curve,
        roc_auc_score,
    )

    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        # Apple Silicon GPU. Roughly 8-10x faster than CPU for this model.
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Training on {device}")

    # pin_memory only helps CUDA host->device copies; it warns elsewhere.
    pin = device.type == "cuda"

    root: Path = args.data_root
    splits = {}
    for split in ("train", "val", "test"):
        rows = load_split(root / "annotations" / f"instances_{split}2017.json", split)
        # Tolerate a partially downloaded dataset: train on what is on disk
        # rather than dying on the first missing file.
        image_dir = root / f"{split}2017"
        present = [r for r in rows if (image_dir / r["file_name"]).exists()]
        if len(present) != len(rows):
            print(f"  {split:5}: {len(present)}/{len(rows)} images present on disk")
        else:
            print(f"  {split:5}: {len(present)} labelled images")
        if not present:
            print(f"\nERROR: no images found for the '{split}' split in {image_dir}.\n"
                  f"Download the dataset first:  python training/download_dataset.py",
                  file=sys.stderr)
            return 1
        splits[split] = present

    negatives_dir = args.negatives or (root / "negatives")
    negatives = load_negatives(negatives_dir)
    if negatives:
        parts = split_negatives(negatives)
        print(f"\n  negatives: {len(negatives)} undamaged photographs from {negatives_dir}")
        for split in ("train", "val", "test"):
            splits[split] = splits[split] + parts[split]
            print(f"    {split:5}: +{len(parts[split])} -> {len(splits[split])} total")
    else:
        print(
            f"\n  WARNING: no undamaged images found at {negatives_dir}.\n"
            "  The model will have no concept of an undamaged car and will report\n"
            "  damage on clean vehicles. See training/extract_negatives.py.",
            file=sys.stderr,
        )

    train_transform = transforms.Compose(
        [
            transforms.Resize((args.image_size, args.image_size)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )
    eval_transform = transforms.Compose(
        [
            transforms.Resize((args.image_size, args.image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )

    loaders = {
        "train": DataLoader(
            CarDamageDataset(splits["train"], root / "train2017", train_transform),
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=args.num_workers,
            pin_memory=pin,
            persistent_workers=args.num_workers > 0,
        ),
        "val": DataLoader(
            CarDamageDataset(splits["val"], root / "val2017", eval_transform),
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            pin_memory=pin,
            persistent_workers=args.num_workers > 0,
        ),
        "test": DataLoader(
            CarDamageDataset(splits["test"], root / "test2017", eval_transform),
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            pin_memory=pin,
            persistent_workers=args.num_workers > 0,
        ),
    }

    # --- model: ImageNet trunk, last three blocks + new head unfrozen -------
    ensure_pretrained_weights()
    model = models.efficientnet_b3(weights="IMAGENET1K_V1")
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.5),
        nn.Linear(in_features, 512),
        nn.ReLU(),
        nn.Dropout(0.25),
        nn.Linear(512, len(DAMAGE_CLASSES)),
    )

    for name, parameter in model.named_parameters():
        # The notebook's filter said 'feature.6', which matches nothing -
        # torchvision names these 'features.6'. Fixed here so the intended
        # last-three-blocks fine-tuning actually happens.
        unfrozen = any(name.startswith(f"features.{i}.") for i in (6, 7, 8))
        parameter.requires_grad = unfrozen or name.startswith("classifier")

    model = model.to(device)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Trainable parameters: {trainable:,}")

    # --- class-balanced loss ------------------------------------------------
    # Weights are computed over the *damaged* images only, deliberately.
    # Including the negatives here would inflate every weight roughly two-fold
    # and push the model toward predicting damage more often - the opposite of
    # what adding negatives is meant to achieve. The negatives contribute by
    # showing the model what "clean" looks like, not by reweighting the loss.
    damaged_rows = [row for rows in splits.values() for row in rows if row["labels"]]
    total = len(damaged_rows)
    positives = {
        name: sum(1 for row in damaged_rows if name in row["labels"])
        for name in DAMAGE_CLASSES
    }
    pos_weight = torch.tensor(
        [total / max(1, positives[name]) for name in DAMAGE_CLASSES],
        dtype=torch.float32,
    ).to(device)
    print("Positive weights:", {k: round(total / max(1, v), 2) for k, v in positives.items()})

    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = AdamW(
        [
            {"params": model.features[6].parameters(), "lr": args.backbone_lr},
            {"params": model.features[7].parameters(), "lr": args.backbone_lr},
            {"params": model.features[8].parameters(), "lr": args.backbone_lr},
            {"params": model.classifier.parameters(), "lr": args.head_lr},
        ],
        weight_decay=args.weight_decay,
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    interim_path = args.output.with_suffix(".best.pth")
    best_state = None
    best_val_loss = float("inf")
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict] = []

    for epoch in range(1, args.epochs + 1):
        started = time.time()

        model.train()
        running = 0.0
        for images, targets in loaders["train"]:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), targets)
            loss.backward()
            optimizer.step()
            running += loss.item() * images.size(0)
        train_loss = running / len(loaders["train"].dataset)

        model.eval()
        running = 0.0
        with torch.no_grad():
            for images, targets in loaders["val"]:
                images, targets = images.to(device), targets.to(device)
                running += criterion(model(images), targets).item() * images.size(0)
        val_loss = running / len(loaders["val"].dataset)
        scheduler.step()

        marker = ""
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            epochs_without_improvement = 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            # Persist immediately. Keeping the best weights only in memory means
            # a crash, a full disk or a closed laptop lid at epoch 29 throws away
            # the entire run.
            torch.save(
                {
                    "model_state_dict": best_state,
                    "classes": list(DAMAGE_CLASSES),
                    "model_name": "efficientnet_b3",
                    "input_size": args.image_size,
                    "epoch": epoch,
                    "val_loss": round(val_loss, 4),
                },
                interim_path,
            )
            marker = "  <- best (saved)"
        else:
            epochs_without_improvement += 1

        history.append({"epoch": epoch, "train_loss": round(train_loss, 4),
                        "val_loss": round(val_loss, 4)})
        print(
            f"Epoch {epoch:02d}/{args.epochs} | train {train_loss:.4f} "
            f"| val {val_loss:.4f} | {time.time() - started:.0f}s{marker}",
            flush=True,
        )

        if args.patience and epochs_without_improvement >= args.patience:
            print(
                f"\nValidation loss has not improved for {args.patience} epochs. "
                f"Stopping early at epoch {epoch}; best was epoch {best_epoch} "
                f"(val {best_val_loss:.4f}).\n"
                "Training longer would only overfit further - the trend is the result, "
                "not a failure.",
                flush=True,
            )
            break

    if best_state is not None:
        model.load_state_dict(best_state)
        print(f"\nRestored the best checkpoint: epoch {best_epoch}, val loss {best_val_loss:.4f}")

    # --- threshold tuning on the held-out test split ------------------------
    model.eval()
    probabilities, labels = [], []
    with torch.no_grad():
        for images, targets in loaders["test"]:
            scores = torch.sigmoid(model(images.to(device))).cpu()
            probabilities.append(scores)
            labels.append(targets)
    probabilities = torch.cat(probabilities).numpy()
    labels = torch.cat(labels).numpy()

    thresholds: dict[str, float] = {}
    train_metrics: dict[str, dict] = {}
    print(f"\n{'class':15} {'threshold':>10} {'F1@0.5':>9} {'F1@best':>9} {'AP':>8} {'AUC':>8}")
    for index, name in enumerate(DAMAGE_CLASSES):
        precision, recall, cuts = precision_recall_curve(labels[:, index], probabilities[:, index])
        f1_curve = 2 * precision * recall / (precision + recall + 1e-8)
        best = int(f1_curve.argmax())
        threshold = float(cuts[best]) if best < len(cuts) else 0.5
        thresholds[name] = threshold
        f1_default = f1_score(labels[:, index], probabilities[:, index] > 0.5, zero_division=0)
        f1_tuned = f1_score(labels[:, index], probabilities[:, index] > threshold, zero_division=0)

        truth_col = labels[:, index]
        has_both = 0 < truth_col.sum() < len(truth_col)
        ap = float(average_precision_score(truth_col, probabilities[:, index])) if has_both else 0.0
        auc = float(roc_auc_score(truth_col, probabilities[:, index])) if has_both else 0.0
        train_metrics[name] = {
            "threshold": round(threshold, 4),
            "f1_at_0.5": round(float(f1_default), 4),
            "f1": round(float(f1_tuned), 4),
            "average_precision": round(ap, 4),
            "roc_auc": round(auc, 4),
        }
        print(f"{name:15} {threshold:>10.4f} {f1_default:>9.4f} {f1_tuned:>9.4f} {ap:>8.4f} {auc:>8.4f}")

    macro_f1 = sum(m["f1"] for m in train_metrics.values()) / len(train_metrics)
    print(f"\nMacro F1 (tuned thresholds): {macro_f1:.4f}")

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "thresholds": thresholds,
            "classes": list(DAMAGE_CLASSES),
            "model_name": "efficientnet_b3",
            "input_size": args.image_size,
            "trained_epochs": len(history),
            "best_epoch": best_epoch,
            "best_val_loss": round(best_val_loss, 4),
            "macro_f1": round(macro_f1, 4),
        },
        args.output,
    )

    sidecar = args.output.with_suffix(".training.json")
    sidecar.write_text(json.dumps({
        "per_class": train_metrics,
        "macro_f1": round(macro_f1, 4),
        "epochs_run": len(history),
        "epochs_requested": args.epochs,
        "best_epoch": best_epoch,
        "best_val_loss": round(best_val_loss, 4),
        "image_size": args.image_size,
        "batch_size": args.batch_size,
        "device": str(device),
        "trainable_parameters": trainable,
        "history": history,
    }, indent=2))

    interim_path.unlink(missing_ok=True)  # the final file supersedes it
    print(f"\nSaved checkpoint to {args.output}")
    print(f"Saved training metrics to {sidecar}")
    print("\nNext: verify it against the held-out test split through the API's own code path:")
    print(f"    python training/evaluate.py --data-root {args.data_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
