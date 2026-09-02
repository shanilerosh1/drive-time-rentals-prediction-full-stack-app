"""Verify the deployed model against the held-out CarDD test split.

This is the answer to "how do I know the system actually identifies damage?".

Two properties make it a real verification rather than a self-report:

1. It loads the model **through `app.ml.get_predictor()`** - the exact code path
   the API uses to answer a request. If the checkpoint, the preprocessing or the
   thresholds were wrong in the running service, they are wrong here too.
2. It scores the **test split only** - images the model never saw in training or
   validation, with ground-truth labels straight from the CarDD annotations.

    python training/evaluate.py --data-root data/CarDD_COCO
    python training/evaluate.py --data-root data/CarDD_COCO --report

Writes `models/evaluation.json`, which the API serves at
`GET /api/v1/model/evaluation` so the dashboard can display measured
performance rather than numbers copied from a notebook.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.damage_classes import DAMAGE_CLASSES  # noqa: E402

COCO_TO_CLASS = {
    "dent": "dent",
    "scratch": "scratch",
    "crack": "crack",
    "glass shatter": "glass_shatter",
    "lamp broken": "lamp_broken",
    "tire flat": "tire_flat",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--limit", type=int, default=0, help="Score only the first N images")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "evaluation.json",
    )
    parser.add_argument("--report", action="store_true", help="Also write a PDF report")
    parser.add_argument(
        "--negatives",
        type=Path,
        default=None,
        help="Directory of undamaged car photographs to include in the test set "
             "(default: <data-root>/negatives). Without these, 'any-damage accuracy' "
             "cannot detect false alarms on clean cars.",
    )
    return parser.parse_args()


def load_ground_truth(data_root: Path, split: str) -> list[dict]:
    with open(data_root / "annotations" / f"instances_{split}2017.json") as handle:
        data = json.load(handle)

    categories = {c["id"]: c["name"] for c in data["categories"]}
    files = {img["id"]: img["file_name"] for img in data["images"]}

    labels: dict[int, set[str]] = defaultdict(set)
    for annotation in data["annotations"]:
        mapped = COCO_TO_CLASS.get(categories[annotation["category_id"]])
        if mapped:
            labels[annotation["image_id"]].add(mapped)

    return [
        {"file_name": files[image_id], "labels": sorted(classes)}
        for image_id, classes in sorted(labels.items())
    ]


def summarise(y_true, y_pred, y_score) -> dict:
    """Per-class and aggregate metrics, computed without sklearn's help for the
    counts so the confusion numbers are inspectable."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    per_class = {}
    for index, name in enumerate(DAMAGE_CLASSES):
        truth = [row[index] for row in y_true]
        pred = [row[index] for row in y_pred]
        score = [row[index] for row in y_score]

        tp = sum(1 for t, p in zip(truth, pred) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(truth, pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(truth, pred) if t == 1 and p == 0)
        tn = sum(1 for t, p in zip(truth, pred) if t == 0 and p == 0)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

        entry = {
            "support": tp + fn,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
        # AUC is undefined when a class is entirely absent or entirely present.
        if 0 < sum(truth) < len(truth):
            entry["roc_auc"] = round(float(roc_auc_score(truth, score)), 4)
            entry["average_precision"] = round(float(average_precision_score(truth, score)), 4)
        per_class[name] = entry

    n = len(DAMAGE_CLASSES)
    macro = {
        key: round(sum(per_class[c].get(key, 0.0) for c in DAMAGE_CLASSES) / n, 4)
        for key in ("precision", "recall", "f1", "roc_auc", "average_precision")
    }

    total_tp = sum(per_class[c]["tp"] for c in DAMAGE_CLASSES)
    total_fp = sum(per_class[c]["fp"] for c in DAMAGE_CLASSES)
    total_fn = sum(per_class[c]["fn"] for c in DAMAGE_CLASSES)
    micro_p = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    micro_r = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if micro_p + micro_r else 0.0

    exact = sum(1 for t, p in zip(y_true, y_pred) if t == p) / max(1, len(y_true))
    # "Any damage" is the operationally interesting question at the image level.
    any_true = [1 if any(row) else 0 for row in y_true]
    any_pred = [1 if any(row) else 0 for row in y_pred]
    any_correct = sum(1 for t, p in zip(any_true, any_pred) if t == p) / max(1, len(any_true))

    return {
        "per_class": per_class,
        "macro": macro,
        "micro": {
            "precision": round(micro_p, 4),
            "recall": round(micro_r, 4),
            "f1": round(micro_f1, 4),
        },
        "exact_match_ratio": round(exact, 4),
        "any_damage_accuracy": round(any_correct, 4),
    }


def main() -> int:
    args = parse_args()

    from app.ml import get_predictor

    predictor = get_predictor()
    print(f"Backend under test : {predictor.name} ({predictor.model_name})")
    if not predictor.is_real:
        print(
            "\nERROR: the mock predictor is loaded, so there is nothing to verify.\n"
            "Put trained weights in backend/models/ (or set PREDICTOR_BACKEND) and retry.",
            file=sys.stderr,
        )
        return 2

    rows = load_ground_truth(args.data_root, args.split)
    image_dir = args.data_root / f"{args.split}2017"
    for row in rows:
        row["path"] = image_dir / row["file_name"]
    available = [r for r in rows if r["path"].exists()]
    if len(available) != len(rows):
        print(f"Note: {len(available)}/{len(rows)} images present on disk; scoring those.")
    rows = available

    # Hold back the same slice of undamaged photographs the trainer held back,
    # so the false-alarm rate is measured on cars the model never saw either.
    negatives_dir = args.negatives or (args.data_root / "negatives")
    negatives: list[dict] = []
    if negatives_dir.is_dir():
        clean = sorted(negatives_dir.glob("*.jpg"))
        held_back = clean[int(len(clean) * 0.90):]  # matches split_negatives()
        negatives = [{"file_name": p.name, "path": p, "labels": []} for p in held_back]
        rows = rows + negatives
        print(f"Undamaged        : {len(negatives)} clean cars included in the test set")
    else:
        print(
            "Undamaged        : none found - 'any-damage accuracy' below measures only "
            "whether damage is FOUND when present.\n"
            "                   It cannot detect false alarms on clean cars.",
            file=sys.stderr,
        )

    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print(f"\nERROR: no images found in {image_dir}.", file=sys.stderr)
        return 1
    print(f"Split              : {args.split} ({len(rows)} images, never trained on)")

    y_true, y_pred, y_score = [], [], []
    thresholds: dict[str, float] = {}
    latencies: list[float] = []
    examples: list[dict] = []

    started = time.perf_counter()
    for position, row in enumerate(rows, start=1):
        raw = row["path"].read_bytes()
        result = predictor.predict(raw)
        latencies.append(result.inference_ms)

        by_class = {f.class_name: f for f in result.findings}
        thresholds = {name: by_class[name].threshold for name in DAMAGE_CLASSES if name in by_class}

        truth = [1 if name in row["labels"] else 0 for name in DAMAGE_CLASSES]
        pred = [1 if by_class[name].is_positive else 0 for name in DAMAGE_CLASSES]
        score = [by_class[name].confidence for name in DAMAGE_CLASSES]

        y_true.append(truth)
        y_pred.append(pred)
        y_score.append(score)

        examples.append({
            "file_name": row["file_name"],
            "truth": row["labels"],
            "predicted": [n for n, p in zip(DAMAGE_CLASSES, pred) if p],
            "scores": {n: round(s, 4) for n, s in zip(DAMAGE_CLASSES, score)},
            "correct": truth == pred,
        })

        if position % 50 == 0 or position == len(rows):
            print(f"  scored {position}/{len(rows)}", end="\r", flush=True)

    elapsed = time.perf_counter() - started
    print()

    metrics = summarise(y_true, y_pred, y_score)

    if negatives:
        clean_offset = len(rows) - len(negatives)
        clean_preds = y_pred[clean_offset:]
        false_alarms = sum(1 for p in clean_preds if any(p))
        metrics["clean_images"] = len(clean_preds)
        metrics["false_alarms"] = false_alarms
        metrics["false_alarm_rate"] = round(false_alarms / max(1, len(clean_preds)), 4)
        metrics["clean_correct_rate"] = round(
            1 - false_alarms / max(1, len(clean_preds)), 4
        )
    latencies.sort()
    metrics.update({
        "split": args.split,
        "images": len(rows),
        "backend": predictor.name,
        "model_name": predictor.model_name,
        "model_version": predictor.model_version,
        "thresholds": {k: round(v, 4) for k, v in thresholds.items()},
        "latency_ms": {
            "mean": round(sum(latencies) / len(latencies), 2),
            "p50": round(latencies[len(latencies) // 2], 2),
            "p95": round(latencies[int(len(latencies) * 0.95)], 2),
        },
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_seconds": round(elapsed, 1),
    })

    # --- console report ---
    print(f"\n{'class':16}{'support':>8}{'precis':>9}{'recall':>8}{'F1':>8}{'AP':>8}{'AUC':>8}")
    print("-" * 65)
    for name in DAMAGE_CLASSES:
        c = metrics["per_class"][name]
        print(
            f"{name:16}{c['support']:>8}{c['precision']:>9.3f}{c['recall']:>8.3f}"
            f"{c['f1']:>8.3f}{c.get('average_precision', 0):>8.3f}{c.get('roc_auc', 0):>8.3f}"
        )
    print("-" * 65)
    m = metrics["macro"]
    print(f"{'MACRO':16}{'':>8}{m['precision']:>9.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}"
          f"{m['average_precision']:>8.3f}{m['roc_auc']:>8.3f}")
    mi = metrics["micro"]
    print(f"{'MICRO':16}{'':>8}{mi['precision']:>9.3f}{mi['recall']:>8.3f}{mi['f1']:>8.3f}")
    print(f"\nExact-match ratio (all six classes right): {metrics['exact_match_ratio']:.3f}")
    if negatives:
        print(f"Damaged vs clean, overall accuracy       : {metrics['any_damage_accuracy']:.3f}")
        print(
            f"False alarms on clean cars               : "
            f"{metrics['false_alarms']}/{metrics['clean_images']} "
            f"({metrics['false_alarm_rate'] * 100:.1f}%)"
        )
    else:
        print(
            f"Damage found when present (recall only)  : "
            f"{metrics['any_damage_accuracy']:.3f}   <-- no clean cars in this test set,"
        )
        print("                                                 so false alarms are NOT measured")
    print(f"Latency  mean {metrics['latency_ms']['mean']:.0f} ms   "
          f"p95 {metrics['latency_ms']['p95']:.0f} ms")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(metrics)
    payload["examples"] = examples[:200]
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {args.out}")
    print("The API serves this at GET /api/v1/model/evaluation")

    if args.report:
        from training.eval_report import build_evaluation_report

        pdf_path = args.out.with_suffix(".pdf")
        build_evaluation_report(metrics, examples, image_dir, pdf_path)
        print(f"Wrote {pdf_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
