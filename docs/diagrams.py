"""Vector diagrams for the project documentation.

Drawn with ReportLab's shapes rather than exported from a drawing tool, so the
figures are reproducible, version-controlled alongside the text they describe,
and cannot drift out of sync with a binary nobody can edit. Each builder
returns a `Drawing` that can be placed straight into a platypus story, and
`export_figures()` writes standalone PNG and PDF copies for use in the
dissertation.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.graphics.shapes import Drawing, Group, Line, Polygon, Rect, String
from reportlab.lib import colors

# --- palette (kept local so this module stands alone) ---------------------
BRAND = colors.HexColor("#1F3A5F")
BRAND_MID = colors.HexColor("#2F5B91")
BRAND_SOFT = colors.HexColor("#DCE6F3")
BRAND_PALE = colors.HexColor("#EEF3FA")
INK = colors.HexColor("#111826")
MUTED = colors.HexColor("#5A6472")
RULE = colors.HexColor("#C6CFDC")
WHITE = colors.white

ACCENT_STORE = colors.HexColor("#167A54")
ACCENT_STORE_BG = colors.HexColor("#E7F6EF")
ACCENT_ML = colors.HexColor("#A4630A")
ACCENT_ML_BG = colors.HexColor("#FDF3E3")
ACCENT_ACTIVE = colors.HexColor("#B3261E")
ACCENT_ACTIVE_BG = colors.HexColor("#FDECEA")

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"


# --- primitives -----------------------------------------------------------
def box(g, x, y, w, h, *, fill=WHITE, stroke=RULE, width=0.7, radius=3, dash=None):
    rect = Rect(x, y, w, h, fillColor=fill, strokeColor=stroke, strokeWidth=width)
    rect.rx = rect.ry = radius
    if dash:
        rect.strokeDashArray = dash
    g.add(rect)
    return rect


def text(g, x, y, s, *, size=7, bold=False, colour=INK, anchor="start"):
    g.add(
        String(x, y, s, fontName=FONT_B if bold else FONT, fontSize=size,
               fillColor=colour, textAnchor=anchor)
    )


def centred(g, cx, y, s, **kw):
    text(g, cx, y, s, anchor="middle", **kw)


def labelled_box(g, x, y, w, h, title, subtitle=None, *, fill=WHITE, stroke=RULE,
                 title_size=7.2, sub_size=6.1, title_colour=INK, dash=None):
    """A box with a bold title and an optional muted second line, both centred."""
    box(g, x, y, w, h, fill=fill, stroke=stroke, dash=dash)
    cx = x + w / 2
    if subtitle:
        centred(g, cx, y + h / 2 + 1.4, title, size=title_size, bold=True, colour=title_colour)
        centred(g, cx, y + h / 2 - 6.4, subtitle, size=sub_size, colour=MUTED)
    else:
        centred(g, cx, y + h / 2 - 2.4, title, size=title_size, bold=True, colour=title_colour)


def arrow(g, x1, y1, x2, y2, *, colour=BRAND_MID, width=1.1, head=4.6, dash=None):
    """Straight arrow from (x1,y1) to (x2,y2), head at the destination."""
    import math

    angle = math.atan2(y2 - y1, x2 - x1)
    # Stop the shaft short so it does not poke through the head.
    sx, sy = x2 - head * math.cos(angle), y2 - head * math.sin(angle)
    line = Line(x1, y1, sx, sy, strokeColor=colour, strokeWidth=width)
    if dash:
        line.strokeDashArray = dash
    g.add(line)

    spread = 0.42
    g.add(
        Polygon(
            [
                x2, y2,
                x2 - head * 1.5 * math.cos(angle - spread),
                y2 - head * 1.5 * math.sin(angle - spread),
                x2 - head * 1.5 * math.cos(angle + spread),
                y2 - head * 1.5 * math.sin(angle + spread),
            ],
            fillColor=colour, strokeColor=colour, strokeWidth=0.4,
        )
    )


def double_arrow(g, x1, y1, x2, y2, **kw):
    arrow(g, x1, y1, x2, y2, **kw)
    arrow(g, x2, y2, x1, y1, **kw)


def band_label(g, x, y, s):
    """Small rotated-style tier caption sitting to the left of a band."""
    text(g, x, y, s, size=5.9, bold=True, colour=MUTED)


# =========================================================================
#  Figure 1 - system architecture
# =========================================================================
def architecture_diagram(width: float = 466) -> Drawing:
    W, H = 466, 436
    d = Drawing(W, H)
    g = Group()

    GUTTER = 8          # tier captions live here, left of all content
    LEFT = 50           # every box starts at or right of this
    RIGHT = 452

    # ---------- client tier ----------
    cx0, cw = 96, 300
    box(g, cx0, 374, cw, 50, fill=BRAND_PALE, stroke=BRAND_MID, width=0.9)
    centred(g, cx0 + cw / 2, 410, "Angular 17 single-page dashboard", size=8, bold=True, colour=BRAND)
    centred(g, cx0 + cw / 2, 401.5, "browser  \u00b7  standalone components  \u00b7  lazy routes",
            size=6, colour=MUTED)
    pill_w = (cw - 34) / 3
    for i, label in enumerate(("Routes + guards", "Signal state", "JWT interceptor")):
        px = cx0 + 8.5 + i * (pill_w + 8.5)
        box(g, px, 380, pill_w, 15, fill=WHITE, stroke=BRAND_SOFT)
        centred(g, px + pill_w / 2, 385, label, size=6.1, colour=BRAND)
    band_label(g, GUTTER, 402, "CLIENT")

    # ---------- client <-> API ----------
    double_arrow(g, 246, 374, 246, 348)
    text(g, 256, 364, "JSON over HTTP", size=6.3, bold=True, colour=BRAND)
    text(g, 256, 355.5, "Authorization: Bearer <JWT>", size=6, colour=MUTED)

    # ---------- service tier ----------
    sx0, sw = LEFT, RIGHT - LEFT
    box(g, sx0, 124, sw, 224, fill=WHITE, stroke=BRAND, width=1.1)
    text(g, sx0 + 11, 332, "FastAPI application service  (Python 3.11+)", size=8, bold=True, colour=BRAND)
    text(g, sx0 + 11, 323, "record management and inference in one process", size=6, colour=MUTED)
    band_label(g, GUTTER, 236, "SERVICE")

    inner_x, inner_w = sx0 + 11, sw - 22

    def band(x, y, w, h, caption, cells):
        box(g, x, y, w, h, fill=BRAND_PALE, stroke=BRAND_SOFT)
        text(g, x + 7, y + h - 10.5, caption, size=6.4, bold=True, colour=BRAND)
        n = len(cells)
        gap = 6
        cell_w = (w - 14 - gap * (n - 1)) / n
        for i, label in enumerate(cells):
            px = x + 7 + i * (cell_w + gap)
            box(g, px, y + 6, cell_w, 15.5, fill=WHITE, stroke=BRAND_SOFT)
            centred(g, px + cell_w / 2, y + 11.2, label, size=6, colour=INK)

    band(inner_x, 276, inner_w, 40, "api/v1  \u2014  REST layer, 35 endpoints, OpenAPI schema",
         ["auth \u00b7 users", "vehicles", "inspections \u00b7 images", "comparisons \u00b7 dashboard"])
    band(inner_x, 224, inner_w, 40, "services  \u2014  domain logic",
         ["storage", "analysis", "comparison", "report (PDF)"])
    band(inner_x, 172, inner_w, 40, "models  \u2014  SQLAlchemy ORM",
         ["User", "Vehicle", "Inspection", "InspectionImage", "Detection"])

    # The ML band is inset on the left, leaving a clear channel for the
    # persistence arrow to pass through without crossing any text.
    CHANNEL = 62
    ml_x, ml_w = inner_x + CHANNEL, inner_w - CHANNEL
    box(g, ml_x, 132, ml_w, 30, fill=ACCENT_ML_BG, stroke=ACCENT_ML, dash=(2.4, 2))
    text(g, ml_x + 7, 151.5, "ml  \u2014  Predictor  (abstract base class)", size=6.4, bold=True,
         colour=ACCENT_ML)
    text(g, ml_x + 7, 139.5,
         "predict(image_bytes) -> PredictionResult   \u00b7   all the rest of the app knows about a model",
         size=5.8, colour=MUTED)

    # ---------- downward arrows ----------
    channel_x = inner_x + CHANNEL / 2
    arrow(g, channel_x, 172, channel_x, 108, colour=ACCENT_STORE)   # models -> persistence
    arrow(g, 340, 132, 340, 108, colour=ACCENT_ML)                  # ml -> backends

    # ---------- persistence ----------
    px0, pw = LEFT, 190
    box(g, px0, 20, pw, 88, fill=ACCENT_STORE_BG, stroke=ACCENT_STORE, width=0.9)
    text(g, px0 + 9, 95, "Persistence", size=7.2, bold=True, colour=ACCENT_STORE)
    labelled_box(g, px0 + 9, 58, pw - 18, 28, "SQLite  \u00b7  data/app.db",
                 "PostgreSQL via DATABASE_URL", fill=WHITE, stroke=ACCENT_STORE)
    labelled_box(g, px0 + 9, 26, pw - 18, 28, "Filesystem  \u00b7  storage/",
                 "photographs, thumbnails, SHA-256", fill=WHITE, stroke=ACCENT_STORE)
    band_label(g, GUTTER, 62, "RESOURCES")

    # ---------- inference backends ----------
    bx0, bw = RIGHT - 190, 190
    box(g, bx0, 20, bw, 88, fill=ACCENT_ML_BG, stroke=ACCENT_ML, width=0.9)
    text(g, bx0 + 9, 95, "Inference backends", size=7.2, bold=True, colour=ACCENT_ML)
    text(g, bx0 + 106, 95.4, "first that loads wins", size=5.8, colour=MUTED)

    rows = [
        ("MockPredictor", "no weights \u2014 deterministic stand-in", True),
        ("EfficientNetClassifier", "car_damage_classifier.pth", False),
        ("YoloDetector", "yolov8_damage.pt \u2014 adds bounding boxes", False),
    ]
    for i, (name, note, active) in enumerate(rows):
        top = 86 - i * 22
        box(g, bx0 + 9, top - 19, bw - 18, 19,
            fill=ACCENT_ACTIVE_BG if active else WHITE,
            stroke=ACCENT_ACTIVE if active else RULE)
        text(g, bx0 + 15, top - 8, name, size=6.2, bold=True,
             colour=ACCENT_ACTIVE if active else INK)
        text(g, bx0 + 15, top - 15.5, note, size=5.4, colour=MUTED)

    d.add(g)
    if width and width != W:
        factor = width / W
        d.scale(factor, factor)
        d.width, d.height = W * factor, H * factor
    return d


# =========================================================================
#  Figure 2 - data model
# =========================================================================
def data_model_diagram(width: float = 466) -> Drawing:
    W, H = 466, 214
    d = Drawing(W, H)
    g = Group()

    def entity(x, y, w, title, fields, *, accent=BRAND):
        h = 22 + len(fields) * 9.4
        box(g, x, y - h, w, h, fill=WHITE, stroke=accent, width=0.9)
        box(g, x, y - 16, w, 16, fill=BRAND_PALE, stroke=accent, width=0.9)
        text(g, x + 6, y - 11.4, title, size=6.9, bold=True, colour=accent)
        for i, field in enumerate(fields):
            text(g, x + 6, y - 26 - i * 9.4, field, size=5.7, colour=MUTED)
        return h

    entity(14, 200, 106, "User",
           ["email  \u00b7  full_name", "role: admin / inspector", "hashed_password"])
    entity(14, 110, 106, "Vehicle",
           ["registration  (unique)", "make  \u00b7  model  \u00b7  year", "colour  \u00b7  body_type"])

    entity(152, 176, 132, "Inspection",
           [
               "type: pre_rental / post_rental",
               "rental_ref  \u2190 pairs the two",
               "status  \u00b7  odometer_km",
               "started_at  \u00b7  completed_at",
           ])

    entity(310, 200, 142, "InspectionImage",
           [
               "stored_name  \u00b7  capture_angle",
               "sha256  \u2190 evidentiary link",
               "width \u00b7 height \u00b7 size_bytes",
               "model_name \u00b7 predictor_backend",
               "inference_ms",
           ])
    entity(310, 104, 142, "Detection",
           [
               "class_name  \u00b7  confidence",
               "threshold  \u00b7  is_positive",
               "severity_hint",
               "bbox_x/y/w/h  (nullable)",
           ],
           accent=ACCENT_ML)

    # Relationships. Labels sit clear of every box edge.
    arrow(g, 120, 178, 152, 158, colour=BRAND_MID, width=0.9)
    text(g, 126, 172, "1..n", size=5.5, colour=MUTED)
    arrow(g, 120, 92, 152, 122, colour=BRAND_MID, width=0.9)
    text(g, 126, 104, "1..n", size=5.5, colour=MUTED)
    arrow(g, 284, 160, 310, 168, colour=BRAND_MID, width=0.9)
    text(g, 288, 166, "1..n", size=5.5, colour=MUTED)
    arrow(g, 381, 138, 381, 108, colour=ACCENT_ML, width=0.9)
    text(g, 387, 120, "1..n   (six rows per image)", size=5.5, colour=MUTED)

    box(g, 14, 14, 438, 24, fill=ACCENT_ML_BG, stroke=ACCENT_ML, dash=(2.4, 2))
    text(g, 21, 27,
         "The four bbox columns are null for image-level classification and populated by the YOLOv8 detector.",
         size=5.9, bold=True, colour=ACCENT_ML)
    text(g, 21, 19.5,
         "Same table, same API shape either way \u2014 enabling detection needs no migration and no frontend change.",
         size=5.9, colour=MUTED)

    d.add(g)
    if width and width != W:
        factor = width / W
        d.scale(factor, factor)
        d.width, d.height = W * factor, H * factor
    return d


# =========================================================================
#  Figure 3 - the inspection lifecycle
# =========================================================================
def workflow_diagram(width: float = 466) -> Drawing:
    W, H = 466, 140
    d = Drawing(W, H)
    g = Group()

    steps = [
        ("1", "Open", "pre- or post-rental,\ntagged with a rental ref"),
        ("2", "Upload", "photographs validated,\nhashed, thumbnailed"),
        ("3", "Analyse", "each class scored against\nits own threshold"),
        ("4", "Compare", "pre vs post \u2192\nnew / pre-existing"),
        ("5", "Export", "evidentiary PDF\nfor the rental file"),
    ]
    n = len(steps)
    gap = 12
    bw = (W - 28 - gap * (n - 1)) / n
    y, h = 62, 66

    for i, (num, title, detail) in enumerate(steps):
        x = 14 + i * (bw + gap)
        last = i == n - 1
        accent = ACCENT_STORE if last else BRAND_MID
        box(g, x, y, bw, h, fill=ACCENT_STORE_BG if last else BRAND_PALE,
            stroke=accent, width=0.9)
        badge = Rect(x + bw / 2 - 8, y + h - 19, 16, 14,
                     fillColor=ACCENT_STORE if last else BRAND, strokeColor=None)
        badge.rx = badge.ry = 3
        g.add(badge)
        centred(g, x + bw / 2, y + h - 15.2, num, size=7, bold=True, colour=WHITE)
        centred(g, x + bw / 2, y + h - 32, title, size=7.6, bold=True,
                colour=ACCENT_STORE if last else BRAND)
        for j, line in enumerate(detail.split("\n")):
            centred(g, x + bw / 2, y + h - 43 - j * 8, line, size=5.7, colour=MUTED)
        if i < n - 1:
            arrow(g, x + bw + 1.5, y + h / 2, x + bw + gap - 1.5, y + h / 2,
                  colour=BRAND_MID, width=1.0, head=3.6)

    box(g, 14, 14, W - 28, 30, fill=WHITE, stroke=RULE, dash=(2.4, 2))
    text(g, 21, 33, "Recorded at every step:", size=6.2, bold=True, colour=BRAND)
    text(g, 21, 23.5,
         "who inspected  \u00b7  when  \u00b7  which model and version answered  \u00b7  "
         "how long it took  \u00b7  SHA-256 of every photograph",
         size=6, colour=MUTED)

    d.add(g)
    if width and width != W:
        factor = width / W
        d.scale(factor, factor)
        d.width, d.height = W * factor, H * factor
    return d


# =========================================================================
#  Standalone export, for dropping figures into the dissertation
# =========================================================================
FIGURES = {
    "figure-1-architecture": (architecture_diagram, "System architecture"),
    "figure-2-data-model": (data_model_diagram, "Data model"),
    "figure-3-workflow": (workflow_diagram, "Inspection lifecycle"),
}


def export_figures(out_dir: Path, dpi: int = 300) -> None:
    """Write each figure as a standalone file for use in the dissertation.

    PDF is always written: it is vector, needs no extra dependency, and is what
    LaTeX and modern Word both prefer for a figure. PNG is written too when
    ReportLab has a raster backend available; that backend (`rlPyCairo`) is an
    optional install, so its absence is reported rather than raised.
    """
    from reportlab.graphics import renderPDF

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from reportlab.graphics import renderPM

        raster = renderPM
    except Exception:  # noqa: BLE001
        raster = None

    png_failed = False
    for name, (builder, _caption) in FIGURES.items():
        drawing = builder(width=None)  # native size, no scaling
        renderPDF.drawToFile(drawing, str(out_dir / f"{name}.pdf"))
        written = f"{name}.pdf"

        if raster is not None and not png_failed:
            try:
                raster.drawToFile(
                    drawing, str(out_dir / f"{name}.png"), fmt="PNG", dpi=dpi, bg=0xFFFFFF
                )
                written += " / .png"
            except Exception:  # noqa: BLE001 - missing raster backend, not a real error
                png_failed = True

        print(f"  {written}")

    if raster is None or png_failed:
        print(
            "  (PNG export skipped - no raster backend. The PDF figures are vector and\n"
            "   import directly into Word and LaTeX. For PNGs: pip install rlPyCairo)"
        )
