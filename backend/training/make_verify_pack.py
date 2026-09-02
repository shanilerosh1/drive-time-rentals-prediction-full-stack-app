"""Build a hand-verification pack: held-out photographs with a written answer key.

The formal check is `training/evaluate.py`, which scores the whole test split
and reports metrics. This is the informal one: a small set of images whose
answer you already know, to drag into the dashboard and eyeball. It is the
check to run in front of a supervisor, because it needs no statistics to read.

    python training/make_verify_pack.py

Writes backend/data/verify_samples/ containing the photographs, ANSWER_KEY.md
and answer_key.json. Every image comes from the CarDD *test* split, so the
model has never seen any of them.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.damage_classes import CLASS_LABELS, DAMAGE_CLASSES  # noqa: E402

COCO_TO_CLASS = {
    "dent": "dent",
    "scratch": "scratch",
    "crack": "crack",
    "glass shatter": "glass_shatter",
    "lamp broken": "lamp_broken",
    "tire flat": "tire_flat",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--data-root", type=Path, default=root / "data" / "CarDD_COCO")
    parser.add_argument("--out", type=Path, default=root / "data" / "verify_samples")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument(
        "--per-class", type=int, default=2,
        help="Single-damage examples to include for each of the six classes",
    )
    parser.add_argument(
        "--multi", type=int, default=2,
        help="Multi-damage examples to include (the hard cases)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    annotations = args.data_root / "annotations" / f"instances_{args.split}2017.json"
    image_dir = args.data_root / f"{args.split}2017"

    if not annotations.exists():
        print(
            f"Dataset not found at {args.data_root}.\n"
            "Download it first:  python training/download_dataset.py",
            file=sys.stderr,
        )
        return 1

    with open(annotations) as handle:
        data = json.load(handle)

    categories = {c["id"]: c["name"] for c in data["categories"]}
    files = {img["id"]: img["file_name"] for img in data["images"]}

    labels: dict[int, set[str]] = defaultdict(set)
    for annotation in data["annotations"]:
        mapped = COCO_TO_CLASS.get(categories[annotation["category_id"]])
        if mapped:
            labels[annotation["image_id"]].add(mapped)

    # Single-class images make an unambiguous check; sorted for reproducibility.
    by_class: dict[str, list[str]] = defaultdict(list)
    for image_id, classes in labels.items():
        if len(classes) == 1:
            by_class[next(iter(classes))].append(files[image_id])

    picked: list[tuple[str, list[str]]] = []
    for name in DAMAGE_CLASSES:
        for file_name in sorted(by_class[name])[: args.per_class]:
            if (image_dir / file_name).exists():
                picked.append((file_name, [name]))

    multi = sorted(
        (files[i], sorted(c)) for i, c in labels.items() if len(c) >= 3
    )[: args.multi]
    picked += [(fn, truth) for fn, truth in multi if (image_dir / fn).exists()]

    if not picked:
        print(f"No usable images found in {image_dir}.", file=sys.stderr)
        return 1

    shutil.rmtree(args.out, ignore_errors=True)
    args.out.mkdir(parents=True)
    for file_name, _truth in picked:
        shutil.copy(image_dir / file_name, args.out / file_name)

    (args.out / "answer_key.json").write_text(
        json.dumps({fn: truth for fn, truth in picked}, indent=2)
    )

    lines = [
        "# Verification sample pack",
        "",
        f"{len(picked)} photographs from the CarDD **{args.split}** split - images the model",
        "was never trained on. Upload them through the dashboard and compare what it",
        "reports against this key.",
        "",
        "| File | Actual damage (expert annotation) |",
        "|---|---|",
    ]
    for file_name, truth in picked:
        lines.append(
            f"| `{file_name}` | {', '.join(CLASS_LABELS.get(c, c) for c in truth)} |"
        )
    lines += [
        "",
        "## How to read the result",
        "",
        "- Every image here genuinely contains damage; CarDD holds no undamaged cars.",
        "  For a negative control, photograph an undamaged vehicle yourself and upload it.",
        "- `crack` is the weakest class - expect it to be missed sometimes.",
        "- The multi-damage images at the end are the hard cases.",
        "- Near-misses usually mean an *extra* class was reported, not the real one missed.",
        "",
        "Regenerate this pack with `python training/make_verify_pack.py`.",
    ]
    (args.out / "ANSWER_KEY.md").write_text("\n".join(lines) + "\n")

    print(f"Wrote {len(picked)} photographs to {args.out}")
    for file_name, truth in picked:
        print(f"  {file_name}  ->  {', '.join(truth)}")
    print(f"\nAnswer key: {args.out / 'ANSWER_KEY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
