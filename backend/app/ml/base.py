"""The contract every inference backend implements.

Keeping this narrow - bytes in, `PredictionResult` out - is what lets the mock,
the EfficientNet classifier and a future YOLOv8 detector be swapped without the
API, the database or the Angular client noticing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.damage_classes import DAMAGE_CLASSES, severity_hint


@dataclass(frozen=True)
class BoundingBox:
    """Normalised to [0, 1] against the image's own width/height."""

    x: float
    y: float
    w: float
    h: float


@dataclass
class DamageFinding:
    class_name: str
    confidence: float
    threshold: float
    bbox: BoundingBox | None = None

    @property
    def is_positive(self) -> bool:
        return self.confidence >= self.threshold

    @property
    def severity(self) -> str:
        return severity_hint(self.confidence, self.threshold)


@dataclass
class PredictionResult:
    findings: list[DamageFinding]
    model_name: str
    model_version: str
    backend: str
    inference_ms: float
    classes: tuple[str, ...] = field(default=DAMAGE_CLASSES)

    @property
    def positive_findings(self) -> list[DamageFinding]:
        return [f for f in self.findings if f.is_positive]


class Predictor(ABC):
    """Base class for an inference backend."""

    name: str = "predictor"
    model_name: str = "unknown"
    model_version: str = "0"

    @abstractmethod
    def predict(self, image_bytes: bytes) -> PredictionResult:
        """Score one image. Must not mutate or retain `image_bytes`."""

    @property
    def is_real(self) -> bool:
        """False for stand-ins whose output must never be presented as evidence."""
        return True

    def describe(self) -> dict:
        return {
            "backend": self.name,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "is_real": self.is_real,
            "classes": list(DAMAGE_CLASSES),
            "produces_bounding_boxes": False,
        }
