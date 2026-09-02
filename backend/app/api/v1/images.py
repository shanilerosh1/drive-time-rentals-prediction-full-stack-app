from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models import InspectionImage
from app.schemas.inspection import InspectionImageRead
from app.services import storage

router = APIRouter(prefix="/images", tags=["images"])


def _get_or_404(db, image_id: int) -> InspectionImage:
    image = db.get(InspectionImage, image_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    return image


@router.get("/{image_id}", response_model=InspectionImageRead)
def read_image_meta(image_id: int, db: DbSession, _: CurrentUser) -> InspectionImage:
    return _get_or_404(db, image_id)


@router.get("/{image_id}/file", response_class=Response, summary="Full-size photograph")
def read_image_file(image_id: int, db: DbSession, _: CurrentUser) -> Response:
    image = _get_or_404(db, image_id)
    return _file_response(image.inspection_id, image.stored_name, image.content_type)


@router.get("/{image_id}/thumbnail", response_class=Response, summary="Thumbnail")
def read_image_thumbnail(image_id: int, db: DbSession, _: CurrentUser) -> Response:
    image = _get_or_404(db, image_id)
    name = image.thumbnail_name or image.stored_name
    content_type = "image/jpeg" if image.thumbnail_name else image.content_type
    return _file_response(image.inspection_id, name, content_type)


def _file_response(inspection_id: int, name: str, content_type: str) -> Response:
    path = storage.image_path(inspection_id, name)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The stored file for this image is missing.",
        )
    return Response(
        content=path.read_bytes(),
        media_type=content_type,
        # Immutable content addressed by a UUID name: safe to cache hard.
        headers={"Cache-Control": "private, max-age=86400"},
    )
