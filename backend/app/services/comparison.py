"""Pre-rental vs post-rental damage comparison.

This is the artefact's core operational claim: an objective, timestamped
statement of which damage is new on return and which was already present at
handover.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Inspection, Vehicle
from app.models.enums import DamageOutcome, InspectionStatus, InspectionType
from app.services.analysis import positive_classes


def latest_inspection(
    db: Session,
    vehicle_id: int,
    inspection_type: InspectionType,
    rental_ref: str | None = None,
) -> Inspection | None:
    stmt = (
        select(Inspection)
        .where(
            Inspection.vehicle_id == vehicle_id,
            Inspection.inspection_type == inspection_type,
            Inspection.status.in_(
                [InspectionStatus.COMPLETED, InspectionStatus.FAILED, InspectionStatus.DRAFT]
            ),
        )
        .order_by(Inspection.created_at.desc())
    )
    if rental_ref:
        stmt = stmt.where(Inspection.rental_ref == rental_ref)
    return db.execute(stmt).scalars().first()


def build_comparison(
    db: Session,
    vehicle: Vehicle,
    pre: Inspection | None,
    post: Inspection | None,
    rental_ref: str | None,
) -> dict:
    pre_classes = positive_classes(pre) if pre else {}
    post_classes = positive_classes(post) if post else {}

    rows = []
    for class_name in sorted(set(pre_classes) | set(post_classes)):
        in_pre = class_name in pre_classes
        in_post = class_name in post_classes

        if in_pre and in_post:
            outcome = DamageOutcome.PRE_EXISTING
        elif in_post:
            outcome = DamageOutcome.NEW
        else:
            outcome = DamageOutcome.RESOLVED

        source = post_classes.get(class_name) or pre_classes[class_name]
        rows.append(
            {
                "class_name": class_name,
                "outcome": outcome,
                "pre_confidence": pre_classes.get(class_name, {}).get("max_confidence"),
                "post_confidence": post_classes.get(class_name, {}).get("max_confidence"),
                "pre_image_ids": pre_classes.get(class_name, {}).get("image_ids", []),
                "post_image_ids": post_classes.get(class_name, {}).get("image_ids", []),
                "severity_hint": source["severity_hint"],
            }
        )

    def classes_with(outcome: DamageOutcome) -> list[str]:
        return [row["class_name"] for row in rows if row["outcome"] == outcome]

    is_complete = bool(
        pre
        and post
        and pre.status == InspectionStatus.COMPLETED
        and post.status == InspectionStatus.COMPLETED
    )

    note = None
    if not pre and not post:
        note = "No inspections recorded for this vehicle yet."
    elif not pre:
        note = (
            "No pre-rental inspection found, so no baseline exists: damage found on "
            "return cannot be attributed to this rental."
        )
    elif not post:
        note = "No post-rental inspection yet - showing the handover baseline only."
    elif not is_complete:
        note = "One or both inspections are not fully analysed; findings are provisional."

    uses_real_model = _uses_real_model(pre) and _uses_real_model(post)

    return {
        "vehicle": vehicle,
        "rental_ref": rental_ref or (post.rental_ref if post else None) or (pre.rental_ref if pre else None),
        "pre_inspection": pre,
        "post_inspection": post,
        "rows": rows,
        "new_damage_classes": classes_with(DamageOutcome.NEW),
        "pre_existing_classes": classes_with(DamageOutcome.PRE_EXISTING),
        "resolved_classes": classes_with(DamageOutcome.RESOLVED),
        "is_complete": is_complete,
        "uses_real_model": uses_real_model,
        "note": note,
    }


def _uses_real_model(inspection: Inspection | None) -> bool:
    if inspection is None or not inspection.images:
        return False
    backends = {image.predictor_backend for image in inspection.images if image.predictor_backend}
    return bool(backends) and "mock" not in backends
