"""YOLOv8 detection backend (dissertation Phase 2).

Unused until a fine-tuned detection checkpoint exists at `DETECTOR_WEIGHTS`.
It writes through the same `DamageFinding` contract as the classifier, with the
bounding box populated, so enabling it changes what the dashboard draws without
changing any API shape.
"""
from __future__ import annotations

import io
import time
from pathlib import Path

from PIL import Image

from app.core.damage_classes import DAMAGE_CLASSES, DEFAULT_THRESHOLDS
from app.ml.base import BoundingBox, DamageFinding, Predictor, PredictionResult

DEFAULT_CONFIDENCE_FLOOR = 0.25


class UltralyticsNotInstalledError(RuntimeError):
    pass


class YoloDetector(Predictor):
    name = "detector"
    model_name = "yolov8"

    def __init__(self, weights_path: Path, confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR):
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise UltralyticsNotInstalledError(
                "ultralytics is required for the detector backend. "
                "Install it with: pip install ultralytics"
            ) from exc

        self.weights_path = Path(weights_path)
        if not self.weights_path.exists():
            raise FileNotFoundError(f"Detector weights not found: {self.weights_path}")

        self.model = YOLO(str(self.weights_path))
        self.confidence_floor = confidence_floor
        self.model_version = str(int(self.weights_path.stat().st_mtime))
        # Ultralytics exposes its own id->name map; fall back to our taxonomy.
        self.class_names: dict[int, str] = dict(getattr(self.model, "names", {})) or dict(
            enumerate(DAMAGE_CLASSES)
        )

    def predict(self, image_bytes: bytes) -> PredictionResult:
        started = time.perf_counter()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        width, height = image.size

        results = self.model.predict(image, conf=self.confidence_floor, verbose=False)

        findings: list[DamageFinding] = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls.item())
                class_name = self._normalise(self.class_names.get(class_id, str(class_id)))
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                findings.append(
                    DamageFinding(
                        class_name=class_name,
                        confidence=round(confidence, 4),
                        threshold=float(
                            DEFAULT_THRESHOLDS.get(class_name, self.confidence_floor)
                        ),
                        bbox=BoundingBox(
                            x=max(0.0, x1 / width),
                            y=max(0.0, y1 / height),
                            w=min(1.0, (x2 - x1) / width),
                            h=min(1.0, (y2 - y1) / height),
                        ),
                    )
                )

        return PredictionResult(
            findings=findings,
            model_name=self.model_name,
            model_version=self.model_version,
            backend=self.name,
            inference_ms=(time.perf_counter() - started) * 1000,
        )

    @staticmethod
    def _normalise(raw: str) -> str:
        """Map dataset label spellings onto our snake_case taxonomy."""
        return raw.strip().lower().replace(" ", "_").replace("-", "_")

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "produces_bounding_boxes": True,
                "weights_path": str(self.weights_path),
                "confidence_floor": self.confidence_floor,
                "class_names": self.class_names,
            }
        )
        return info
