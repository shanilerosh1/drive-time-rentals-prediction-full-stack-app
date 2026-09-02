"""EfficientNet-B3 multi-label damage classifier.

Mirrors the architecture built in `car-damage-classification.ipynb`: an
ImageNet-pretrained EfficientNet-B3 trunk with the default classifier replaced
by Dropout -> Linear(1536, 512) -> ReLU -> Dropout -> Linear(512, 6), trained
with BCEWithLogitsLoss under per-class positive weights.

torch is imported lazily so the API runs on a machine with no ML stack
installed; only constructing this class pulls it in.
"""
from __future__ import annotations

import io
import time
from pathlib import Path

from PIL import Image

from app.core.damage_classes import DAMAGE_CLASSES, DEFAULT_THRESHOLDS
from app.ml.base import DamageFinding, Predictor, PredictionResult

# Matches the notebook's preprocessing exactly - any drift here silently
# degrades accuracy, so the constants are kept together and commented.
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
INPUT_SIZE = (224, 224)
CLASSIFIER_HIDDEN = 512


class TorchNotInstalledError(RuntimeError):
    pass


class EfficientNetClassifier(Predictor):
    name = "classifier"
    model_name = "efficientnet_b3"

    def __init__(self, weights_path: Path, device: str | None = None):
        try:
            import torch
            from torchvision import models, transforms
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise TorchNotInstalledError(
                "torch/torchvision are required for the classifier backend. "
                "Install them with: pip install -r requirements-ml.txt"
            ) from exc

        self._torch = torch
        self.weights_path = Path(weights_path)
        if not self.weights_path.exists():
            raise FileNotFoundError(f"Model weights not found: {self.weights_path}")

        checkpoint = torch.load(self.weights_path, map_location="cpu", weights_only=False)

        # The notebook saves a dict; tolerate a bare state_dict too.
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
            self.classes = tuple(checkpoint.get("classes") or DAMAGE_CLASSES)
            self.thresholds = dict(checkpoint.get("thresholds") or DEFAULT_THRESHOLDS)
            self.model_name = checkpoint.get("model_name", self.model_name)
            self._input_size = int(checkpoint.get("input_size", INPUT_SIZE[0]))
        else:
            state_dict = checkpoint
            self.classes = DAMAGE_CLASSES
            self.thresholds = dict(DEFAULT_THRESHOLDS)
            self._input_size = INPUT_SIZE[0]

        self.device = torch.device(device or self._resolve_device(torch))

        model = models.efficientnet_b3(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = torch.nn.Sequential(
            torch.nn.Dropout(0.5),
            torch.nn.Linear(in_features, CLASSIFIER_HIDDEN),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.25),
            torch.nn.Linear(CLASSIFIER_HIDDEN, len(self.classes)),
        )
        model.load_state_dict(state_dict)
        model.eval()
        self.model = model.to(self.device)

        self.transform = transforms.Compose(
            [
                transforms.Resize((self._input_size, self._input_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )

        # File mtime is a cheap, stable version marker for provenance in reports.
        self.model_version = str(int(self.weights_path.stat().st_mtime))

    @staticmethod
    def _resolve_device(torch) -> str:
        """Pick an inference device.

        `auto` never selects MPS: requests are served from a thread pool and
        MPS has not been dependably thread-safe. Ask for it explicitly with
        INFERENCE_DEVICE=mps on a single-user machine where it is much faster.
        """
        from app.core.config import settings

        requested = settings.INFERENCE_DEVICE.strip().lower()
        if requested != "auto":
            return requested
        return "cuda" if torch.cuda.is_available() else "cpu"

    def predict(self, image_bytes: bytes) -> PredictionResult:
        torch = self._torch
        started = time.perf_counter()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probabilities = torch.sigmoid(logits)[0].cpu().tolist()

        findings = [
            DamageFinding(
                class_name=class_name,
                confidence=round(float(probability), 4),
                threshold=float(self.thresholds.get(class_name, 0.5)),
            )
            for class_name, probability in zip(self.classes, probabilities)
        ]

        return PredictionResult(
            findings=findings,
            model_name=self.model_name,
            model_version=self.model_version,
            backend=self.name,
            inference_ms=(time.perf_counter() - started) * 1000,
            classes=tuple(self.classes),
        )

    def describe(self) -> dict:
        info = super().describe()
        info.update(
            {
                "classes": list(self.classes),
                "thresholds": self.thresholds,
                "device": str(self.device),
                "weights_path": str(self.weights_path),
                "input_size": self._input_size,
            }
        )
        return info
