from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Detection(Base, TimestampMixin):
    """One class score for one image.

    The classifier produces image-level scores, so the four bbox columns are
    null. They exist now so that the YOLOv8 detection backend (Phase 2) can
    write localised findings through the same table and the same API contract,
    without a schema migration or a client-side change.
    """

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(
        ForeignKey("inspection_images.id", ondelete="CASCADE"), index=True, nullable=False
    )
    class_name: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    is_positive: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False)
    severity_hint: Mapped[str] = mapped_column(String(16), nullable=False, default="none")

    # Normalised [0,1] box, null for image-level classification results.
    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float | None] = mapped_column(Float, nullable=True)

    image: Mapped["InspectionImage"] = relationship(back_populates="detections")  # noqa: F821

    @property
    def has_bbox(self) -> bool:
        return None not in (self.bbox_x, self.bbox_y, self.bbox_w, self.bbox_h)
