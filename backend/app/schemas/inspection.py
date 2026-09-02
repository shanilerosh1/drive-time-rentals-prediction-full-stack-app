from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import (
    CaptureAngle,
    DamageOutcome,
    ImageStatus,
    InspectionStatus,
    InspectionType,
)
from app.schemas.user import UserRead
from app.schemas.vehicle import VehicleRead


class BoundingBoxRead(BaseModel):
    """Normalised [0,1] box. Null on image-level classification results."""

    x: float
    y: float
    w: float
    h: float


class DetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_name: str
    confidence: float
    threshold: float
    is_positive: bool
    severity_hint: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bbox(self) -> BoundingBoxRead | None:
        if None in (self.bbox_x, self.bbox_y, self.bbox_w, self.bbox_h):
            return None
        return BoundingBoxRead(x=self.bbox_x, y=self.bbox_y, w=self.bbox_w, h=self.bbox_h)

    # Source columns, excluded from the response in favour of `bbox`.
    bbox_x: float | None = Field(default=None, exclude=True)
    bbox_y: float | None = Field(default=None, exclude=True)
    bbox_w: float | None = Field(default=None, exclude=True)
    bbox_h: float | None = Field(default=None, exclude=True)


class InspectionImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inspection_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    sha256: str
    capture_angle: CaptureAngle
    status: ImageStatus
    error_message: str | None
    model_name: str | None
    model_version: str | None
    predictor_backend: str | None
    inference_ms: float | None
    created_at: datetime
    detections: list[DetectionRead] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_url(self) -> str:
        return f"/api/v1/images/{self.id}/file"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def thumbnail_url(self) -> str:
        return f"/api/v1/images/{self.id}/thumbnail"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def positive_classes(self) -> list[str]:
        return [d.class_name for d in self.detections if d.is_positive]


class InspectionBase(BaseModel):
    vehicle_id: int
    inspection_type: InspectionType
    rental_ref: str | None = Field(default=None, max_length=64)
    odometer_km: int | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class InspectionCreate(InspectionBase):
    pass


class InspectionUpdate(BaseModel):
    rental_ref: str | None = Field(default=None, max_length=64)
    odometer_km: int | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=128)
    notes: str | None = None
    status: InspectionStatus | None = None


class InspectionSummary(BaseModel):
    """List-row shape: no images, so listing many inspections stays cheap."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    inspector_id: int
    inspection_type: InspectionType
    status: InspectionStatus
    rental_ref: str | None
    odometer_km: int | None
    location: str | None
    notes: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    vehicle: VehicleRead | None = None
    inspector: UserRead | None = None
    image_count: int = 0
    damage_classes: list[str] = []


class InspectionRead(InspectionSummary):
    images: list[InspectionImageRead] = []


class AnalyseRequest(BaseModel):
    """Re-running is opt-in so a completed evidentiary record is not overwritten
    by accident."""

    force: bool = False


class AnalyseResponse(BaseModel):
    inspection_id: int
    analysed: int
    skipped: int
    failed: int
    status: InspectionStatus
    backend: str
    is_real_model: bool
    total_ms: float


class ClassFinding(BaseModel):
    class_name: str
    max_confidence: float
    image_ids: list[int]
    severity_hint: str


class ComparisonClassRow(BaseModel):
    class_name: str
    outcome: DamageOutcome
    pre_confidence: float | None
    post_confidence: float | None
    pre_image_ids: list[int] = []
    post_image_ids: list[int] = []
    severity_hint: str


class ComparisonRead(BaseModel):
    vehicle: VehicleRead
    rental_ref: str | None
    pre_inspection: InspectionRead | None
    post_inspection: InspectionRead | None
    rows: list[ComparisonClassRow] = []
    new_damage_classes: list[str] = []
    pre_existing_classes: list[str] = []
    resolved_classes: list[str] = []
    is_complete: bool = False
    uses_real_model: bool = False
    note: str | None = None


class DashboardStats(BaseModel):
    total_vehicles: int
    total_inspections: int
    inspections_last_7_days: int
    images_analysed: int
    completed_inspections: int
    draft_inspections: int
    damage_class_counts: dict[str, int]
    mean_inference_ms: float | None
    backend: str
    is_real_model: bool
    recent_inspections: list[InspectionSummary] = []
