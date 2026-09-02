"""Damage taxonomy and decision thresholds.

The six classes are the CarDD categories (Wang et al., 2023) used by the
classifier in `car-damage-classification.ipynb`. The thresholds are the
per-class F1-optimal values found by the notebook's precision-recall sweep on
the held-out test split; they are the fallback used whenever a checkpoint does
not carry its own `thresholds` dict.
"""

DAMAGE_CLASSES: tuple[str, ...] = (
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "lamp_broken",
    "tire_flat",
)

DEFAULT_THRESHOLDS: dict[str, float] = {
    "dent": 0.5398045182228088,
    "scratch": 0.6064741015434265,
    "crack": 0.6602650284767151,
    "glass_shatter": 0.7183960080146790,
    "lamp_broken": 0.7474693655967712,
    "tire_flat": 0.8488282561302185,
}

# Human-facing labels and the display colours reused by the Angular dashboard.
CLASS_LABELS: dict[str, str] = {
    "dent": "Dent",
    "scratch": "Scratch",
    "crack": "Crack",
    "glass_shatter": "Glass shatter",
    "lamp_broken": "Lamp broken",
    "tire_flat": "Tyre flat",
}

CLASS_COLOURS: dict[str, str] = {
    "dent": "#4C72B0",
    "scratch": "#DD8452",
    "crack": "#55A868",
    "glass_shatter": "#C44E52",
    "lamp_broken": "#8172B2",
    "tire_flat": "#937860",
}

# Per-class test-set metrics from the notebook, surfaced in the UI so a user
# reading a prediction can see how much weight that class deserves.
CLASS_TEST_METRICS: dict[str, dict[str, float]] = {
    "dent": {"roc_auc": 0.8523, "average_precision": 0.8200, "f1": 0.7514},
    "scratch": {"roc_auc": 0.8465, "average_precision": 0.8172, "f1": 0.7913},
    "crack": {"roc_auc": 0.8098, "average_precision": 0.3748, "f1": 0.4655},
    "glass_shatter": {"roc_auc": 0.9904, "average_precision": 0.9688, "f1": 0.9000},
    "lamp_broken": {"roc_auc": 0.8968, "average_precision": 0.6206, "f1": 0.6569},
    "tire_flat": {"roc_auc": 0.9814, "average_precision": 0.9056, "f1": 0.8214},
}


def severity_hint(confidence: float, threshold: float) -> str:
    """Coarse severity band derived from how far a score clears its threshold.

    This is a presentation heuristic, not a model output: the classifier is
    trained for presence/absence only and has no severity supervision. It is
    labelled as a hint everywhere it is shown so a report reader is not misled.
    """
    if confidence < threshold:
        return "none"
    headroom = (confidence - threshold) / max(1e-6, 1.0 - threshold)
    if headroom >= 0.60:
        return "severe"
    if headroom >= 0.25:
        return "moderate"
    return "minor"
