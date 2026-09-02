from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import Inspection, InspectionImage, Vehicle
from app.models.enums import InspectionType
from app.schemas.inspection import ComparisonRead
from app.services import report
from app.services.comparison import build_comparison, latest_inspection

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


def _load(db, inspection_id: int | None) -> Inspection | None:
    if inspection_id is None:
        return None
    inspection = db.execute(
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.vehicle),
            selectinload(Inspection.inspector),
            selectinload(Inspection.images).selectinload(InspectionImage.detections),
        )
    ).scalar_one_or_none()
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Inspection {inspection_id} not found."
        )
    return inspection


def _resolve(
    db,
    vehicle_id: int | None,
    rental_ref: str | None,
    pre_id: int | None,
    post_id: int | None,
) -> dict:
    """Either pin both sides explicitly, or let the vehicle's latest pair stand in."""
    pre = _load(db, pre_id)
    post = _load(db, post_id)

    if pre is None and post is None:
        if vehicle_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide vehicle_id, or pre_inspection_id and post_inspection_id.",
            )
        pre = latest_inspection(db, vehicle_id, InspectionType.PRE_RENTAL, rental_ref)
        post = latest_inspection(db, vehicle_id, InspectionType.POST_RENTAL, rental_ref)

    vehicle_source = pre or post
    if vehicle_source is not None:
        vehicle = vehicle_source.vehicle
    else:
        vehicle = db.get(Vehicle, vehicle_id) if vehicle_id else None

    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found.")

    if pre and post and pre.vehicle_id != post.vehicle_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The two inspections belong to different vehicles.",
        )

    return build_comparison(db, vehicle, pre, post, rental_ref)


@router.get("", response_model=ComparisonRead)
def compare(
    db: DbSession,
    _: CurrentUser,
    vehicle_id: int | None = Query(default=None),
    rental_ref: str | None = Query(default=None),
    pre_inspection_id: int | None = Query(default=None),
    post_inspection_id: int | None = Query(default=None),
) -> ComparisonRead:
    result = _resolve(db, vehicle_id, rental_ref, pre_inspection_id, post_inspection_id)
    return ComparisonRead.model_validate(result, from_attributes=True)


@router.get(
    "/report",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Download the pre/post comparison as a PDF",
)
def download_comparison_report(
    db: DbSession,
    _: CurrentUser,
    vehicle_id: int | None = Query(default=None),
    rental_ref: str | None = Query(default=None),
    pre_inspection_id: int | None = Query(default=None),
    post_inspection_id: int | None = Query(default=None),
) -> Response:
    result = _resolve(db, vehicle_id, rental_ref, pre_inspection_id, post_inspection_id)
    pdf = report.build_comparison_report(result)
    filename = f"comparison-{result['vehicle'].registration}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
