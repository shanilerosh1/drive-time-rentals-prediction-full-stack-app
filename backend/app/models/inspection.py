from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import InspectionStatus, InspectionType


class Inspection(Base, TimestampMixin):
    """One walk-around of one vehicle, at either check-out or check-in.

    `rental_ref` is what pairs a pre-rental inspection with its post-rental
    counterpart; the comparison endpoint keys off it.
    """

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inspector_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    inspection_type: Mapped[InspectionType] = mapped_column(
        Enum(InspectionType, native_enum=False, length=20), nullable=False
    )
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus, native_enum=False, length=20),
        default=InspectionStatus.DRAFT,
        nullable=False,
    )
    rental_ref: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    odometer_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="inspections")  # noqa: F821
    inspector: Mapped["User"] = relationship(back_populates="inspections")  # noqa: F821
    images: Mapped[list["InspectionImage"]] = relationship(  # noqa: F821
        back_populates="inspection",
        cascade="all, delete-orphan",
        order_by="InspectionImage.id",
    )
