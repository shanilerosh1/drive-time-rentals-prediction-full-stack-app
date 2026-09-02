from datetime import timedelta

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.db.base import utcnow
from app.ml import get_predictor
from app.models import Detection, Inspection, InspectionImage, Vehicle
from app.models.enums import ImageStatus, InspectionStatus
from app.schemas.inspection import DashboardStats, InspectionSummary
from app.services.analysis import positive_classes

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: DbSession, _: CurrentUser) -> DashboardStats:
    predictor = get_predictor()
    week_ago = utcnow() - timedelta(days=7)

    def count(model, *filters) -> int:
        return db.execute(select(func.count()).select_from(model).where(*filters)).scalar_one()

    # How many distinct images carry each positive class, not how many
    # detection rows exist - a class detected in three photos of one car is
    # three pieces of evidence, which is what an operator wants to see.
    class_rows = db.execute(
        select(Detection.class_name, func.count(func.distinct(Detection.image_id)))
        .where(Detection.is_positive.is_(True))
        .group_by(Detection.class_name)
    ).all()

    mean_ms = db.execute(
        select(func.avg(InspectionImage.inference_ms)).where(
            InspectionImage.inference_ms.is_not(None)
        )
    ).scalar_one_or_none()

    recent = (
        db.execute(
            select(Inspection)
            .options(
                selectinload(Inspection.vehicle),
                selectinload(Inspection.inspector),
                selectinload(Inspection.images).selectinload(InspectionImage.detections),
            )
            .order_by(Inspection.created_at.desc(), Inspection.id.desc())
            .limit(6)
        )
        .scalars()
        .unique()
        .all()
    )

    summaries = []
    for inspection in recent:
        summary = InspectionSummary.model_validate(inspection)
        summary.image_count = len(inspection.images)
        summary.damage_classes = sorted(positive_classes(inspection))
        summaries.append(summary)

    return DashboardStats(
        total_vehicles=count(Vehicle),
        total_inspections=count(Inspection),
        inspections_last_7_days=count(Inspection, Inspection.created_at >= week_ago),
        images_analysed=count(InspectionImage, InspectionImage.status == ImageStatus.ANALYSED),
        completed_inspections=count(Inspection, Inspection.status == InspectionStatus.COMPLETED),
        draft_inspections=count(Inspection, Inspection.status == InspectionStatus.DRAFT),
        damage_class_counts={name: total for name, total in class_rows},
        mean_inference_ms=round(mean_ms, 2) if mean_ms is not None else None,
        backend=predictor.name,
        is_real_model=predictor.is_real,
        recent_inspections=summaries,
    )
