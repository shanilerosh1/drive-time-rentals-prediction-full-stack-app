from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VehicleBase(BaseModel):
    registration: str = Field(min_length=1, max_length=32)
    make: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=64)
    year: int | None = Field(default=None, ge=1950, le=2100)
    colour: str | None = Field(default=None, max_length=32)
    body_type: str | None = Field(default=None, max_length=32)
    notes: str | None = None

    @field_validator("registration")
    @classmethod
    def _normalise_registration(cls, value: str) -> str:
        # Plates are the natural key; normalise so "ABC-1234" and "abc 1234"
        # cannot become two vehicles.
        return value.strip().upper().replace(" ", "-")


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    make: str | None = Field(default=None, min_length=1, max_length=64)
    model: str | None = Field(default=None, min_length=1, max_length=64)
    year: int | None = Field(default=None, ge=1950, le=2100)
    colour: str | None = Field(default=None, max_length=32)
    body_type: str | None = Field(default=None, max_length=32)
    notes: str | None = None


class VehicleRead(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class VehicleWithStats(VehicleRead):
    inspection_count: int = 0
    last_inspected_at: datetime | None = None
