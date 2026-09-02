"""Runs inference over an inspection's images and records the results."""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.ml import get_predictor
from app.models import Detection, Inspection, InspectionImage
from app.models.enums import ImageStatus, InspectionStatus
from app.services import storage

logger = logging.getLogger(__name__)


def analyse_inspection(db: Session, inspection: Inspection, force: bool = False) -> dict:
    """Score every pending image on `inspection`.

    Idempotent by default: an already-analysed image is skipped unless `force`
    is set, so a retry after a partial failure does not rewrite findings that
    have already been reported.
    """
    predictor = get_predictor()
    started = time.perf_counter()

    targets = [
        image
        for image in inspection.images
        if force or image.status != ImageStatus.ANALYSED
    ]

    inspection.status = InspectionStatus.ANALYSING
    if inspection.started_at is None:
        inspection.started_at = utcnow()
    db.flush()

    analysed = failed = 0
    for image in targets:
        try:
            raw = storage.read_image(inspection.id, image.stored_name)
            result = predictor.predict(raw)
        except Exception as exc:  # noqa: BLE001 - one bad image must not sink the batch
            logger.exception("Inference failed for image %s", image.id)
            image.status = ImageStatus.FAILED
            image.error_message = str(exc)[:500]
            failed += 1
            continue

        # Replace rather than append, so re-analysis cannot leave two
        # generations of findings attached to the same photograph.
        image.detections.clear()
        db.flush()

        for finding in result.findings:
            db.add(
                Detection(
                    image_id=image.id,
                    class_name=finding.class_name,
                    confidence=finding.confidence,
                    threshold=finding.threshold,
                    is_positive=finding.is_positive,
                    severity_hint=finding.severity,
                    bbox_x=finding.bbox.x if finding.bbox else None,
                    bbox_y=finding.bbox.y if finding.bbox else None,
                    bbox_w=finding.bbox.w if finding.bbox else None,
                    bbox_h=finding.bbox.h if finding.bbox else None,
                )
            )

        image.status = ImageStatus.ANALYSED
        image.error_message = None
        image.model_name = result.model_name
        image.model_version = result.model_version
        image.predictor_backend = result.backend
        image.inference_ms = round(result.inference_ms, 2)
        analysed += 1

    statuses = {image.status for image in inspection.images}
    if not inspection.images:
        inspection.status = InspectionStatus.DRAFT
    elif ImageStatus.FAILED in statuses:
        inspection.status = InspectionStatus.FAILED
    elif statuses == {ImageStatus.ANALYSED}:
        inspection.status = InspectionStatus.COMPLETED
        inspection.completed_at = utcnow()
    else:
        inspection.status = InspectionStatus.DRAFT

    db.commit()
    db.refresh(inspection)

    return {
        "inspection_id": inspection.id,
        "analysed": analysed,
        "skipped": len(inspection.images) - len(targets),
        "failed": failed,
        "status": inspection.status,
        "backend": predictor.name,
        "is_real_model": predictor.is_real,
        "total_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def positive_classes(inspection: Inspection) -> dict[str, dict]:
    """Collapse per-image findings into one row per damage class.

    An inspection is a set of photographs of one car, so the operator-facing
    question is "does this car have a scratch", not "does photo 3 have one".
    The strongest score across images wins, and the contributing image ids are
    kept so the dashboard can jump straight to the evidence.
    """
    aggregate: dict[str, dict] = {}
    for image in inspection.images:
        for detection in image.detections:
            if not detection.is_positive:
                continue
            row = aggregate.setdefault(
                detection.class_name,
                {"max_confidence": 0.0, "image_ids": [], "severity_hint": "minor"},
            )
            row["image_ids"].append(image.id)
            if detection.confidence > row["max_confidence"]:
                row["max_confidence"] = detection.confidence
                row["severity_hint"] = detection.severity_hint
    return aggregate
