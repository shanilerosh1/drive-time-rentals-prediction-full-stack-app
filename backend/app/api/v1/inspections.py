from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import Inspection, InspectionImage, Vehicle
from app.models.enums import CaptureAngle, ImageStatus, InspectionStatus, InspectionType, UserRole
from app.schemas.common import Message, Page
from app.schemas.inspection import (
    AnalyseRequest,
    AnalyseResponse,
    InspectionCreate,
    InspectionImageRead,
    InspectionRead,
    InspectionSummary,
    InspectionUpdate,
)
from app.services import report, storage
from app.services.analysis import analyse_inspection, positive_classes
from app.services.storage import InvalidImageError

router = APIRouter(prefix="/inspections", tags=["inspections"])


def _loaded(stmt):
    return stmt.options(
        selectinload(Inspection.vehicle),
        selectinload(Inspection.inspector),
        selectinload(Inspection.images).selectinload(InspectionImage.detections),
    )


def _get_or_404(db, inspection_id: int) -> Inspection:
    inspection = db.execute(
        _loaded(select(Inspection).where(Inspection.id == inspection_id))
    ).scalar_one_or_none()
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found.")
    return inspection


def _assert_can_edit(inspection: Inspection, user) -> None:
    """An inspector owns their own records; an admin may edit any."""
    if user.role != UserRole.ADMIN and inspection.inspector_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify inspections you created.",
        )


def _to_summary(inspection: Inspection) -> InspectionSummary:
    summary = InspectionSummary.model_validate(inspection)
    summary.image_count = len(inspection.images)
    summary.damage_classes = sorted(positive_classes(inspection))
    return summary


def _to_read(inspection: Inspection) -> InspectionRead:
    detail = InspectionRead.model_validate(inspection)
    detail.image_count = len(inspection.images)
    detail.damage_classes = sorted(positive_classes(inspection))
    return detail


@router.get("", response_model=Page[InspectionSummary])
def list_inspections(
    db: DbSession,
    _: CurrentUser,
    vehicle_id: int | None = None,
    inspector_id: int | None = None,
    inspection_type: InspectionType | None = None,
    status_filter: InspectionStatus | None = Query(default=None, alias="status"),
    rental_ref: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[InspectionSummary]:
    filters = []
    if vehicle_id is not None:
        filters.append(Inspection.vehicle_id == vehicle_id)
    if inspector_id is not None:
        filters.append(Inspection.inspector_id == inspector_id)
    if inspection_type is not None:
        filters.append(Inspection.inspection_type == inspection_type)
    if status_filter is not None:
        filters.append(Inspection.status == status_filter)
    if rental_ref:
        filters.append(Inspection.rental_ref == rental_ref)

    total = db.execute(select(func.count()).select_from(Inspection).where(*filters)).scalar_one()
    rows = (
        db.execute(
            _loaded(select(Inspection))
            .where(*filters)
            .order_by(Inspection.created_at.desc(), Inspection.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .unique()
        .all()
    )
    return Page(
        items=[_to_summary(row) for row in rows], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
def create_inspection(
    payload: InspectionCreate, db: DbSession, user: CurrentUser
) -> InspectionRead:
    if db.get(Vehicle, payload.vehicle_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found.")

    inspection = Inspection(**payload.model_dump(), inspector_id=user.id)
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return _to_read(_get_or_404(db, inspection.id))


@router.get("/{inspection_id}", response_model=InspectionRead)
def read_inspection(inspection_id: int, db: DbSession, _: CurrentUser) -> InspectionRead:
    return _to_read(_get_or_404(db, inspection_id))


@router.patch("/{inspection_id}", response_model=InspectionRead)
def update_inspection(
    inspection_id: int, payload: InspectionUpdate, db: DbSession, user: CurrentUser
) -> InspectionRead:
    inspection = _get_or_404(db, inspection_id)
    _assert_can_edit(inspection, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(inspection, field, value)
    db.commit()
    return _to_read(_get_or_404(db, inspection_id))


@router.delete("/{inspection_id}", response_model=Message)
def delete_inspection(inspection_id: int, db: DbSession, user: CurrentUser) -> Message:
    inspection = _get_or_404(db, inspection_id)
    _assert_can_edit(inspection, user)
    for image in inspection.images:
        storage.delete_image(inspection.id, image.stored_name, image.thumbnail_name)
    db.delete(inspection)
    db.commit()
    return Message(detail=f"Inspection #{inspection_id} deleted.")


@router.post(
    "/{inspection_id}/images",
    response_model=list[InspectionImageRead],
    status_code=status.HTTP_201_CREATED,
)
def upload_images(
    inspection_id: int,
    db: DbSession,
    user: CurrentUser,
    files: list[UploadFile] = File(..., description="One or more inspection photographs"),
    capture_angle: CaptureAngle = Form(default=CaptureAngle.OTHER),
    analyse: bool = Form(default=True, description="Run inference immediately after upload"),
) -> list[InspectionImageRead]:
    inspection = _get_or_404(db, inspection_id)
    _assert_can_edit(inspection, user)

    created: list[InspectionImage] = []
    errors: list[str] = []

    for upload in files:
        raw = upload.file.read()
        try:
            stored = storage.save_image(inspection.id, raw, upload.content_type)
        except InvalidImageError as exc:
            errors.append(f"{upload.filename}: {exc}")
            continue

        image = InspectionImage(
            inspection_id=inspection.id,
            original_filename=upload.filename or stored.stored_name,
            stored_name=stored.stored_name,
            thumbnail_name=stored.thumbnail_name,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            width=stored.width,
            height=stored.height,
            sha256=stored.sha256,
            capture_angle=capture_angle,
            status=ImageStatus.PENDING,
        )
        db.add(image)
        created.append(image)

    if not created:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid images were uploaded. " + " ".join(errors),
        )

    if inspection.status in (InspectionStatus.COMPLETED, InspectionStatus.FAILED):
        # New evidence invalidates a completed verdict until it is re-analysed.
        inspection.status = InspectionStatus.DRAFT
        inspection.completed_at = None

    db.commit()

    if analyse:
        analyse_inspection(db, _get_or_404(db, inspection_id))

    refreshed = _get_or_404(db, inspection_id)
    created_ids = {image.id for image in created}
    return [
        InspectionImageRead.model_validate(image)
        for image in refreshed.images
        if image.id in created_ids
    ]


@router.post("/{inspection_id}/analyse", response_model=AnalyseResponse)
def analyse(
    inspection_id: int,
    db: DbSession,
    user: CurrentUser,
    payload: AnalyseRequest | None = None,
) -> AnalyseResponse:
    inspection = _get_or_404(db, inspection_id)
    _assert_can_edit(inspection, user)
    if not inspection.images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload at least one photograph before running analysis.",
        )
    result = analyse_inspection(db, inspection, force=bool(payload and payload.force))
    return AnalyseResponse(**result)


@router.delete("/{inspection_id}/images/{image_id}", response_model=Message)
def delete_image(
    inspection_id: int, image_id: int, db: DbSession, user: CurrentUser
) -> Message:
    inspection = _get_or_404(db, inspection_id)
    _assert_can_edit(inspection, user)
    image = next((i for i in inspection.images if i.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    storage.delete_image(inspection.id, image.stored_name, image.thumbnail_name)
    db.delete(image)
    db.commit()
    return Message(detail=f"Image #{image_id} deleted.")


@router.get(
    "/{inspection_id}/report",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Download the inspection report as a PDF",
)
def download_report(inspection_id: int, db: DbSession, _: CurrentUser) -> Response:
    inspection = _get_or_404(db, inspection_id)
    pdf = report.build_inspection_report(inspection)
    filename = f"inspection-{inspection.id}-{inspection.vehicle.registration}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
