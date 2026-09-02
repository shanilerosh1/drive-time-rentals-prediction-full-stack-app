"""Structured PDF inspection reports.

The dissertation's explainability position (Section 2.7, after Arrieta et al.,
2020) is that annotated findings with class labels and confidence scores in a
structured document are the proportionate form of explanation for a
non-technical rental-operations audience. This module is that output: findings,
confidences, thresholds, the model that produced them, and the SHA-256 of each
photograph so the record can be tied back to the evidence.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
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

from app.core.damage_classes import CLASS_LABELS, CLASS_TEST_METRICS
from app.models import Inspection
from app.models.enums import DamageOutcome
from app.services import storage
from app.services.analysis import positive_classes

BRAND = colors.HexColor("#1F3A5F")
MUTED = colors.HexColor("#5A6472")
WARN_BG = colors.HexColor("#FFF4E5")
WARN_BORDER = colors.HexColor("#E08A00")

OUTCOME_LABELS = {
    DamageOutcome.NEW: "NEW - arose during this rental",
    DamageOutcome.PRE_EXISTING: "Pre-existing at handover",
    DamageOutcome.RESOLVED: "Present at handover, not detected on return",
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=17, textColor=BRAND, spaceAfter=2
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontSize=9.5, textColor=MUTED, spaceAfter=10
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=12, textColor=BRAND, spaceBefore=12,
            spaceAfter=5,
        ),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9, leading=12.5),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=7.5, textColor=MUTED, leading=10
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"], fontSize=8.5, leading=11, alignment=TA_LEFT
        ),
        "warn": ParagraphStyle(
            "warn", parent=base["Normal"], fontSize=8.5, leading=11.5,
            textColor=colors.HexColor("#7A4A00"),
        ),
    }


def _fmt(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _kv_table(rows: list[tuple[str, str]], styles) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", styles["cell"]), Paragraph(v, styles["cell"])] for k, v in rows]
    table = Table(data, colWidths=[42 * mm, 118 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#E3E6EA")),
            ]
        )
    )
    return table


def _mock_warning(styles) -> Table:
    text = (
        "<b>Not evidential.</b> These findings were produced by the deterministic "
        "placeholder predictor, which does not analyse image content. This report is a "
        "format and workflow demonstration only. Install trained model weights to "
        "produce a report that can support a damage claim."
    )
    table = Table([[Paragraph(text, styles["warn"])]], colWidths=[160 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
                ("BOX", (0, 0), (-1, -1), 0.8, WARN_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _findings_table(inspection: Inspection, styles) -> Table:
    aggregate = positive_classes(inspection)
    header = ["Damage class", "Max confidence", "Severity (hint)", "Evidence images", "Class F1"]
    data = [[Paragraph(f"<b>{h}</b>", styles["cell"]) for h in header]]

    if not aggregate:
        data.append([Paragraph("No damage detected above threshold.", styles["cell"]), "", "", "", ""])
    else:
        for class_name, row in sorted(
            aggregate.items(), key=lambda kv: kv[1]["max_confidence"], reverse=True
        ):
            metrics = CLASS_TEST_METRICS.get(class_name, {})
            data.append(
                [
                    Paragraph(CLASS_LABELS.get(class_name, class_name), styles["cell"]),
                    f"{row['max_confidence'] * 100:.1f}%",
                    row["severity_hint"].title(),
                    ", ".join(f"#{i}" for i in row["image_ids"]) or "-",
                    f"{metrics.get('f1', 0):.2f}" if metrics else "-",
                ]
            )

    table = Table(data, colWidths=[42 * mm, 28 * mm, 28 * mm, 40 * mm, 22 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F7")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DEE6")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _image_block(inspection: Inspection, image, styles) -> KeepTogether:
    flowables = [
        Paragraph(
            f"<b>Image #{image.id}</b> &nbsp; {image.capture_angle.value.replace('_', ' ').title()}"
            f" &nbsp;&middot;&nbsp; {image.original_filename}",
            styles["body"],
        ),
        Spacer(1, 3),
    ]

    thumb_path = storage.image_path(inspection.id, image.thumbnail_name or image.stored_name)
    if thumb_path.exists():
        display_w = 78 * mm
        display_h = display_w * (image.height / image.width) if image.width else 55 * mm
        display_h = min(display_h, 62 * mm)
        flowables.append(RLImage(str(thumb_path), width=display_w, height=display_h))
        flowables.append(Spacer(1, 3))

    positives = [d for d in image.detections if d.is_positive]
    if positives:
        lines = " &nbsp;|&nbsp; ".join(
            f"{CLASS_LABELS.get(d.class_name, d.class_name)} "
            f"{d.confidence * 100:.1f}% (threshold {d.threshold * 100:.0f}%)"
            for d in sorted(positives, key=lambda d: d.confidence, reverse=True)
        )
    else:
        lines = "No damage above threshold."
    flowables.append(Paragraph(lines, styles["small"]))
    flowables.append(
        Paragraph(
            f"SHA-256: {image.sha256} &nbsp;&middot;&nbsp; {image.width}&times;{image.height} px "
            f"&nbsp;&middot;&nbsp; model: {image.model_name or '-'} "
            f"({image.predictor_backend or '-'}) "
            f"&nbsp;&middot;&nbsp; {image.inference_ms or 0:.0f} ms",
            styles["small"],
        )
    )
    flowables.append(Spacer(1, 9))
    return KeepTogether(flowables)


def build_inspection_report(inspection: Inspection) -> bytes:
    """Render a single-inspection report."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Inspection {inspection.id} - {inspection.vehicle.registration}",
        author="DriveTime Vehicle Damage Inspection System",
    )

    vehicle = inspection.vehicle
    backends = {i.predictor_backend for i in inspection.images if i.predictor_backend}
    is_mock = "mock" in backends or not backends

    story: list = [
        Paragraph("Vehicle Damage Inspection Report", styles["title"]),
        Paragraph(
            f"{inspection.inspection_type.value.replace('_', '-').title()} inspection "
            f"&middot; Report generated {_fmt(datetime.now(timezone.utc))}",
            styles["subtitle"],
        ),
    ]

    if is_mock:
        story += [_mock_warning(styles), Spacer(1, 10)]

    story += [
        Paragraph("1. Inspection record", styles["h2"]),
        _kv_table(
            [
                ("Inspection ID", f"#{inspection.id}"),
                ("Type", inspection.inspection_type.value.replace("_", "-").title()),
                ("Status", inspection.status.value.title()),
                ("Rental reference", inspection.rental_ref or "-"),
                ("Inspector", f"{inspection.inspector.full_name} ({inspection.inspector.email})"),
                ("Location", inspection.location or "-"),
                ("Started", _fmt(inspection.started_at)),
                ("Completed", _fmt(inspection.completed_at)),
                ("Odometer", f"{inspection.odometer_km:,} km" if inspection.odometer_km else "-"),
            ],
            styles,
        ),
        Paragraph("2. Vehicle", styles["h2"]),
        _kv_table(
            [
                ("Registration", vehicle.registration),
                ("Make / model", f"{vehicle.make} {vehicle.model}"),
                ("Year", str(vehicle.year) if vehicle.year else "-"),
                ("Colour", vehicle.colour or "-"),
                ("Body type", vehicle.body_type or "-"),
            ],
            styles,
        ),
        Paragraph("3. Detected damage", styles["h2"]),
        _findings_table(inspection, styles),
        Spacer(1, 4),
        Paragraph(
            "Confidence is the model's per-class score for the strongest supporting image. "
            "Each class is reported positive only above its own F1-optimised threshold. "
            "Severity is a presentation heuristic derived from how far a score clears its "
            "threshold - the model receives no severity supervision and does not measure "
            "physical damage extent. 'Class F1' is that class's F1 on the held-out test "
            "split, included so a reader can weigh each finding appropriately.",
            styles["small"],
        ),
    ]

    if inspection.notes:
        story += [
            Paragraph("4. Inspector notes", styles["h2"]),
            Paragraph(inspection.notes.replace("\n", "<br/>"), styles["body"]),
        ]

    if inspection.images:
        story += [PageBreak(), Paragraph("Photographic evidence", styles["h2"])]
        story += [_image_block(inspection, image, styles) for image in inspection.images]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def build_comparison_report(comparison: dict) -> bytes:
    """Render a pre/post comparison - the document that supports a dispute."""
    styles = _styles()
    buffer = io.BytesIO()
    vehicle = comparison["vehicle"]
    pre = comparison["pre_inspection"]
    post = comparison["post_inspection"]

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Pre/post comparison - {vehicle.registration}",
        author="DriveTime Vehicle Damage Inspection System",
    )

    story: list = [
        Paragraph("Pre / Post Rental Damage Comparison", styles["title"]),
        Paragraph(
            f"{vehicle.registration} &middot; {vehicle.make} {vehicle.model} &middot; "
            f"Rental ref {comparison['rental_ref'] or '-'} &middot; "
            f"Generated {_fmt(datetime.now(timezone.utc))}",
            styles["subtitle"],
        ),
    ]

    if not comparison["uses_real_model"]:
        story += [_mock_warning(styles), Spacer(1, 10)]

    if comparison.get("note"):
        story += [Paragraph(comparison["note"], styles["body"]), Spacer(1, 8)]

    story += [
        Paragraph("1. Inspections compared", styles["h2"]),
        _kv_table(
            [
                (
                    "Pre-rental",
                    f"#{pre.id} &middot; {_fmt(pre.completed_at or pre.created_at)} &middot; "
                    f"{pre.inspector.full_name}" if pre else "Not recorded",
                ),
                (
                    "Post-rental",
                    f"#{post.id} &middot; {_fmt(post.completed_at or post.created_at)} &middot; "
                    f"{post.inspector.full_name}" if post else "Not recorded",
                ),
                (
                    "Odometer",
                    f"{pre.odometer_km or '-'} km &rarr; {post.odometer_km or '-'} km"
                    if pre and post
                    else "-",
                ),
            ],
            styles,
        ),
        Paragraph("2. Damage delta", styles["h2"]),
    ]

    header = ["Damage class", "Outcome", "At handover", "On return"]
    data = [[Paragraph(f"<b>{h}</b>", styles["cell"]) for h in header]]
    for row in comparison["rows"]:
        data.append(
            [
                Paragraph(CLASS_LABELS.get(row["class_name"], row["class_name"]), styles["cell"]),
                Paragraph(OUTCOME_LABELS[row["outcome"]], styles["cell"]),
                f"{row['pre_confidence'] * 100:.1f}%" if row["pre_confidence"] else "not detected",
                f"{row['post_confidence'] * 100:.1f}%" if row["post_confidence"] else "not detected",
            ]
        )
    if len(data) == 1:
        data.append([Paragraph("No damage detected in either inspection.", styles["cell"]), "", "", ""])

    table = Table(data, colWidths=[36 * mm, 66 * mm, 29 * mm, 29 * mm], repeatRows=1)
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F7")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DEE6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for index, row in enumerate(comparison["rows"], start=1):
        if row["outcome"] == DamageOutcome.NEW:
            style_commands.append(
                ("BACKGROUND", (0, index), (-1, index), colors.HexColor("#FDECEC"))
            )
    table.setStyle(TableStyle(style_commands))

    story += [
        table,
        Spacer(1, 8),
        Paragraph(
            f"<b>New damage this rental:</b> "
            f"{', '.join(CLASS_LABELS.get(c, c) for c in comparison['new_damage_classes']) or 'none'}<br/>"
            f"<b>Pre-existing:</b> "
            f"{', '.join(CLASS_LABELS.get(c, c) for c in comparison['pre_existing_classes']) or 'none'}",
            styles["body"],
        ),
        Spacer(1, 6),
        Paragraph(
            "A class is reported as new only where it was below threshold across every "
            "pre-rental photograph and above threshold in at least one post-rental "
            "photograph. Absence of a detection is not proof of absence of damage: "
            "recall is bounded by the model's per-class performance and by whether the "
            "affected panel was photographed.",
            styles["small"],
        ),
    ]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        25 * mm, 11 * mm,
        "Generated by the DriveTime automated damage inspection prototype - "
        "computer-vision assisted, subject to human review.",
    )
    canvas.drawRightString(A4[0] - 25 * mm, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()
