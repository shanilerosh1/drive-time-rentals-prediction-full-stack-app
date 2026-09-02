"""Convert CarDD's COCO annotations into the YOLO layout, for detector training.

Objective 3 of the proposal calls for a YOLOv8 detector benchmarked against a
YOLOv5 baseline. Those need bounding boxes in YOLO's format rather than the
COCO JSON CarDD ships.

Two details that matter for correctness:

* **Normalised coordinates are scale-invariant.** `download_dataset.py` rescales
  images to a 640 px long edge while COCO boxes are in original-image pixels.
  Dividing by the *original* width and height from the JSON yields normalised
  coordinates that remain correct for the resized file, because the aspect
  ratio is preserved.
* **Undamaged cars are included as background images** - files with no label
  file at all, which is how YOLO represents "nothing here". This is the same
  lesson the classifier taught us: without negatives a detector invents damage
  on clean vehicles.

    python training/prepare_yolo_dataset.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.damage_classes import DAMAGE_CLASSES  # noqa: E402

COCO_TO_CLASS = {
    "dent": "dent",
    "scratch": "scratch",
    "crack": "crack",
    "glass shatter": "glass_shatter",
    "lamp broken": "lamp_broken",
    "tire flat": "tire_flat",
}
CLASS_INDEX = {name: i for i, name in enumerate(DAMAGE_CLASSES)}

# YOLO's own split names; CarDD's "val" becomes YOLO's "val".
SPLIT_MAP = {"train": "train", "val": "val", "test": "test"}


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=root / "data" / "CarDD_COCO")
    parser.add_argument("--out", type=Path, default=root / "data" / "CarDD_YOLO")
    parser.add_argument(
        "--negatives-per-split",
        type=str,
        default="0.70,0.20,0.10",
        help="Fractions of the undamaged images to place in train,val,test",
    )
    parser.add_argument(
        "--no-negatives", action="store_true", help="Exclude the undamaged images"
    )
    parser.add_argument("--symlink", action="store_true",
                        help="Symlink images instead of copying (saves ~450 MB)")
    return parser.parse_args()


def place(src: Path, dst: Path, symlink: bool) -> None:
    if dst.exists():
        return
    if symlink:
        dst.symlink_to(src.resolve())
    else:
        shutil.copy2(src, dst)


def main() -> int:
    args = parse_args()
    root: Path = args.data_root
    out: Path = args.out

    if not (root / "annotations").is_dir():
        print(f"CarDD not found at {root}. Run training/download_dataset.py first.",
              file=sys.stderr)
        return 1

    for split in SPLIT_MAP.values():
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    counts: dict[str, dict[str, int]] = {}
    class_totals: dict[str, int] = defaultdict(int)

    for coco_split, yolo_split in SPLIT_MAP.items():
        with open(root / "annotations" / f"instances_{coco_split}2017.json") as handle:
            data = json.load(handle)

        categories = {c["id"]: c["name"] for c in data["categories"]}
        images = {img["id"]: img for img in data["images"]}

        boxes: dict[int, list[str]] = defaultdict(list)
        skipped = 0
        for annotation in data["annotations"]:
            mapped = COCO_TO_CLASS.get(categories[annotation["category_id"]])
            if mapped is None:
                skipped += 1
                continue
            image = images[annotation["image_id"]]
            width, height = image["width"], image["height"]
            x, y, w, h = annotation["bbox"]

            # COCO gives a top-left corner and a size; YOLO wants a normalised
            # centre and size. Clamp so a box that runs off the edge (a few do)
            # cannot produce an out-of-range coordinate.
            cx = min(max((x + w / 2) / width, 0.0), 1.0)
            cy = min(max((y + h / 2) / height, 0.0), 1.0)
            nw = min(max(w / width, 0.0), 1.0)
            nh = min(max(h / height, 0.0), 1.0)
            if nw <= 0 or nh <= 0:
                skipped += 1
                continue

            boxes[annotation["image_id"]].append(
                f"{CLASS_INDEX[mapped]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"
            )
            class_totals[mapped] += 1

        written = 0
        for image_id, lines in boxes.items():
            name = images[image_id]["file_name"]
            source = root / f"{coco_split}2017" / name
            if not source.exists():
                continue
            place(source, out / "images" / yolo_split / name, args.symlink)
            (out / "labels" / yolo_split / f"{Path(name).stem}.txt").write_text(
                "\n".join(lines) + "\n"
            )
            written += 1

        counts[yolo_split] = {"damaged": written, "boxes": sum(len(v) for v in boxes.values())}
        if skipped:
            counts[yolo_split]["skipped_boxes"] = skipped

    # --- undamaged cars as background images (no label file at all) ---------
    negatives_dir = root / "negatives"
    if not args.no_negatives and negatives_dir.is_dir():
        clean = sorted(negatives_dir.glob("*.jpg"))
        fractions = [float(x) for x in args.negatives_per_split.split(",")]
        n_train = int(len(clean) * fractions[0])
        n_val = int(len(clean) * fractions[1])
        parts = {
            "train": clean[:n_train],
            "val": clean[n_train : n_train + n_val],
            "test": clean[n_train + n_val :],
        }
        for yolo_split, files in parts.items():
            for path in files:
                place(path, out / "images" / yolo_split / path.name, args.symlink)
                # Deliberately no .txt: YOLO reads a missing label file as
                # "this image contains no objects", which is exactly right.
            counts[yolo_split]["background"] = len(files)

    # --- dataset descriptor -------------------------------------------------
    yaml_path = out / "cardd.yaml"
    yaml_path.write_text(
        "# CarDD in YOLO format, generated by training/prepare_yolo_dataset.py\n"
        f"path: {out.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "\n"
        "names:\n"
        + "".join(f"  {i}: {name}\n" for i, name in enumerate(DAMAGE_CLASSES))
    )

    print(f"YOLO dataset written to {out}")
    for split, info in counts.items():
        parts_desc = ", ".join(f"{k}={v}" for k, v in info.items())
        print(f"  {split:5}: {parts_desc}")
    print(f"  boxes per class: {dict(class_totals)}")
    print(f"  descriptor: {yaml_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
