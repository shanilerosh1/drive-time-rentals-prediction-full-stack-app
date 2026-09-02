"""Deterministic stand-in used until trained weights are available.

Scores are derived from a hash of the image bytes, so the same photograph
always yields the same result. That keeps the dashboard, the comparison view
and the test-suite reproducible without a GPU or a checkpoint - but the output
carries no visual meaning whatsoever, and `is_real` is False so every surface
that displays it can say so.
"""
from __future__ import annotations

import hashlib
import struct
import time

from app.core.damage_classes import DAMAGE_CLASSES, DEFAULT_THRESHOLDS
from app.ml.base import DamageFinding, Predictor, PredictionResult


class MockPredictor(Predictor):
    name = "mock"
    model_name = "deterministic-stub"
    model_version = "0"

    @property
    def is_real(self) -> bool:
        return False

    def predict(self, image_bytes: bytes) -> PredictionResult:
        started = time.perf_counter()
        digest = hashlib.sha256(image_bytes).digest()

        findings: list[DamageFinding] = []
        for index, class_name in enumerate(DAMAGE_CLASSES):
            # Four fresh bytes per class, folded into [0, 1).
            chunk = digest[index * 4 : index * 4 + 4]
            (raw,) = struct.unpack(">I", chunk)
            score = raw / 0xFFFFFFFF

            # Squash toward the middle so a typical image trips one or two
            # classes rather than all six - closer to a realistic damage mix.
            score = 0.25 + score * 0.62
            findings.append(
                DamageFinding(
                    class_name=class_name,
                    confidence=round(score, 4),
                    threshold=DEFAULT_THRESHOLDS[class_name],
                )
            )

        return PredictionResult(
            findings=findings,
            model_name=self.model_name,
            model_version=self.model_version,
            backend=self.name,
            inference_ms=(time.perf_counter() - started) * 1000,
        )
