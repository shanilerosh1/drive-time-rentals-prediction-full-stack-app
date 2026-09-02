"""Train YOLOv8 and a YOLOv5 baseline on CarDD, and compare them.

This is Objective 3 of the proposal: "Design, train and fine-tune a YOLOv8 model
for multi-class damage detection and benchmark it against a YOLOv5 baseline."

Both models are trained on identical data, splits, image size, epochs and
augmentation, so the only variable is the architecture. Both start from
COCO-pretrained weights (the transfer-learning strategy of Section 2.4), and
both see the same undamaged background images.

    python training/train_detectors.py --model yolov8n --epochs 40
    python training/train_detectors.py --model yolov5nu --epochs 40
    python training/train_detectors.py --compare        # after both have run

Results land in models/detectors/<name>/ and a combined table in
models/detector_comparison.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.damage_classes import DAMAGE_CLASSES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/{name}.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="yolov8n",
                        help="yolov8n / yolov8s / yolov5nu / yolov5su")
    parser.add_argument("--data", type=Path,
                        default=ROOT / "data" / "CarDD_YOLO" / "cardd.yaml")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--device", default=None, help="mps / cpu / 0")
    parser.add_argument("--out", type=Path, default=ROOT / "models" / "detectors")
    parser.add_argument("--compare", action="store_true",
                        help="Skip training; just build the comparison table")
    parser.add_argument(
        "--resume", action="store_true",
        help="Continue an interrupted run from its last.pt (after a reboot, say)",
    )
    return parser.parse_args()


def ensure_weights(name: str) -> Path:
    """Pre-fetch pretrained weights with curl.

    Ultralytics downloads through Python's HTTP stack, which is blocked in some
    sandboxes while curl is not - the same reason the dataset downloader uses
    curl.
    """
    target = ROOT / f"{name}.pt"
    if target.exists() and target.stat().st_size > 1_000_000:
        return target
    url = WEIGHTS_URL.format(name=name)
    print(f"Fetching pretrained weights: {url}")
    result = subprocess.run(
        ["curl", "-sS", "-L", "--fail", "--retry", "3", "-o", str(target), url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        target.unlink(missing_ok=True)
        print(f"  could not pre-fetch ({result.stderr.strip()[:140]}); "
              "letting ultralytics try.")
        return Path(f"{name}.pt")
    return target


def resolve_device(requested: str | None) -> str:
    import torch

    if requested:
        return requested
    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def train_one(args: argparse.Namespace) -> dict:
    from ultralytics import YOLO

    device = resolve_device(args.device)
    weights = ensure_weights(args.model)
    run_dir = args.out / args.model
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {args.model} on {device} "
          f"({args.epochs} epochs, imgsz {args.imgsz}, batch {args.batch}) ===")

    # An interrupted run leaves last.pt behind; ultralytics can pick it up.
    last = run_dir / "weights" / "last.pt"
    if args.resume and last.exists():
        print(f"Resuming from {last}")
        model = YOLO(str(last))
    else:
        if args.resume:
            print(f"No checkpoint at {last}; starting from scratch.")
        model = YOLO(str(weights))

    started = time.perf_counter()
    model.train(
        resume=bool(args.resume and last.exists()),
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        device=device,
        project=str(args.out),
        name=args.model,
        exist_ok=True,
        seed=0,          # identical initialisation for a fair comparison
        val=True,
        plots=True,
        verbose=True,
    )
    train_seconds = time.perf_counter() - started

    # Evaluate on the held-out *test* split, not the validation split the
    # training loop was already selecting against.
    print(f"\n--- evaluating {args.model} on the held-out test split ---")
    metrics = model.val(data=str(args.data), split="test", device=device, verbose=False)

    per_class = {}
    try:
        for index, name in enumerate(DAMAGE_CLASSES):
            per_class[name] = {
                "map50": round(float(metrics.box.ap50[index]), 4),
                "map50_95": round(float(metrics.box.ap[index]), 4),
                "precision": round(float(metrics.box.p[index]), 4),
                "recall": round(float(metrics.box.r[index]), 4),
            }
    except Exception as exc:  # noqa: BLE001 - class ordering can vary by version
        print(f"  (per-class breakdown unavailable: {exc})")

    result = {
        "model": args.model,
        "device": device,
        "epochs_requested": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "train_seconds": round(train_seconds, 1),
        "parameters": sum(p.numel() for p in model.model.parameters()),
        "map50": round(float(metrics.box.map50), 4),
        "map50_95": round(float(metrics.box.map), 4),
        "precision": round(float(metrics.box.mp), 4),
        "recall": round(float(metrics.box.mr), 4),
        "per_class": per_class,
        "weights": str(run_dir / "weights" / "best.pt"),
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (run_dir / "test_metrics.json").write_text(json.dumps(result, indent=2))
    print(f"\n{args.model}:  mAP@0.5 = {result['map50']:.4f}   "
          f"mAP@0.5:0.95 = {result['map50_95']:.4f}   "
          f"({train_seconds / 60:.1f} min to train)")
    return result


def build_comparison(out: Path) -> dict:
    runs = {}
    for path in sorted(out.glob("*/test_metrics.json")):
        data = json.loads(path.read_text())
        runs[data["model"]] = data
    if not runs:
        print("No completed runs found. Train at least one model first.", file=sys.stderr)
        return {}

    comparison = {
        "runs": runs,
        "compared_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    target = out.parent / "detector_comparison.json"
    target.write_text(json.dumps(comparison, indent=2))

    print(f"\n{'model':12}{'params':>12}{'mAP@0.5':>10}{'mAP@.5:.95':>12}"
          f"{'precision':>11}{'recall':>9}{'train min':>11}")
    print("-" * 77)
    for name, r in runs.items():
        print(f"{name:12}{r['parameters']:>12,}{r['map50']:>10.4f}{r['map50_95']:>12.4f}"
              f"{r['precision']:>11.4f}{r['recall']:>9.4f}{r['train_seconds']/60:>11.1f}")
    print("-" * 77)

    if len(runs) >= 2:
        names = list(runs)
        best = max(names, key=lambda n: runs[n]["map50"])
        other = [n for n in names if n != best][0]
        delta = runs[best]["map50"] - runs[other]["map50"]
        print(f"\n{best} leads {other} by {delta:+.4f} mAP@0.5 "
              f"({delta / max(1e-9, runs[other]['map50']) * 100:+.1f}%).")

    print(f"\nWrote {target}")
    return comparison


def main() -> int:
    args = parse_args()
    if args.compare:
        return 0 if build_comparison(args.out) else 1

    if not args.data.exists():
        print(f"Dataset descriptor not found: {args.data}\n"
              "Run training/prepare_yolo_dataset.py first.", file=sys.stderr)
        return 1

    try:
        import ultralytics  # noqa: F401
    except ImportError:
        print("ultralytics is required:  pip install ultralytics", file=sys.stderr)
        return 1

    train_one(args)
    build_comparison(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
