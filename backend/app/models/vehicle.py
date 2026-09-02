from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Vehicle(Base, TimestampMixin):
    """A fleet vehicle. Registration is the operator-facing natural key."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    registration: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    make: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    colour: Mapped[str | None] = mapped_column(String(32), nullable=True)
    body_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    inspections: Mapped[list["Inspection"]] = relationship(  # noqa: F821
        back_populates="vehicle", cascade="all, delete-orphan"
    )
