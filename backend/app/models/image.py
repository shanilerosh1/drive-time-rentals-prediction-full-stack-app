from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import CaptureAngle, ImageStatus


class InspectionImage(Base, TimestampMixin):
    """A stored inspection photograph and the provenance of its analysis.

    `sha256` is recorded at upload so a report can later demonstrate that the
    bytes behind a finding are the bytes that were analysed - the evidentiary
    requirement in the dissertation's dispute-resolution use case.
    """

    __tablename__ = "inspection_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    thumbnail_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    capture_angle: Mapped[CaptureAngle] = mapped_column(
        Enum(CaptureAngle, native_enum=False, length=20),
        default=CaptureAngle.OTHER,
        nullable=False,
    )

    status: Mapped[ImageStatus] = mapped_column(
        Enum(ImageStatus, native_enum=False, length=20), default=ImageStatus.PENDING, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Analysis provenance
    model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    predictor_backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    inference_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    inspection: Mapped["Inspection"] = relationship(back_populates="images")  # noqa: F821
    detections: Mapped[list["Detection"]] = relationship(  # noqa: F821
        back_populates="image", cascade="all, delete-orphan", order_by="Detection.id"
    )
