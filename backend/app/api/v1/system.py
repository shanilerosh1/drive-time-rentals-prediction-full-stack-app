"""Health, model provenance and the damage taxonomy the client renders from."""
import json

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser
from app.core.config import settings
from app.core.damage_classes import (
    CLASS_COLOURS,
    CLASS_LABELS,
    CLASS_TEST_METRICS,
    DAMAGE_CLASSES,
    DEFAULT_THRESHOLDS,
)
from app.ml import describe_predictor, get_predictor, reset_predictor

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    return {"status": "ok", "version": settings.VERSION}


@router.get("/model", summary="Which model is answering, and how well it scores")
def model_info() -> dict:
    info = describe_predictor()
    info["test_metrics"] = CLASS_TEST_METRICS
    if not info.get("is_real"):
        info["warning"] = (
            "No trained weights are loaded. Predictions come from a deterministic "
            "placeholder and must not be used as evidence."
        )
    return info


@router.post("/model/reload", summary="Re-detect weights without restarting (admin)")
def reload_model(_: AdminUser) -> dict:
    reset_predictor()
    get_predictor()
    return describe_predictor()


@router.get(
    "/model/evaluation",
    summary="Measured performance on the held-out test split",
)
def model_evaluation() -> dict:
    """Serve the report written by `training/evaluate.py`.

    These are numbers measured by running the *deployed* predictor over images
    it never trained on - not figures transcribed from a notebook. If no report
    has been generated, say so plainly rather than inventing a placeholder.
    """
    path = settings.CLASSIFIER_WEIGHTS.parent / "evaluation.json"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No evaluation report yet. Generate one with: "
                "python training/evaluate.py --data-root data/CarDD_COCO"
            ),
        )
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"The evaluation report is not readable JSON: {exc}",
        ) from exc

    # The examples list is large and only needed by the drill-down view.
    report["example_count"] = len(report.get("examples", []))
    return report


@router.get("/damage-classes", summary="Taxonomy, thresholds and display metadata")
def damage_classes() -> dict:
    return {
        "classes": [
            {
                "name": name,
                "label": CLASS_LABELS[name],
                "colour": CLASS_COLOURS[name],
                "default_threshold": DEFAULT_THRESHOLDS[name],
                "test_metrics": CLASS_TEST_METRICS.get(name, {}),
            }
            for name in DAMAGE_CLASSES
        ]
    }
