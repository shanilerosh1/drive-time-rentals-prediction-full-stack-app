"""Selects and caches the process-wide inference backend.

`PREDICTOR_BACKEND=auto` prefers a real model and degrades to the mock, so a
clean checkout runs end-to-end and gains real inference the moment weights are
dropped into `backend/models/`. An explicit setting never silently degrades -
if you ask for `classifier` and it cannot load, that is an error worth seeing.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import settings
from app.ml.base import Predictor
from app.ml.mock import MockPredictor

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_predictor: Predictor | None = None
_load_error: str | None = None


def _build(backend: str) -> Predictor:
    if backend == "mock":
        return MockPredictor()

    if backend == "detector":
        from app.ml.detector import YoloDetector

        return YoloDetector(settings.DETECTOR_WEIGHTS)

    if backend == "classifier":
        from app.ml.classifier import EfficientNetClassifier

        return EfficientNetClassifier(settings.CLASSIFIER_WEIGHTS)

    raise ValueError(f"Unknown PREDICTOR_BACKEND: {backend!r}")


def _build_auto() -> Predictor:
    """Detector, then classifier, then mock - first one that loads wins."""
    global _load_error

    for backend, weights in (
        ("detector", settings.DETECTOR_WEIGHTS),
        ("classifier", settings.CLASSIFIER_WEIGHTS),
    ):
        if not weights.exists():
            continue
        try:
            predictor = _build(backend)
            logger.info("Inference backend: %s (%s)", backend, weights)
            return predictor
        except Exception as exc:  # noqa: BLE001 - any load failure falls through
            _load_error = f"{backend}: {exc}"
            logger.warning("Could not load %s backend from %s: %s", backend, weights, exc)

    logger.warning(
        "No usable model weights found - falling back to the deterministic mock "
        "predictor. Its output is NOT evidence."
    )
    return MockPredictor()


def get_predictor() -> Predictor:
    global _predictor
    if _predictor is None:
        with _lock:
            if _predictor is None:
                backend = settings.PREDICTOR_BACKEND.strip().lower()
                _predictor = _build_auto() if backend == "auto" else _build(backend)
    return _predictor


def reset_predictor() -> None:
    """Drop the cached backend. Used by tests and by the reload endpoint."""
    global _predictor, _load_error
    with _lock:
        _predictor = None
        _load_error = None


def describe_predictor() -> dict:
    predictor = get_predictor()
    info = predictor.describe()
    info["configured_backend"] = settings.PREDICTOR_BACKEND
    info["classifier_weights_present"] = settings.CLASSIFIER_WEIGHTS.exists()
    info["detector_weights_present"] = settings.DETECTOR_WEIGHTS.exists()
    if _load_error:
        info["last_load_error"] = _load_error
    return info
