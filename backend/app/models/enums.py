"""Domain enumerations shared by the ORM models and the API schemas."""
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    INSPECTOR = "inspector"


class InspectionType(StrEnum):
    PRE_RENTAL = "pre_rental"
    POST_RENTAL = "post_rental"


class InspectionStatus(StrEnum):
    DRAFT = "draft"           # created, images may still be uploading
    ANALYSING = "analysing"   # inference in flight
    COMPLETED = "completed"   # every image analysed
    FAILED = "failed"         # inference failed for at least one image
    CANCELLED = "cancelled"


class ImageStatus(StrEnum):
    PENDING = "pending"
    ANALYSED = "analysed"
    FAILED = "failed"


class CaptureAngle(StrEnum):
    FRONT = "front"
    FRONT_LEFT = "front_left"
    FRONT_RIGHT = "front_right"
    LEFT = "left"
    RIGHT = "right"
    REAR = "rear"
    REAR_LEFT = "rear_left"
    REAR_RIGHT = "rear_right"
    ROOF = "roof"
    INTERIOR_DETAIL = "detail"
    OTHER = "other"


class DamageOutcome(StrEnum):
    """Result of comparing a pre-rental inspection against a post-rental one."""
    NEW = "new"                   # absent before, present after -> chargeable
    PRE_EXISTING = "pre_existing" # present in both -> not chargeable
    RESOLVED = "resolved"         # present before, absent after -> repaired/false positive
