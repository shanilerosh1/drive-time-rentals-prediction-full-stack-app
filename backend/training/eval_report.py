"""PDF verification report for a trained model.

Produced by `training/evaluate.py --report`. It exists so the claim "the model
identifies damage correctly" can be handed to a supervisor as evidence rather
than asserted: measured metrics on a held-out split, the confusion counts
behind them, and a page of individual predictions set against the dataset's
own annotations - including the failures.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.damage_classes import CLASS_LABELS, DAMAGE_CLASSES

BRAND = colors.HexColor("#1F3A5F")
BRAND_PALE = colors.HexColor("#EEF3FA")
MUTED = colors.HexColor("#5A6472")
RULE = colors.HexColor("#D8DEE6")
OK_BG = colors.HexColor("#E7F6EF")
BAD_BG = colors.HexColor("#FDECEA")

CONTENT_WIDTH = A4[0] - 46 * mm


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=17, textColor=BRAND,
                                spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=9, textColor=MUTED,
                              spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, textColor=BRAND,
                             spaceBefore=13, spaceAfter=6),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9, leading=13),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8, leading=10.5),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=7.4, leading=10,
                                textColor=MUTED),
        "cap": ParagraphStyle("cap", parent=base["Normal"], fontSize=6.6, leading=8.6,
                              alignment=TA_CENTER),
    }


S = _styles()


def _metric_cards(metrics: dict) -> Table:
    cards = [
        ("Macro F1", f"{metrics['macro']['f1']:.3f}", "mean over six classes"),
        ("Macro ROC-AUC", f"{metrics['macro']['roc_auc']:.3f}", "ranking quality"),
        ("Any-damage acc.", f"{metrics['any_damage_accuracy'] * 100:.1f}%", "damaged vs clean"),
        ("Exact match", f"{metrics['exact_match_ratio'] * 100:.1f}%", "all six correct"),
    ]
    row = []
    for label, value, note in cards:
        inner = Table(
            [[Paragraph(f"<b>{label}</b>", S["small"])],
             [Paragraph(f"<font size=15 color='#1F3A5F'><b>{value}</b></font>", S["cell"])],
             [Paragraph(note, S["small"])]],
            colWidths=[CONTENT_WIDTH / 4 - 5],
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_PALE),
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        row.append(inner)

    outer = Table([row], colWidths=[CONTENT_WIDTH / 4] * 4)
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
    return outer


def _per_class_table(metrics: dict) -> Table:
    header = ["Class", "Thresh", "Support", "Precision", "Recall", "F1", "AP", "AUC", "TP/FP/FN"]
    data = [[Paragraph(f"<b>{h}</b>", S["cell"]) for h in header]]

    for name in DAMAGE_CLASSES:
        c = metrics["per_class"].get(name)
        if not c:
            continue
        data.append([
            Paragraph(CLASS_LABELS.get(name, name), S["cell"]),
            f"{metrics.get('thresholds', {}).get(name, 0.5):.3f}",
            str(c["support"]),
            f"{c['precision']:.3f}",
            f"{c['recall']:.3f}",
            f"{c['f1']:.3f}",
            f"{c.get('average_precision', 0):.3f}",
            f"{c.get('roc_auc', 0):.3f}",
            f"{c['tp']}/{c['fp']}/{c['fn']}",
        ])

    m = metrics["macro"]
    data.append([
        Paragraph("<b>Macro avg</b>", S["cell"]), "", "",
        f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}",
        f"{m['average_precision']:.3f}", f"{m['roc_auc']:.3f}", "",
    ])

    widths = [30, 16, 18, 21, 18, 16, 16, 17, 24]
    total = sum(widths)
    table = Table(data, colWidths=[w / total * CONTENT_WIDTH for w in widths], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_PALE),
        ("GRID", (0, 0), (-1, -1), 0.3, RULE),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, len(data) - 1), (-1, len(data) - 1), 1.1, BRAND),
        ("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#F6F8FB")),
    ]
    table.setStyle(TableStyle(style))
    return table


def _example_cell(example: dict, image_dir: Path) -> Table:
    """One prediction: the photograph, the annotation, and what the model said."""
    path = image_dir / example["file_name"]
    flow = []
    if path.exists():
        try:
            from PIL import Image as PILImage

            with PILImage.open(path) as probe:
                width, height = probe.size
            display_w = CONTENT_WIDTH / 3 - 12
            display_h = min(display_w * height / width, 42 * mm)
            flow.append(RLImage(str(path), width=display_w, height=display_h))
        except Exception:  # noqa: BLE001 - a missing thumbnail is not fatal
            pass

    truth = ", ".join(CLASS_LABELS.get(c, c) for c in example["truth"]) or "clean"
    pred = ", ".join(CLASS_LABELS.get(c, c) for c in example["predicted"]) or "clean"
    mark = "MATCH" if example["correct"] else "DIFFERS"

    flow += [
        Spacer(1, 3),
        Paragraph(f"<b>{mark}</b> &nbsp; {example['file_name']}", S["cap"]),
        Paragraph(f"annotated: {truth}", S["cap"]),
        Paragraph(f"predicted: {pred}", S["cap"]),
    ]

    cell = Table([[flow]], colWidths=[CONTENT_WIDTH / 3 - 6])
    cell.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), OK_BG if example["correct"] else BAD_BG),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return cell


def _example_grid(examples: list[dict], image_dir: Path, columns: int = 3) -> list:
    rows = []
    for start in range(0, len(examples), columns):
        chunk = examples[start : start + columns]
        cells = [_example_cell(e, image_dir) for e in chunk]
        cells += [""] * (columns - len(cells))
        grid = Table([cells], colWidths=[CONTENT_WIDTH / columns] * columns)
        grid.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        rows.append(KeepTogether(grid))
    return rows


def build_evaluation_report(
    metrics: dict, examples: list[dict], image_dir: Path, out_path: Path
) -> None:
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=23 * mm, rightMargin=23 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
        title="Model verification report",
        author="DriveTime Vehicle Damage Inspection System",
    )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story: list = [
        Paragraph("Model Verification Report", S["title"]),
        Paragraph(
            f"{metrics['model_name']} ({metrics['backend']}) &middot; "
            f"held-out {metrics['split']} split, {metrics['images']} images &middot; "
            f"generated {generated}",
            S["sub"],
        ),
        Paragraph(
            "Every figure below was produced by running the <b>deployed</b> predictor - the "
            "same object the API calls to answer a request - over CarDD images that were not "
            "used for training or validation. Ground truth comes from the dataset's own "
            "annotations.",
            S["body"],
        ),
        Spacer(1, 12),
        _metric_cards(metrics),
        Spacer(1, 14),
        Paragraph("Per-class results", S["h2"]),
        _per_class_table(metrics),
        Spacer(1, 8),
        Paragraph(
            "<b>Precision</b> is how often a reported detection is genuine; low precision means "
            "the system would accuse customers of damage that is not there. <b>Recall</b> is how "
            "much of the real damage is caught; low recall means missed damage. Each class is "
            "reported positive only above its own F1-optimised threshold, shown in the second "
            "column - a single flat 0.5 cut-off measurably underperforms on the rarer classes. "
            "<b>TP/FP/FN</b> are the raw counts behind those rates.",
            S["small"],
        ),
        Spacer(1, 6),
        Paragraph(
            f"Inference latency: {metrics['latency_ms']['mean']:.0f} ms mean, "
            f"{metrics['latency_ms']['p50']:.0f} ms median, "
            f"{metrics['latency_ms']['p95']:.0f} ms at the 95th percentile, "
            f"measured over the same {metrics['images']} images.",
            S["body"],
        ),
    ]

    wrong = [e for e in examples if not e["correct"]]
    right = [e for e in examples if e["correct"]]

    story += [
        PageBreak(),
        Paragraph("Individual predictions", S["h2"]),
        Paragraph(
            f"{len(right)} of {len(examples)} recorded examples matched the annotation on all six "
            "classes simultaneously. Both the matches and the failures are shown; a report that "
            "only showed successes would not be evidence of anything.",
            S["body"],
        ),
        Spacer(1, 10),
        Paragraph("Correct predictions", S["h2"]),
    ]
    story += _example_grid(right[:9], image_dir)

    if wrong:
        story += [
            Spacer(1, 6),
            Paragraph("Disagreements with the annotation", S["h2"]),
            Paragraph(
                "A row counts as differing if any of the six classes disagrees, so many of these "
                "are right about five classes and wrong about one. Inspect these before trusting "
                "the model on a class it is weak at.",
                S["small"],
            ),
            Spacer(1, 6),
        ]
        story += _example_grid(wrong[:12], image_dir)

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(23 * mm, 11 * mm,
                          "Model verification - measured on held-out data, not training data.")
        canvas.drawRightString(A4[0] - 23 * mm, 11 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
