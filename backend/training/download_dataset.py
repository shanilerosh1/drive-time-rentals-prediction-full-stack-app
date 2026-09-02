"""Download the CarDD dataset from Hugging Face into a local COCO layout.

CarDD (Wang et al., 2023) is the dataset named in the dissertation proposal.
The `shawnmichael/CarDD` mirror is public, Apache-2.0, and already carries the
COCO annotations the training script expects.

    python training/download_dataset.py

Produces:

    backend/data/CarDD_COCO/
        annotations/instances_{train,val,test}2017.json
        {train,val,test}2017/*.jpg

Images are fetched in parallel from the CDN and downscaled on the way in.
The originals are 1000x667 (~800 KB each, ~3 GB total); the model trains at
224x224, so a 640 px long edge preserves everything the network can use while
cutting the dataset to roughly a tenth of the size - and making every training
epoch faster, because JPEG decode dominates the input pipeline.
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = "shawnmichael/CarDD"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main"
SPLITS = {"train": "train", "val": "val", "test": "test"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "CarDD_COCO",
    )
    parser.add_argument("--workers", type=int, default=16, help="Parallel connections")
    parser.add_argument(
        "--max-edge",
        type=int,
        default=640,
        help="Downscale so the long edge is at most this many pixels (0 = keep original)",
    )
    parser.add_argument("--quality", type=int, default=92, help="JPEG quality when rescaling")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--splits", nargs="+", default=list(SPLITS), choices=list(SPLITS),
        help="Which splits to fetch (test alone is enough to run an evaluation)",
    )
    return parser.parse_args()


def fetch(url: str, retries: int) -> bytes:
    """Fetch one URL via curl.

    curl rather than urllib deliberately: Python's socket layer cannot reach
    this host in some sandboxed environments, while curl can, and curl also
    brings connection reuse and retry handling for free.
    """
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        temporary = Path(handle.name)
    try:
        result = subprocess.run(
            ["curl", "-sS", "-L", "--fail", "--retry", str(retries),
             "--retry-delay", "2", "--max-time", "120", "-o", str(temporary), url],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed ({result.returncode}): {result.stderr.strip()[:200]}")
        return temporary.read_bytes()
    finally:
        temporary.unlink(missing_ok=True)


def fetch_many(jobs: list[tuple[str, Path]], workers: int, retries: int) -> list[str]:
    """Download many URLs with one curl process using its parallel transfer mode.

    One process with connection reuse beats N processes competing for sockets,
    and keeps the whole batch under a single retry policy.
    """
    if not jobs:
        return []

    with tempfile.NamedTemporaryFile("w", suffix=".curlrc", delete=False) as handle:
        for url, target in jobs:
            # curl config format: one directive per line, values quoted.
            handle.write(f'url = "{url}"\noutput = "{target}"\n')
        config = Path(handle.name)

    try:
        result = subprocess.run(
            ["curl", "-sS", "-L", "--fail", "--parallel",
             "--parallel-max", str(workers),
             "--retry", str(retries), "--retry-delay", "2", "--max-time", "180",
             "-K", str(config)],
            capture_output=True, text=True,
        )
    finally:
        config.unlink(missing_ok=True)

    missing = [str(target) for _url, target in jobs if not target.exists()]
    if result.returncode != 0 and not missing:
        # curl reports a non-zero code if any single transfer failed, even when
        # the rest succeeded; only treat it as fatal if files are actually absent.
        pass
    return missing


def download_annotations(out: Path, splits: list[str], retries: int) -> dict[str, list[str]]:
    """Fetch the COCO annotation files; they also name every image to download."""
    annotations_dir = out / "annotations"
    annotations_dir.mkdir(parents=True, exist_ok=True)

    filenames: dict[str, list[str]] = {}
    for split in splits:
        name = f"instances_{split}2017.json"
        target = annotations_dir / name
        if not target.exists():
            print(f"  annotations: {name}")
            target.write_bytes(fetch(f"{BASE}/annotations/{name}", retries))
        data = json.loads(target.read_text())
        filenames[split] = [image["file_name"] for image in data["images"]]
    return filenames


def save_image(raw: bytes, target: Path, max_edge: int, quality: int) -> None:
    if not max_edge:
        target.write_bytes(raw)
        return

    from PIL import Image

    with Image.open(io.BytesIO(raw)) as image:
        image = image.convert("RGB")
        if max(image.size) > max_edge:
            scale = max_edge / max(image.size)
            new_size = (round(image.width * scale), round(image.height * scale))
            image = image.resize(new_size, Image.LANCZOS)
        image.save(target, format="JPEG", quality=quality, optimize=True)


def main() -> int:
    args = parse_args()
    out: Path = args.out

    print(f"Downloading CarDD from {REPO}")
    filenames = download_annotations(out, args.splits, args.retries)

    jobs: list[tuple[str, str, Path]] = []
    for split in args.splits:
        directory = out / f"{split}2017"
        directory.mkdir(parents=True, exist_ok=True)
        for name in filenames[split]:
            target = directory / name
            if not target.exists():
                jobs.append((SPLITS[split], name, target))

    total_expected = sum(len(v) for v in filenames.values())
    if not jobs:
        print(f"All {total_expected} images already present at {out}")
        return 0

    print(f"{total_expected} images listed, {len(jobs)} to fetch "
          f"({args.workers} parallel connections"
          f"{f', rescaled to {args.max_edge} px long edge' if args.max_edge else ''})")

    failures: list[str] = []
    started = time.perf_counter()

    # Download in chunks so progress is visible and a stall is obvious.
    CHUNK = 250
    fetched = 0
    for offset in range(0, len(jobs), CHUNK):
        batch = jobs[offset : offset + CHUNK]
        transfers = [
            (f"{BASE}/images/{folder}/{name}", target.with_suffix(".part"))
            for folder, name, target in batch
        ]
        fetch_many(transfers, args.workers, args.retries)

        # Rescale locally, in parallel: JPEG decode is the slow part and the
        # GIL is released inside Pillow, so threads genuinely help here.
        def finish(job: tuple[str, str, Path]) -> str | None:
            """Rescale one downloaded file, re-fetching it once if it is corrupt.

            A truncated transfer must not abort the batch: it is a single bad
            image out of thousands, and one retry almost always fixes it.
            """
            folder, name, target = job
            part = target.with_suffix(".part")
            for attempt in (1, 2):
                try:
                    if not part.exists() or part.stat().st_size == 0:
                        raise OSError("missing or empty download")
                    save_image(part.read_bytes(), target, args.max_edge, args.quality)
                    part.unlink(missing_ok=True)
                    return None
                except Exception:  # noqa: BLE001 - corrupt or partial transfer
                    part.unlink(missing_ok=True)
                    if attempt == 2:
                        return name
                    try:
                        part.write_bytes(fetch(f"{BASE}/images/{folder}/{name}", args.retries))
                    except Exception:  # noqa: BLE001
                        return name
            return name

        with ThreadPoolExecutor(max_workers=8) as pool:
            failures.extend(name for name in pool.map(finish, batch) if name)

        fetched += len(batch)
        rate = fetched / max(1e-6, time.perf_counter() - started)
        remaining = (len(jobs) - fetched) / max(1e-6, rate)
        print(
            f"  {fetched}/{len(jobs)}  ({rate:.1f} img/s, ~{remaining / 60:.1f} min left)",
            flush=True,
        )

    if failures:
        print(f"\n{len(failures)} image(s) could not be retrieved:", file=sys.stderr)
        for name in failures[:10]:
            print(f"  {name}", file=sys.stderr)
        print("  Re-run this command to retry only the missing files.", file=sys.stderr)

    size_mb = sum(f.stat().st_size for f in out.rglob("*.jpg")) / 1024 / 1024
    print(f"\nDataset ready at {out}  ({size_mb:.0f} MB)")
    for split in args.splits:
        count = len(list((out / f"{split}2017").glob("*.jpg")))
        print(f"  {split:5}: {count} images")

    with open(out / "annotations" / f"instances_{args.splits[0]}2017.json") as handle:
        classes = [c["name"] for c in json.load(handle)["categories"]]
    print(f"  classes: {classes}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
