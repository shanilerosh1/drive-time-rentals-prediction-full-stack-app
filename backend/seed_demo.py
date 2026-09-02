"""Populate the database with a demo fleet and a set of completed rentals.

Uses **real CarDD photographs** drawn from the held-out test split, so the
damage on screen is genuine damage and the model's predictions on it are honest
predictions on images it has never seen. Each seeded inspection records the
dataset's ground-truth labels in its notes, which means the dashboard doubles
as a spot-check: what the model said, next to what the annotation says.

Rentals are built by *pairing* real images - a pre-rental photograph whose
ground truth is clean or lightly damaged, and a post-rental photograph of the
same body style carrying additional damage - so the pre/post comparison has
something real to find.

    python seed_demo.py                 # add demo rentals
    python seed_demo.py --reset         # wipe inspections first
    python seed_demo.py --rentals 8     # how many rentals to build

Falls back to generated placeholder images only if the CarDD dataset has not
been downloaded (see training/download_dataset.py).
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.damage_classes import CLASS_LABELS, severity_hint  # noqa: E402
from app.db.base import utcnow  # noqa: E402
from app.db.init_db import create_tables  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.ml import get_predictor  # noqa: E402
from app.models import Detection, Inspection, InspectionImage, User, Vehicle  # noqa: E402
from app.models.enums import (  # noqa: E402
    CaptureAngle,
    ImageStatus,
    InspectionStatus,
    InspectionType,
    UserRole,
)
from app.services import storage  # noqa: E402

DEFAULT_DATA_ROOT = Path(__file__).resolve().parent / "data" / "CarDD_COCO"

COCO_TO_CLASS = {
    "dent": "dent",
    "scratch": "scratch",
    "crack": "crack",
    "glass shatter": "glass_shatter",
    "lamp broken": "lamp_broken",
    "tire flat": "tire_flat",
}

FLEET = ["CBA-4471", "CAR-8820", "KX-1093", "CBB-2255", "CAF-7710"]

LOCATIONS = [
    "Colombo - Union Place",
    "Katunayake Airport",
    "Galle Road branch",
    "Kandy city depot",
]

ANGLES = [
    CaptureAngle.FRONT_LEFT,
    CaptureAngle.LEFT,
    CaptureAngle.REAR,
    CaptureAngle.FRONT_RIGHT,
]


# ---------------------------------------------------------------------------
#  Real CarDD imagery
# ---------------------------------------------------------------------------
def load_cardd_pool(data_root: Path, split: str = "test") -> list[dict]:
    """Return [{path, labels}] for one CarDD split, or [] if it is absent."""
    annotations = data_root / "annotations" / f"instances_{split}2017.json"
    image_dir = data_root / f"{split}2017"
    if not annotations.exists() or not image_dir.is_dir():
        return []

    with open(annotations) as handle:
        data = json.load(handle)

    categories = {c["id"]: c["name"] for c in data["categories"]}
    files = {img["id"]: img["file_name"] for img in data["images"]}

    labels: dict[int, set[str]] = defaultdict(set)
    for annotation in data["annotations"]:
        mapped = COCO_TO_CLASS.get(categories[annotation["category_id"]])
        if mapped:
            labels[annotation["image_id"]].add(mapped)

    pool = []
    for image_id, classes in labels.items():
        path = image_dir / files[image_id]
        if path.exists():
            pool.append({"path": path, "labels": frozenset(classes)})
    return pool


def build_rentals(pool: list[dict], count: int, rng: random.Random) -> list[dict]:
    """Pair real images into rentals with a genuine pre -> post damage story.

    The post-rental set is chosen to contain at least one class the pre-rental
    set does not, so the comparison view has real new damage to report.
    """
    by_class: dict[frozenset, list[dict]] = defaultdict(list)
    for item in pool:
        by_class[item["labels"]].append(item)

    label_sets = sorted(by_class, key=lambda s: (-len(by_class[s]), sorted(s)))
    singles = [s for s in label_sets if len(s) == 1]
    multis = [s for s in label_sets if len(s) >= 2]

    rentals = []
    for index in range(count):
        # Alternate the narrative so the demo covers every outcome.
        story = index % 4

        if story == 0 and singles and multis:
            # Clean-ish handover, extra damage on return.
            pre_set = rng.choice(singles)
            candidates = [s for s in multis if pre_set < s] or multis
            post_set = rng.choice(candidates)
        elif story == 1 and singles:
            # Same damage both ways: pre-existing, not chargeable.
            pre_set = post_set = rng.choice(singles)
        elif story == 2 and multis and singles:
            # Mixed: one class persists, another appears.
            pre_set = rng.choice(singles)
            post_set = rng.choice(multis)
        else:
            # Both sides carry the same single class.
            pre_set = post_set = rng.choice(singles or label_sets)

        rentals.append({
            "pre": rng.choice(by_class[pre_set]),
            "post": rng.choice(by_class[post_set]),
            "pre_labels": sorted(pre_set),
            "post_labels": sorted(post_set),
        })
    return rentals


# ---------------------------------------------------------------------------
#  Fallback imagery (only when the dataset is missing)
# ---------------------------------------------------------------------------
def render_placeholder(seed: int) -> bytes:
    rng = random.Random(seed)
    image = Image.new("RGB", (880, 560), (196, 204, 214))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 880, 300], fill=(168, 182, 200))
    draw.rectangle([0, 300, 880, 560], fill=(96, 99, 104))
    body = (rng.randint(30, 230),) * 3
    draw.rounded_rectangle([120, 250, 760, 400], radius=26, fill=body)
    draw.polygon([(250, 250), (350, 158), (560, 158), (640, 250)],
                 fill=tuple(max(0, c - 26) for c in body))
    for cx in (250, 630):
        draw.ellipse([cx - 46, 354, cx + 46, 446], fill=(26, 27, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
def record_image(db, inspection: Inspection, raw: bytes, angle: CaptureAngle,
                 filename: str, predictor) -> InspectionImage:
    stored = storage.save_image(inspection.id, raw, "image/jpeg")
    result = predictor.predict(raw)

    image = InspectionImage(
        inspection_id=inspection.id,
        original_filename=filename,
        stored_name=stored.stored_name,
        thumbnail_name=stored.thumbnail_name,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        width=stored.width,
        height=stored.height,
        sha256=stored.sha256,
        capture_angle=angle,
        status=ImageStatus.ANALYSED,
        model_name=result.model_name,
        model_version=result.model_version,
        predictor_backend=result.backend,
        inference_ms=round(result.inference_ms, 2),
    )
    db.add(image)
    db.flush()

    for finding in result.findings:
        db.add(Detection(
            image_id=image.id,
            class_name=finding.class_name,
            confidence=finding.confidence,
            threshold=finding.threshold,
            is_positive=finding.is_positive,
            severity_hint=severity_hint(finding.confidence, finding.threshold),
            bbox_x=finding.bbox.x if finding.bbox else None,
            bbox_y=finding.bbox.y if finding.bbox else None,
            bbox_w=finding.bbox.w if finding.bbox else None,
            bbox_h=finding.bbox.h if finding.bbox else None,
        ))
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Delete existing inspections first")
    parser.add_argument("--rentals", type=int, default=6, help="How many rentals to build")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--split", default="test", choices=["train", "val", "test"],
                        help="CarDD split to draw imagery from (test = never trained on)")
    parser.add_argument("--seed", type=int, default=20260831)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    create_tables()
    predictor = get_predictor()
    print(f"Predictor: {predictor.name} ({predictor.model_name})  real={predictor.is_real}")

    pool = load_cardd_pool(args.data_root, args.split)
    if pool:
        print(f"Using {len(pool)} real CarDD photographs from the '{args.split}' split.")
    else:
        print(f"CarDD not found at {args.data_root} - falling back to placeholder imagery.")
        print("Run:  python training/download_dataset.py")

    with SessionLocal() as db:
        if args.reset:
            existing = db.query(Inspection).all()
            for inspection in existing:
                for image in inspection.images:
                    storage.delete_image(inspection.id, image.stored_name, image.thumbnail_name)
                db.delete(inspection)
            db.commit()
            print(f"Removed {len(existing)} existing inspection(s).")

        inspectors = []
        for email, name in [("inspector@drivetime.lk", "Ravindu Perera"),
                            ("nimali@drivetime.lk", "Nimali Fernando")]:
            user = db.query(User).filter(User.email == email).one_or_none()
            if user is None:
                user = User(email=email, full_name=name,
                            hashed_password=hash_password("Inspector123!"),
                            role=UserRole.INSPECTOR)
                db.add(user)
                db.flush()
            inspectors.append(user)

        vehicles = db.query(Vehicle).filter(Vehicle.registration.in_(FLEET)).all()
        if not vehicles:
            print("No fleet vehicles found - start the API once to seed them.")
            return 1

        rentals = (
            build_rentals(pool, args.rentals, rng) if pool
            else [{"pre": None, "post": None, "pre_labels": [], "post_labels": []}
                  for _ in range(args.rentals)]
        )

        existing_refs = {r[0] for r in db.query(Inspection.rental_ref).distinct() if r[0]}
        made = 0
        placeholder_seed = 0

        for index, rental in enumerate(rentals):
            ref = f"R-2026-{4100 + index}"
            if ref in existing_refs:
                print(f"  = {ref} already present, skipping")
                continue

            vehicle = vehicles[index % len(vehicles)]
            inspector = inspectors[index % len(inspectors)]
            location = LOCATIONS[index % len(LOCATIONS)]
            odometer = rng.randrange(18_000, 120_000, 50)

            for kind, side, truth in (
                (InspectionType.PRE_RENTAL, rental["pre"], rental["pre_labels"]),
                (InspectionType.POST_RENTAL, rental["post"], rental["post_labels"]),
            ):
                is_post = kind is InspectionType.POST_RENTAL
                truth_text = ", ".join(CLASS_LABELS.get(c, c) for c in truth) or "no damage annotated"
                inspection = Inspection(
                    vehicle_id=vehicle.id,
                    inspector_id=inspector.id,
                    inspection_type=kind,
                    status=InspectionStatus.COMPLETED,
                    rental_ref=ref,
                    odometer_km=odometer + (rng.randrange(200, 1400, 10) if is_post else 0),
                    location=location,
                    notes=(
                        f"Dataset ground truth for this photograph: {truth_text}. "
                        "Recorded so the model's output can be checked against the "
                        "CarDD annotation."
                    ) if pool else None,
                    started_at=utcnow(),
                    completed_at=utcnow(),
                )
                db.add(inspection)
                db.flush()

                if side is not None:
                    raw = side["path"].read_bytes()
                    record_image(db, inspection, raw, ANGLES[0], side["path"].name, predictor)
                    # A second, clean-ish angle for realism.
                    other = rng.choice(pool)
                    record_image(db, inspection, other["path"].read_bytes(),
                                 ANGLES[1], other["path"].name, predictor)
                else:
                    placeholder_seed += 1
                    record_image(db, inspection, render_placeholder(placeholder_seed),
                                 ANGLES[0], f"placeholder-{placeholder_seed}.jpg", predictor)

                made += 1

            print(f"  + {ref}  {vehicle.registration:9} "
                  f"pre={rental['pre_labels'] or ['clean']} -> post={rental['post_labels'] or ['clean']}")

        db.commit()
        print(f"\nSeeded {made} inspections across {len(rentals)} rentals.")
        if pool:
            print("Each inspection's notes carry the dataset ground truth for comparison.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
