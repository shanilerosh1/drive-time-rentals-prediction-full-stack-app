"""Filesystem-backed image storage.

Every read/write goes through here so that swapping in Azure Blob (the
proposal's Section 3.7 choice) later means reimplementing one module rather
than touching the API layer.
"""
from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.config import settings

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXTENSION_BY_FORMAT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class InvalidImageError(ValueError):
    pass


@dataclass(frozen=True)
class StoredImage:
    stored_name: str
    thumbnail_name: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    sha256: str


def _inspection_dir(inspection_id: int) -> Path:
    path = settings.STORAGE_DIR / "inspections" / str(inspection_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_image(inspection_id: int, raw: bytes, declared_content_type: str | None) -> StoredImage:
    """Validate, persist and thumbnail one upload.

    The content type is taken from the decoded image, not from the client's
    header, so a mislabelled or hostile upload cannot get a wrong extension.
    """
    if not raw:
        raise InvalidImageError("Empty upload.")
    if len(raw) > settings.max_upload_bytes:
        raise InvalidImageError(
            f"Image exceeds the {settings.MAX_UPLOAD_MB} MB limit "
            f"({len(raw) / 1024 / 1024:.1f} MB)."
        )

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()  # cheap structural check; consumes the handle
        with Image.open(io.BytesIO(raw)) as image:
            image_format = (image.format or "").upper()
            image = image.convert("RGB")
            width, height = image.size
            thumbnail = image.copy()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("File is not a readable image.") from exc

    if image_format not in EXTENSION_BY_FORMAT:
        raise InvalidImageError(
            f"Unsupported image format {image_format or 'unknown'}. Use JPEG, PNG or WebP."
        )

    directory = _inspection_dir(inspection_id)
    stem = uuid.uuid4().hex
    extension = EXTENSION_BY_FORMAT[image_format]
    stored_name = f"{stem}{extension}"
    thumbnail_name = f"{stem}_thumb.jpg"

    (directory / stored_name).write_bytes(raw)

    thumbnail.thumbnail(
        (settings.THUMBNAIL_MAX_EDGE, settings.THUMBNAIL_MAX_EDGE), Image.LANCZOS
    )
    thumbnail.save(directory / thumbnail_name, format="JPEG", quality=82, optimize=True)

    return StoredImage(
        stored_name=stored_name,
        thumbnail_name=thumbnail_name,
        content_type=f"image/{'jpeg' if extension == '.jpg' else extension.lstrip('.')}",
        size_bytes=len(raw),
        width=width,
        height=height,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def image_path(inspection_id: int, stored_name: str) -> Path:
    return _inspection_dir(inspection_id) / stored_name


def read_image(inspection_id: int, stored_name: str) -> bytes:
    return image_path(inspection_id, stored_name).read_bytes()


def delete_image(inspection_id: int, stored_name: str, thumbnail_name: str | None) -> None:
    for name in filter(None, (stored_name, thumbnail_name)):
        image_path(inspection_id, name).unlink(missing_ok=True)
