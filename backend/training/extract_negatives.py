"""Extract undamaged car photographs to use as negative training examples.

Why this exists
---------------
CarDD contains 4,000 photographs and *every one of them shows damage*. A model
trained on it alone never learns what an undamaged car looks like, so asked
"which damage is in this photo?" about a clean car it answers with whichever
class has the lowest threshold rather than "none". That is not a tuning
problem; it is a missing half of the problem definition.

These images come from Stanford Cars (marketing and street photographs of
ordinary vehicles) and are added to training with an all-zero label vector,
which teaches the model that "no damage" is a valid answer.

    python training/extract_negatives.py

Writes backend/data/CarDD_COCO/negatives/ plus a manifest.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parquet", type=Path, default=root / "data" / "negatives_raw" / "part0.parquet"
    )
    parser.add_argument(
        "--out", type=Path, default=root / "data" / "CarDD_COCO" / "negatives"
    )
    parser.add_argument("--max-edge", type=int, default=640)
    parser.add_argument("--quality", type=int, default=92)
    parser.add_argument(
        "--limit", type=int, default=0, help="Cap the number extracted (0 = all)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.parquet.exists():
        print(
            f"Source not found: {args.parquet}\n"
            "Download it with:\n"
            "  curl -L -o data/negatives_raw/part0.parquet \\\n"
            "    https://huggingface.co/datasets/Multimodal-Fatima/StanfordCars_test/"
            "resolve/main/data/test-00000-of-00003-18db3ba1d2223f87.parquet",
            file=sys.stderr,
        )
        return 1

    try:
        import pyarrow.parquet as pq
        from PIL import Image
    except ImportError:
        print("pyarrow and Pillow are required: pip install pyarrow", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    reader = pq.ParquetFile(args.parquet)

    written = 0
    skipped = 0
    names: list[str] = []

    for group in range(reader.num_row_groups):
        # Read only the image column: the file also carries 20-odd caption and
        # embedding columns we have no use for, and they dominate its size.
        table = reader.read_row_group(group, columns=["image"]).to_pydict()
        for record in table["image"]:
            if args.limit and written >= args.limit:
                break
            raw = record.get("bytes")
            if not raw:
                skipped += 1
                continue
            try:
                with Image.open(io.BytesIO(raw)) as handle:
                    image = handle.convert("RGB")
                    if max(image.size) > args.max_edge:
                        scale = args.max_edge / max(image.size)
                        image = image.resize(
                            (round(image.width * scale), round(image.height * scale)),
                            Image.LANCZOS,
                        )
                    name = f"clean_{written:05d}.jpg"
                    image.save(args.out / name, format="JPEG",
                               quality=args.quality, optimize=True)
                    names.append(name)
                    written += 1
            except Exception:  # noqa: BLE001 - a corrupt row is not fatal
                skipped += 1
        if args.limit and written >= args.limit:
            break

    (args.out / "manifest.json").write_text(json.dumps({
        "source": "Multimodal-Fatima/StanfordCars_test (Stanford Cars)",
        "purpose": "negative examples - undamaged vehicles, all-zero damage labels",
        "count": written,
        "files": names,
    }, indent=2))

    size_mb = sum(f.stat().st_size for f in args.out.glob("*.jpg")) / 1024 / 1024
    print(f"Extracted {written} undamaged car photographs to {args.out} ({size_mb:.0f} MB)")
    if skipped:
        print(f"  skipped {skipped} unreadable rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
