"""ORM models. Importing this package registers every table on `Base`."""
from app.db.base import Base
from app.models.detection import Detection
from app.models.enums import (
    CaptureAngle,
    DamageOutcome,
    ImageStatus,
    InspectionStatus,
    InspectionType,
    UserRole,
)
from app.models.image import InspectionImage
from app.models.inspection import Inspection
from app.models.user import User
from app.models.vehicle import Vehicle

__all__ = [
    "Base",
    "CaptureAngle",
    "DamageOutcome",
    "Detection",
    "ImageStatus",
    "Inspection",
    "InspectionImage",
    "InspectionStatus",
    "InspectionType",
    "User",
    "UserRole",
    "Vehicle",
]
