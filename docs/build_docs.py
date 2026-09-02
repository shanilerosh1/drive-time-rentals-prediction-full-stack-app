"""Generate the project's PDF documentation.

    ../backend/.venv/bin/python build_docs.py

Writes USER_MANUAL.pdf and TECH_STACK.pdf next to this script. Re-run after
changing the content blocks below; the PDFs are build artefacts, the text here
is the source.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
import diagrams
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent

BRAND = colors.HexColor("#1F3A5F")
BRAND_LIGHT = colors.HexColor("#EEF3FA")
MUTED = colors.HexColor("#5A6472")
RULE = colors.HexColor("#D8DEE6")
CODE_BG = colors.HexColor("#F4F6F9")
WARN_BG = colors.HexColor("#FFF4E5")
WARN_LINE = colors.HexColor("#E08A00")
OK_BG = colors.HexColor("#E7F6EF")
OK_LINE = colors.HexColor("#4FA97F")

CONTENT_WIDTH = A4[0] - 46 * mm



# --- measured results ------------------------------------------------------
# The documentation should report what was measured, not what a notebook once
# printed. If an evaluation report exists, its numbers are used and the text
# says so; otherwise the notebook's original figures are shown, clearly labelled
# as the pre-fix baseline.
EVALUATION_PATH = OUT.parent / "backend" / "models" / "evaluation.json"
TRAINING_PATH = OUT.parent / "backend" / "models" / "car_damage_classifier.training.json"

NOTEBOOK_BASELINE = {
    "dent":          {"threshold": 0.540, "f1_at_0.5": 0.733, "f1": 0.751, "roc_auc": 0.852},
    "scratch":       {"threshold": 0.606, "f1_at_0.5": 0.784, "f1": 0.791, "roc_auc": 0.847},
    "crack":         {"threshold": 0.660, "f1_at_0.5": 0.418, "f1": 0.466, "roc_auc": 0.810},
    "glass_shatter": {"threshold": 0.718, "f1_at_0.5": 0.843, "f1": 0.900, "roc_auc": 0.990},
    "lamp_broken":   {"threshold": 0.747, "f1_at_0.5": 0.599, "f1": 0.657, "roc_auc": 0.897},
    "tire_flat":     {"threshold": 0.849, "f1_at_0.5": 0.667, "f1": 0.821, "roc_auc": 0.981},
}

CLASS_ORDER = ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"]


def load_evaluation() -> dict | None:
    import json

    if not EVALUATION_PATH.exists():
        return None
    try:
        return json.loads(EVALUATION_PATH.read_text())
    except Exception:  # noqa: BLE001 - a broken report must not break the build
        return None


def load_training() -> dict | None:
    import json

    if not TRAINING_PATH.exists():
        return None
    try:
        return json.loads(TRAINING_PATH.read_text())
    except Exception:  # noqa: BLE001
        return None


def styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontSize=25, leading=30,
            textColor=BRAND, alignment=TA_CENTER, spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontSize=11.5, leading=17,
            textColor=MUTED, alignment=TA_CENTER,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta", parent=base["Normal"], fontSize=9, leading=15,
            textColor=MUTED, alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=15, leading=19, textColor=BRAND,
            spaceBefore=4, spaceAfter=9,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=11.5, leading=15, textColor=BRAND,
            spaceBefore=13, spaceAfter=5,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontSize=9.8, leading=13,
            textColor=colors.HexColor("#35425A"), spaceBefore=9, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=9.3, leading=14, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontSize=9.3, leading=14,
            leftIndent=13, bulletIndent=3, spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "code", parent=base["Normal"], fontName="Courier", fontSize=8.2, leading=12,
            textColor=colors.HexColor("#1B2433"),
        ),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=8.4, leading=11.5),
        "cellb": ParagraphStyle(
            "cellb", parent=base["Normal"], fontSize=8.4, leading=11.5,
            fontName="Helvetica-Bold", textColor=BRAND,
        ),
        "callout": ParagraphStyle("callout", parent=base["Normal"], fontSize=8.6, leading=12.5),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=8, leading=11, textColor=MUTED,
        ),
    }


S = styles()


# --- building blocks ------------------------------------------------------
def h1(text):
    return Paragraph(text, S["h1"])


def h2(text):
    return Paragraph(text, S["h2"])


def h3(text):
    return Paragraph(text, S["h3"])


def p(text):
    return Paragraph(text, S["body"])


def bullets(items, style="bullet"):
    return [Paragraph(item, S[style], bulletText="•") for item in items]


def steps(items):
    out = []
    for index, item in enumerate(items, start=1):
        out.append(Paragraph(item, S["bullet"], bulletText=f"{index}."))
    return out


def code(lines: str):
    body = "<br/>".join(
        line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")
        for line in lines.strip("\n").split("\n")
    )
    table = Table([[Paragraph(body, S["code"])]], colWidths=[CONTENT_WIDTH])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )
    return KeepTogether([table, Spacer(1, 8)])


def callout(text, kind="warn"):
    bg, line = (WARN_BG, WARN_LINE) if kind == "warn" else (OK_BG, OK_LINE)
    table = Table([[Paragraph(text, S["callout"])]], colWidths=[CONTENT_WIDTH])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("LINEBEFORE", (0, 0), (0, -1), 2.4, line),
            ("BOX", (0, 0), (-1, -1), 0.4, line),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    return KeepTogether([table, Spacer(1, 9)])


def table(header: list[str], rows: list[list[str]], widths: list[float]):
    data = [[Paragraph(f"<b>{c}</b>", S["cell"]) for c in header]]
    for row in rows:
        data.append([Paragraph(str(c), S["cell"]) for c in row])
    total = sum(widths)
    scaled = [w / total * CONTENT_WIDTH for w in widths]
    tbl = Table(data, colWidths=scaled, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), BRAND),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]
    for i in range(2, len(data), 2):
        style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFBFD")))
    tbl.setStyle(TableStyle(style))
    return KeepTogether([tbl, Spacer(1, 9)])


def figure(drawing, number: int, caption: str):
    """A diagram with a numbered caption, kept together on one page."""
    return KeepTogether([
        Spacer(1, 4),
        drawing,
        Spacer(1, 5),
        Paragraph(
            f"<b>Figure {number}.</b> {caption}",
            ParagraphStyle("cap", fontSize=7.6, leading=10.5, textColor=MUTED,
                           alignment=TA_CENTER),
        ),
        Spacer(1, 12),
    ])


def make_doc(path: Path, title: str, footer_text: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        str(path), pagesize=A4,
        leftMargin=23 * mm, rightMargin=23 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
        title=title, author="Stefania Crishani (CB016792)", subject=title,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")

    def cover(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(BRAND)
        canvas.rect(0, A4[1] - 14 * mm, A4[0], 14 * mm, stroke=0, fill=1)
        canvas.setFillColor(BRAND_LIGHT)
        canvas.rect(0, 0, A4[0], 9 * mm, stroke=0, fill=1)
        canvas.restoreState()

    def page(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(23 * mm, A4[1] - 14 * mm, A4[0] - 23 * mm, A4[1] - 14 * mm)
        canvas.setFont("Helvetica", 7.4)
        canvas.setFillColor(MUTED)
        canvas.drawString(23 * mm, A4[1] - 12 * mm, title)
        canvas.drawRightString(A4[0] - 23 * mm, A4[1] - 12 * mm, "CB016792")
        canvas.line(23 * mm, 13 * mm, A4[0] - 23 * mm, 13 * mm)
        canvas.drawString(23 * mm, 9 * mm, footer_text)
        canvas.drawRightString(A4[0] - 23 * mm, 9 * mm, f"Page {doc_.page - 1}")
        canvas.restoreState()

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover),
        PageTemplate(id="body", frames=[frame], onPage=page),
    ])
    return doc


def cover_page(title: str, subtitle: str, meta_lines: list[str]) -> list:
    return [
        Spacer(1, 52 * mm),
        Paragraph(title, S["cover_title"]),
        Spacer(1, 3),
        Paragraph(subtitle, S["cover_sub"]),
        Spacer(1, 14 * mm),
        Table(
            [[""]], colWidths=[46 * mm], rowHeights=[1.6],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), BRAND)]),
            hAlign="CENTER",
        ),
        Spacer(1, 14 * mm),
        *[Paragraph(line, S["cover_meta"]) for line in meta_lines],
        NextPageTemplate("body"),
        PageBreak(),
    ]


# =========================================================================
#  USER MANUAL
# =========================================================================
def build_manual() -> None:
    doc = make_doc(
        OUT / "USER_MANUAL.pdf",
        "User Manual - Vehicle Damage Inspection System",
        "Automated Pre- and Post-Rental Damage Inspection - prototype",
    )
    story = cover_page(
        "Vehicle Damage<br/>Inspection System",
        "User Manual &amp; Step-by-Step Setup Guide",
        [
            "Automated Pre- and Post-Rental Passenger Car Damage Inspection",
            "MSc Dissertation Prototype &mdash; APIIT Sri Lanka",
            "Stefania Crishani &nbsp;&middot;&nbsp; CB016792",
            f"Generated {date.today().strftime('%d %B %Y')}",
        ],
    )

    # ---- How to use this manual ----
    story += [
        h1("How to use this manual"),
        p(
            "This manual assumes <b>no prior knowledge</b> of the project, of Python, or of "
            "machine learning. Every command you need to type is shown in full, together with "
            "what you should see when it works and roughly how long it takes."
        ),
        p("Work through it in order. There are two stages:"),
        table(
            ["Stage", "Sections", "How long", "How often"],
            [
                ["<b>A. Get it running</b>",
                 "1 &ndash; 5",
                 "about 10 minutes",
                 "Once per computer"],
                ["<b>B. Set up the AI model</b>",
                 "6 &ndash; 9",
                 "about 45 minutes, mostly unattended",
                 "Once, then only when retraining"],
                ["Daily use",
                 "10 &ndash; 12",
                 "&mdash;",
                 "Every time you use the system"],
            ],
            [2.2, 1.5, 2.4, 2.0],
        ),
        callout(
            "<b>You can do Stage A on its own.</b> The application runs immediately without a "
            "trained model, using a placeholder that produces fake damage scores so you can "
            "explore the screens. Every page and every PDF is clearly marked while this is the "
            "case. Stage B replaces the placeholder with a real model trained on 3,937 real "
            "damage photographs.",
            kind="ok",
        ),
        h2("A note on typing commands"),
        p(
            "Commands are typed into a <b>terminal</b> &mdash; a window where you type "
            "instructions instead of clicking. To open one:"
        ),
    ]
    story += bullets([
        "<b>macOS</b>: press Cmd+Space, type <i>Terminal</i>, press Enter.",
        "<b>Windows</b>: press the Windows key, type <i>Command Prompt</i>, press Enter.",
    ])
    story += [
        p(
            "Type each command exactly as shown and press Enter. Lines beginning with "
            "<font face='Courier'>#</font> are comments explaining what follows &mdash; you do "
            "not type those."
        ),
    ]

    # ---- 1. Overview ----
    story += [
        PageBreak(),
        h1("1. What this system does"),
        p(
            "This application replaces the manual walk-around inspection a rental operator "
            "performs at vehicle check-out and check-in. Staff photograph the vehicle, a "
            "deep-learning model classifies exterior damage, and the system produces a "
            "timestamped record. When the vehicle returns, it compares the two inspections and "
            "states which damage is <b>new this rental</b> and which was <b>already present at "
            "handover</b>."
        ),
        p("The system has two parts, and <b>both must be running</b> for it to work:"),
    ]
    story += bullets([
        "<b>The backend</b> &mdash; a Python program holding the database, the photographs, the "
        "damage model and the PDF report generator. You never look at it directly; it runs in a "
        "terminal window and answers requests.",
        "<b>The frontend</b> &mdash; the dashboard staff actually use, viewed in a web browser.",
    ])
    story += [
        Spacer(1, 6),
        figure(
            diagrams.workflow_diagram(width=CONTENT_WIDTH), 1,
            "What an inspection looks like end to end. Steps 1 to 3 happen at check-out and "
            "again at check-in; step 4 compares the two.",
        ),
    ]

    # ---- 2. Requirements ----
    story += [
        h1("2. Before you start"),
        p(
            "Two programs must be installed on the computer. Check each one by opening a "
            "terminal and typing the command in the third column. If you see a version number, "
            "it is installed; if you see <i>command not found</i>, install it from the link."
        ),
        table(
            ["What", "Version needed", "Check by typing", "If missing"],
            [
                ["Python", "3.11 or newer",
                 "<font face='Courier'>python3 --version</font><br/>"
                 "(Windows: <font face='Courier'>python --version</font>)",
                 "python.org/downloads &mdash; on Windows you <b>must</b> tick "
                 "<i>Add python.exe to PATH</i> during installation"],
                ["Node.js", "18.13+ or 20.9+",
                 "<font face='Courier'>node --version</font>",
                 "nodejs.org &mdash; choose the LTS version"],
            ],
            [1.3, 1.5, 2.4, 2.8],
        ),
        p("You also need:"),
    ]
    story += bullets([
        "<b>Disk space</b>: about 1 GB for Stage A, plus 3 GB for Stage B (the dataset and "
        "the machine-learning libraries).",
        "<b>An internet connection</b> for the first run of each stage.",
        "<b>A modern browser</b> &mdash; Chrome, Edge, Firefox or Safari.",
    ])

    # ---- 3. Starting ----
    story += [
        h1("3. Starting the application"),
        p(
            "You need <b>two terminal windows open at the same time</b>, one per part of the "
            "system. Both must stay open the whole time you are using the application. Closing "
            "a window stops that part."
        ),
        p(
            "First, in each window, move into the project folder. Replace the path below with "
            "wherever you saved the project:"
        ),
        code(
            "# macOS / Linux\n"
            "cd ~/projects/car-damage-identification\n"
            "\n"
            "# Windows\n"
            "cd C:\\Users\\YourName\\projects\\car-damage-identification"
        ),
        h2("Step 3.1 &mdash; Start the backend (window 1)"),
        code(
            "# macOS / Linux\n"
            "./run-backend.sh\n"
            "\n"
            "# Windows\n"
            "run-backend.bat"
        ),
        p(
            "<b>The first time only</b>, this installs everything the backend needs and takes "
            "one to two minutes. Later starts take a few seconds. It has worked when you see "
            "this line and the window stops producing new text:"
        ),
        code("INFO:     Uvicorn running on http://127.0.0.1:8000"),
        callout(
            "<b>Leave this window open.</b> It looks idle, but it is the running server. If you "
            "close it, the dashboard will stop being able to sign in or load anything.",
            kind="ok",
        ),
        h2("Step 3.2 &mdash; Start the frontend (window 2)"),
        p("Open a <b>second</b> terminal window, move into the project folder again, then:"),
        code(
            "# macOS / Linux\n"
            "./run-frontend.sh\n"
            "\n"
            "# Windows\n"
            "run-frontend.bat"
        ),
        p(
            "The first run installs the dashboard's packages and takes a few minutes. It has "
            "worked when you see:"
        ),
        code("Local:   http://localhost:4200/"),
        h2("Step 3.3 &mdash; Open the dashboard"),
        p(
            "Open your browser and go to <b>http://localhost:4200</b>. You should see the "
            "sign-in screen. If the page loads but signing in fails, the backend is not running "
            "&mdash; go back and check window 1."
        ),
        callout(
            "<b>Stopping the system:</b> press <font face='Courier'>Ctrl+C</font> in each window "
            "(on Windows, confirm with <font face='Courier'>Y</font>), or just close them. "
            "Nothing is lost &mdash; your records live in "
            "<font face='Courier'>backend/data/app.db</font> and your photographs in "
            "<font face='Courier'>backend/storage/</font>, and both are still there next time. "
            "The startup scripts also free their ports automatically, so you can simply run them "
            "again if you are unsure whether something is already running.",
            kind="ok",
        ),
    ]

    # ---- 4. Signing in ----
    story += [
        PageBreak(),
        h1("4. Signing in"),
        p("Two accounts are created automatically the first time the backend starts:"),
        table(
            ["Email", "Password", "Role", "Can do"],
            [
                ["admin@drivetime.lk", "ChangeMe123!", "Administrator",
                 "Everything, including managing users and editing any inspection"],
                ["inspector@drivetime.lk", "Inspector123!", "Inspector",
                 "Run inspections and view all records; edit only their own"],
            ],
            [2.0, 1.3, 1.2, 3.0],
        ),
        p(
            "The sign-in screen lists both accounts &mdash; click one to fill the form in "
            "automatically, then press <b>Sign in</b>. A session lasts 8 hours."
        ),
        callout(
            "These are development passwords, printed in this manual and visible in the source "
            "code. Change them &mdash; and change <font face='Courier'>SECRET_KEY</font> in "
            "<font face='Courier'>backend/.env</font> &mdash; before running this anywhere other "
            "people can reach."
        ),
    ]

    # ---- 5. First look ----
    story += [
        h1("5. Your first look around"),
        p(
            "The system starts with five fleet vehicles already registered, so there is "
            "something to work with immediately. Take a minute to click through the five items "
            "in the left-hand sidebar:"
        ),
        table(
            ["Sidebar item", "What it shows"],
            [
                ["<b>Dashboard</b>", "Activity counters, which damage types have been found "
                                     "across the fleet, and the most recent inspections."],
                ["<b>Inspections</b>", "Every recorded condition check, with filters by type, "
                                       "status and rental reference."],
                ["<b>Fleet</b>", "The registered vehicles, and each one's inspection history."],
                ["<b>Pre / post</b>", "The comparison screen &mdash; the heart of the system."],
                ["<b>Model</b>", "Which model is answering and how accurate it has been "
                                 "measured to be. Covered in section 9."],
            ],
            [1.6, 6.0],
        ),
        callout(
            "<b>Is there an amber banner across the top?</b> If so it says predictions are "
            "placeholders, and that is correct and expected on a fresh installation: no model "
            "has been trained yet, so the system generates fake damage scores purely so you can "
            "explore the workflow. Until Stage B is done, <b>do not treat any damage finding as "
            "meaningful</b>.<br/><br/>"
            "If there is <b>no</b> banner, someone has already completed Stage B for you and the "
            "findings are real. You can skip to section 10, though sections 6 to 9 are still "
            "worth reading to understand what those findings mean and how they were checked."
        ),
    ]

    # ---- STAGE B ----
    story += [
        PageBreak(),
        h1("Stage B &mdash; Setting up the AI model"),
        p(
            "This is what makes the system actually detect damage rather than pretend to. There "
            "are four steps, and you do them <b>once</b>:"
        ),
        table(
            ["Step", "What it does", "Time"],
            [
                ["<b>6.</b> Install the AI libraries", "Adds PyTorch, the machine-learning "
                                                        "toolkit", "5 min"],
                ["<b>7.</b> Download the dataset", "Fetches 3,937 real damage photographs "
                                                   "with expert labels", "10 min"],
                ["<b>7b.</b> Add undamaged cars", "Fetches photographs of <i>clean</i> cars. "
                                                  "Without these the model cannot say "
                                                  "\u2018no damage\u2019", "5 min"],
                ["<b>8.</b> Train the model", "Teaches the model to recognise damage. Runs "
                                              "unattended", "20&ndash;40 min"],
                ["<b>9.</b> Verify the model", "Measures how accurate it actually is", "2 min"],
            ],
            [1.9, 4.4, 1.3],
        ),
        p(
            "Every command below is typed in a <b>new, third terminal window</b>, and every one "
            "starts by moving into the <font face='Courier'>backend</font> folder. Leave the two "
            "windows from Stage A running."
        ),
        h2("6. Install the AI libraries"),
        code(
            "cd /path/to/car-damage-identification/backend\n"
            "\n"
            "# macOS / Linux\n"
            ".venv/bin/pip install -r requirements-ml.txt\n"
            "\n"
            "# Windows\n"
            ".venv\\Scripts\\pip.exe install -r requirements-ml.txt"
        ),
        p(
            "This downloads roughly 500 MB. When it finishes you will see a line beginning "
            "<font face='Courier'>Successfully installed</font>."
        ),
        h2("7. Download the training data"),
        code(
            "# macOS / Linux\n"
            ".venv/bin/python training/download_dataset.py\n"
            "\n"
            "# Windows\n"
            ".venv\\Scripts\\python.exe training\\download_dataset.py"
        ),
        p(
            "This fetches <b>CarDD</b> (Wang et al., 2023) &mdash; the public research dataset "
            "of real car damage photographs, each labelled by human annotators. Progress is "
            "printed as it goes, with an estimate of the time remaining."
        ),
        p("You should end with:"),
        code(
            "Dataset ready at .../backend/data/CarDD_COCO  (318 MB)\n"
            "  train: 2816 images\n"
            "  val  : 810 images\n"
            "  test : 374 images\n"
            "  classes: ['dent', 'scratch', 'crack', 'glass shatter', "
            "'lamp broken', 'tire flat']"
        ),
        callout(
            "<b>The three splits matter and are the basis of section 9.</b> <i>train</i> is what "
            "the model learns from. <i>val</i> is used during training to check progress. "
            "<i>test</i> is held back and never shown to the model at all &mdash; it is the only "
            "honest way to measure accuracy afterwards. If the run is interrupted, simply run "
            "the same command again: it downloads only what is missing.",
            kind="ok",
        ),
    ]

    story += [
        PageBreak(),
        h2("7b. Add undamaged cars (do not skip this)"),
        callout(
            "<b>CarDD contains no undamaged vehicles.</b> All 4,000 photographs show damage. "
            "A model trained on that alone is never shown a clean car, so it cannot answer "
            "\u2018no damage\u2019 \u2014 asked about a pristine vehicle it returns whichever "
            "damage class clears its threshold first. Measured, a model trained without this "
            "step reported damage on <b>88.5% of clean cars</b>. This step is what fixes that."
        ),
        p(
            "The photographs come from Stanford Cars, a public dataset of ordinary vehicles. "
            "Download one shard and extract it:"
        ),
        code(
            "cd backend\n"
            "mkdir -p data/negatives_raw\n"
            "curl -L -o data/negatives_raw/part0.parquet \\\n"
            "  https://huggingface.co/datasets/Multimodal-Fatima/StanfordCars_test/\\\n"
            "resolve/main/data/test-00000-of-00003-18db3ba1d2223f87.parquet\n"
            "\n"
            ".venv/bin/python training/extract_negatives.py"
        ),
        p("You should end with:"),
        code("Extracted 2681 undamaged car photographs to data/CarDD_COCO/negatives (137 MB)"),
        p(
            "The training and evaluation scripts pick that folder up automatically. They add "
            "the clean cars with an all-zero label \u2014 no damage of any kind \u2014 and "
            "split them 70/20/10 across train, validation and test in the same proportions as "
            "CarDD itself, so the false-alarm rate is measured on clean cars the model never "
            "saw either."
        ),
        p(
            "If you skip this step both scripts warn you, and the evaluation refuses to call "
            "its headline figure \u2018damaged versus clean\u2019, because without clean cars "
            "it is only measuring whether damage is found when damage is present."
        ),
        Spacer(1, 4),
                h2("8. Train the model"),
        code(
            "# macOS / Linux\n"
            ".venv/bin/python training/train_classifier.py \\\n"
            "    --data-root data/CarDD_COCO --epochs 30\n"
            "\n"
            "# Windows (all on one line)\n"
            ".venv\\Scripts\\python.exe training\\train_classifier.py "
            "--data-root data/CarDD_COCO --epochs 30"
        ),
        p(
            "This is the long step. It runs unattended &mdash; start it and do something else. "
            "It prints one line per <i>epoch</i> (one complete pass over the training images):"
        ),
        code(
            "Training on mps\n"
            "Trainable parameters: 9,296,100\n"
            "Epoch 01/20 | train 0.9278 | val 0.6573 | 128s  <- best (saved)\n"
            "Epoch 02/20 | train 0.6035 | val 0.5510 | 101s  <- best (saved)\n"
            "Epoch 03/20 | train 0.5232 | val 0.5137 | 104s  <- best (saved)"
        ),
        p("How to read those lines:"),
    ]
    story += bullets([
        "<b>Training on ...</b> &mdash; <font face='Courier'>cuda</font> is an NVIDIA graphics "
        "card, <font face='Courier'>mps</font> is an Apple Silicon Mac, "
        "<font face='Courier'>cpu</font> is everything else. CPU works but is several times "
        "slower; allow a couple of hours.",
        "<b>train</b> is how well the model does on the images it is learning from. <b>val</b> "
        "is how well it does on images held aside during training. <b>val is the one that "
        "matters</b> &mdash; it is the honest signal.",
        "<b>&lt;- best (saved)</b> marks an epoch better than every one before it. The "
        "checkpoint is written to disk at that moment, so if the run is interrupted you keep "
        "the best model so far rather than losing everything.",
    ])
    story += [
        Spacer(1, 4),
        h3("When train keeps falling but val starts rising"),
        p(
            "This is <b>overfitting</b>: the model has begun memorising the training "
            "photographs instead of learning what damage looks like in general. It is normal "
            "and expected, and it tells you training has gone as far as it usefully can."
        ),
        code(
            "Epoch 07/30 | train 0.3793 | val 0.4501 | 75s  <- best (saved)\n"
            "Epoch 08/30 | train 0.3556 | val 0.4858 | 100s\n"
            "Epoch 09/30 | train 0.3365 | val 0.4754 | 81s\n"
            "Epoch 10/30 | train 0.3141 | val 0.4765 | 78s      <- val no longer improving"
        ),
        p(
            "You do not need to watch for this. The script stops on its own once validation "
            "has failed to improve for several epochs in a row, and keeps the best epoch:"
        ),
        code(
            "Validation loss has not improved for 5 epochs.\n"
            "Stopping early at epoch 12; best was epoch 7 (val 0.4501)."
        ),
        p(
            "Control it with <font face='Courier'>--patience N</font> (default 8; use "
            "<font face='Courier'>--patience 0</font> to disable and always run every epoch). "
            "Because of this, asking for more epochs than you need costs nothing &mdash; the "
            "run simply stops when it stops improving."
        ),
        callout(
            "<b>A note for the dissertation.</b> The original notebook used 60 epochs, which "
            "made sense while its backbone was accidentally frozen and only 790,022 parameters "
            "had to converge. With that bug fixed, 9,296,100 parameters converge in under ten "
            "epochs and then overfit. If you observe the same, it is a genuine result about the "
            "corrected setup, not a failed run &mdash; and worth reporting as such."
        ),
        Spacer(1, 4),
    ]
    story += [
        p("At the end you will see a table of per-class results and:"),
        code(
            "Macro F1 (tuned thresholds): 0.7xxx\n"
            "Saved checkpoint to models/car_damage_classifier.pth"
        ),
        h3("Step 8.1 &mdash; Put the model into service"),
        p(
            "There is a script that performs the whole switch-over &mdash; install the "
            "checkpoint, restart the API on it, verify it, and rebuild the demo data around it "
            "&mdash; in one command. This is the recommended route, and it covers steps 8.1, 9 "
            "and 10 together:"
        ),
        code(
            "cd backend\n"
            "./finalize_demo.sh          # macOS / Linux"
        ),
        p(
            "If you would rather do it by hand, or you are on Windows: go to terminal window 1, "
            "press <font face='Courier'>Ctrl+C</font> to stop the backend, then start it again "
            "with the same command as before. On startup it finds the trained model and loads "
            "it automatically &mdash; there is nothing to configure."
        ),
        p("You know it worked when:"),
    ]
    story += bullets([
        "The startup messages no longer include the warning about placeholder predictions.",
        "The amber banner has disappeared from every screen in the dashboard.",
        "The <b>Model</b> page shows <i>Trained weights loaded</i>.",
    ])

    # ---- 9. Verification ----
    story += [
        h1("9. Verifying that the model actually works"),
        p(
            "Training tells you a model was produced. It does not tell you whether that model is "
            "any good. This step measures it, and it is the step to point at when someone asks "
            "whether the system really identifies damage."
        ),
        code(
            "# macOS / Linux\n"
            ".venv/bin/python training/evaluate.py \\\n"
            "    --data-root data/CarDD_COCO --report\n"
            "\n"
            "# Windows (all on one line)\n"
            ".venv\\Scripts\\python.exe training\\evaluate.py "
            "--data-root data/CarDD_COCO --report"
        ),
        p("Two things make this a genuine check rather than the model marking its own homework:"),
    ]
    story += steps([
        "It scores the <b>test split only</b> &mdash; 374 photographs the model has never seen, "
        "in training or otherwise &mdash; against the dataset's own expert labels.",
        "It loads the model <b>through the same code the running application uses</b> to answer "
        "a request. If anything were wrong in the live service, it would be wrong here too.",
    ])
    story += [
        Spacer(1, 4),
        p("It prints a table like this, then saves it:"),
        code(
            "class            support  precis  recall      F1      AP     AUC\n"
            "-----------------------------------------------------------------\n"
            "dent                 157   0.7xx   0.8xx   0.7xx   0.8xx   0.8xx\n"
            "scratch              183   0.7xx   0.8xx   0.8xx   0.8xx   0.8xx\n"
            "...\n"
            "Exact-match ratio (all six classes right): 0.xxx\n"
            "Any-damage accuracy (damaged vs clean)   : 0.xxx"
        ),
        h3("What the numbers mean"),
        table(
            ["Number", "Plain English", "Why it matters here"],
            [
                ["<b>Precision</b>",
                 "Of the damage the model reported, how much was really there.",
                 "Low precision means <b>accusing customers of damage that does not exist</b>. "
                 "For a dispute tool this is the number that matters most."],
                ["<b>Recall</b>",
                 "Of the damage that was really there, how much the model found.",
                 "Low recall means <b>missed damage</b> &mdash; the operator absorbs the cost."],
                ["<b>F1</b>",
                 "A single score balancing the two above.",
                 "The headline per-class number. 1.0 is perfect; below about 0.5 the class is "
                 "unreliable on its own."],
                ["<b>Support</b>",
                 "How many test images genuinely contain that damage type.",
                 "A class with small support has a less trustworthy score, simply because it "
                 "was measured on fewer examples."],
                ["<b>Damaged vs clean</b>",
                 "How often it gets 'is this car damaged at all' right, ignoring the type.",
                 "The realistic operational number \u2014 but <b>only meaningful if clean cars "
                 "are in the test set</b> (step 7b). Without them it measures nothing but "
                 "recall."],
                ["<b>False alarms</b>",
                 "How often it reports damage on a car that has none.",
                 "The number that decides whether the tool is safe to point at a customer. "
                 "A high rate means accusing people of damage that is not there."],
                ["<b>Exact match</b>",
                 "How often all six damage types are simultaneously correct.",
                 "A deliberately harsh measure. It will always look low; one wrong class out of "
                 "six fails the whole image."],
            ],
            [1.3, 2.9, 3.4],
        ),
        h3("Where to see the results"),
    ]
    story += bullets([
        "<b>In the dashboard</b>: click <b>Model</b> in the sidebar. Headline figures, the "
        "per-class table, and a <i>spot check</i> list comparing what the model said against the "
        "expert label for individual images. Use the <b>Mistakes only</b> button to look "
        "specifically at what it gets wrong.",
        "<b>As a PDF</b>: <font face='Courier'>backend/models/evaluation.pdf</font>, written by "
        "the <font face='Courier'>--report</font> option. It shows individual photographs beside "
        "their labels, <b>including the failures</b> &mdash; a report showing only successes "
        "would prove nothing.",
        "<b>As raw data</b>: <font face='Courier'>backend/models/evaluation.json</font>.",
    ])
    story += [
        h2("9.1 Four ways to satisfy yourself it works"),
        p(
            "The metrics above are the formal answer. These four checks are the practical "
            "ones, easiest first. Run them in front of a supervisor; none needs statistics "
            "to read."
        ),
        h3("Check 1 &mdash; Read the measured numbers (30 seconds)"),
        p(
            "Click <b>Model</b> in the sidebar. It shows performance measured on the held-out "
            "test split: macro F1, any-damage accuracy, and a per-class table with each "
            "class's own threshold and the raw TP / FP / FN counts behind it."
        ),
        p(
            "Then press <b>Mistakes only</b> in the spot-check list. That filters to the "
            "images the model got <i>wrong</i>, beside the expert label. A tool that only "
            "showed you its successes would not be worth trusting."
        ),
        h3("Check 2 &mdash; Test it against a known answer key (5 minutes)"),
        p(
            "A ready-made pack is generated for this purpose: fourteen photographs from the "
            "held-out split, two per damage type plus two hard multi-damage cases, with a "
            "written answer key."
        ),
        code(
            "cd backend\n"
            ".venv/bin/python training/make_verify_pack.py\n"
            "\n"
            "#  ->  data/verify_samples/\n"
            "#          ANSWER_KEY.md     what each photograph actually shows\n"
            "#          answer_key.json   the same, machine-readable\n"
            "#          000033.jpg ...    the photographs"
        ),
    ]
    story += steps([
        "Open <b>ANSWER_KEY.md</b> and keep it beside you.",
        "In the dashboard, click <b>+ New inspection</b>, pick any vehicle, type a rental "
        "reference such as <font face='Courier'>VERIFY</font>, and create it.",
        "Drag every photograph from <font face='Courier'>verify_samples/</font> onto the drop "
        "zone and click <b>Upload and analyse</b>.",
        "Compare what each photograph reports against the answer key.",
    ])
    story += [
        Spacer(1, 5),
        p("On the reference run the result was:"),
        code(
            "file          expert says                model says                     verdict\n"
            "---------------------------------------------------------------------------------\n"
            "000012.jpg    Tyre flat                  Tyre flat                      EXACT\n"
            "000015.jpg    Scratch                    Scratch                        EXACT\n"
            "000090.jpg    Glass shatter              Glass shatter                  EXACT\n"
            "000297.jpg    Lamp broken                Lamp broken                    EXACT\n"
            "000033.jpg    Dent                       Dent, Scratch                  found it\n"
            "000088.jpg    Crack                      Crack, Scratch                 found it\n"
            "000044.jpg    Crack, Dent, Scratch       Crack, Dent, Lamp b., Scratch  found it\n"
            "---------------------------------------------------------------------------------\n"
            "Caught the real damage in 14/14.  Exactly right on all six classes: 7/14."
        ),
        p(
            "Read the <i>shape</i> of the near-misses, not just the count. Every one adds an "
            "<b>extra</b> class rather than missing the real one &mdash; 'Dent' becomes 'Dent, "
            "Scratch'. For an inspection aid that is the safer direction to err in, because a "
            "human confirms every finding before it reaches a customer. Note also what a "
            "second opinion costs: 'scratch' is the class most often added, and it has the "
            "lowest threshold of the six."
        ),
        h3("Check 3 &mdash; Reproducibility (2 minutes)"),
        p(
            "Upload the <b>same photograph twice</b> and compare the scores. They must be "
            "identical. If the same evidence produced different answers on different days, no "
            "report built on it could be defended in a dispute."
        ),
        code(
            "class              upload 1    upload 2    identical?\n"
            "-----------------------------------------------------\n"
            "glass_shatter        1.0000      1.0000    yes\n"
            "dent                 0.1107      0.1107    yes\n"
            "scratch              0.0041      0.0041    yes\n"
            "-----------------------------------------------------\n"
            "Same SHA-256 fingerprint, identical to four decimal places."
        ),
        h3("Check 4 &mdash; The negative control: does it cry wolf?"),
        p(
            "<b>This is the check that matters most</b>, and the one most easily missed. A "
            "system that reports damage on an undamaged car would accuse customers of damage "
            "they did not cause."
        ),
        p(
            "It is now measured automatically. Provided step 7b was done, the evaluation "
            "includes clean cars the model never saw and reports:"
        ),
        code(
            "Damaged vs clean, overall accuracy       : 0.9xx\n"
            "False alarms on clean cars               : n/269 (x.x%)"
        ),
        p(
            "The <b>Model</b> page shows the same figure as a <i>False alarms</i> card, "
            "coloured red above 15%. If the card is absent, no clean cars were tested and the "
            "page says so explicitly rather than implying a pass."
        ),
        callout(
            "<b>Why this check exists.</b> An early build of this system scored macro F1 0.786 "
            "and looked excellent \u2014 then reported a dent on a photograph of a pristine "
            "Ford Mustang. Measured properly, it was raising false alarms on <b>88.5% of clean "
            "cars</b>. Nothing in the original metrics could reveal that, because every test "
            "image contained damage. The fix was step 7b."
        ),
        p(
            "Do the human version too: <b>photograph an undamaged vehicle yourself and upload "
            "it.</b> A car from your own fleet, in your own lighting, is a harder and more "
            "honest test than any curated dataset."
        ),
        Spacer(1, 6),
        table(
            ["Check", "Answers the question", "Effort"],
            [
                ["1. Model page", "How accurate is it overall, and where is it weak?", "30 s"],
                ["2. Answer-key pack", "Does it get specific, known photographs right?", "5 min"],
                ["3. Reproducibility", "Would a report hold up if challenged?", "2 min"],
                ["4. Negative control", "Does it cry wolf on an undamaged car? "
                                        "(measured, plus upload your own)", "5 min"],
            ],
            [1.7, 4.3, 1.0],
        ),
        Spacer(1, 4),
        callout(
            "<b>Expect the per-class scores to differ.</b> Glass shatter and flat tyres are "
            "distinctive and score well. Cracks are thin, low-contrast and easily confused with "
            "panel gaps or reflections, and score worst. This is a real property of the problem, "
            "not a bug &mdash; and it is why the dashboard shows each class's own F1 when you "
            "hover over a damage label, so a reader can weigh each finding appropriately."
        ),
    ]

    # ---- 10. Real demo data ----
    story += [
        PageBreak(),
        h1("10. Loading the demo with real damage photographs"),
        p(
            "Optional, but recommended before showing the system to anyone. This fills the "
            "database with rentals built from <b>real photographs from the test split</b>, "
            "pairing a handover image with a return image that carries additional damage, so "
            "the comparison screen has genuine new damage to find."
        ),
        code(
            "# macOS / Linux\n"
            ".venv/bin/python seed_demo.py --reset\n"
            "\n"
            "# Windows\n"
            ".venv\\Scripts\\python.exe seed_demo.py --reset"
        ),
        callout(
            "<font face='Courier'>--reset</font> <b>deletes every existing inspection</b> and "
            "its photographs before seeding. Vehicles and user accounts are kept. Leave the flag "
            "off to add demo rentals alongside whatever is already there."
        ),
        p(
            "Each seeded inspection records the dataset's expert labels in its <b>Notes</b> "
            "field. That turns the dashboard itself into a spot-check: open any inspection and "
            "compare the damage the system reports against the ground truth written in the "
            "notes."
        ),
    ]

    # ---- 11. Daily use ----
    story += [
        h1("11. Running an inspection"),
        h2("11.1 Register the vehicle (once per vehicle)"),
        p(
            "<b>Fleet</b> &rarr; <b>+ Add vehicle</b>. Registration, make and model are "
            "required. The registration is forced to upper case and must be unique &mdash; it is "
            "how the system identifies the car."
        ),
        h2("11.2 Record the handover (pre-rental)"),
    ]
    story += steps([
        "Click <b>+ New inspection</b>, top right of any screen.",
        "Choose <b>Pre-rental</b>.",
        "Select the vehicle.",
        "Enter a <b>rental reference</b>. <b>This is the most important field.</b> It is what "
        "links the handover check to the return check. Invent any scheme you like "
        "(for example <font face='Courier'>R-2026-0148</font>) but use the <b>identical</b> "
        "reference on both halves of the same rental, or the comparison will not find its pair.",
        "Optionally record the odometer, the location and any notes.",
        "Click <b>Create and add photographs</b>.",
        "Choose the <b>capture angle</b> from the dropdown, then drag photographs onto the drop "
        "zone (or click <i>browse</i>). JPEG, PNG or WebP, up to 15 MB each.",
        "Click <b>Upload and analyse</b>. Results appear when analysis finishes &mdash; a "
        "second or two per photograph.",
        "Change the capture angle and repeat for each side of the car, so the report identifies "
        "every photograph correctly.",
    ])
    story += [
        callout(
            "Photograph every panel you would check by hand. The system can only report damage "
            "that appears in a photograph. An unphotographed panel is <b>not</b> evidence of an "
            "undamaged panel, and the reports state this explicitly."
        ),
        h2("11.3 Record the return (post-rental)"),
        p(
            "Exactly the same, but choose <b>Post-rental</b> and enter the <b>same rental "
            "reference</b> you used at handover."
        ),
        h2("11.4 Read the result"),
        p(
            "Each photograph shows all six damage types with a confidence bar. Two things on "
            "that bar matter:"
        ),
    ]
    story += bullets([
        "<b>The coloured bar</b> is how confident the model is.",
        "<b>The small grey tick</b> is that damage type's decision threshold. Each type has its "
        "own, tuned during training &mdash; so a raw percentage is not comparable between types, "
        "and only a bar that reaches its own tick counts as detected.",
    ])
    story += [
        p(
            "Detected types appear in full colour and are listed at the top of the inspection; "
            "the rest are dimmed. Hovering over a damage label shows that type's measured F1 "
            "score, so you can judge how much weight to give it."
        ),
        p(
            "The <b>severity hint</b> (minor / moderate / severe) comes from how far a score "
            "clears its threshold. It is a display aid only &mdash; the model was never taught "
            "severity and does not measure how big the damage is."
        ),
    ]

    story += [
        PageBreak(),
        h1("12. Comparing handover against return"),
        p(
            "This is what the system is for. Click <b>Pre / post</b> in the sidebar, choose the "
            "vehicle, and optionally type the rental reference &mdash; leave it blank and the "
            "most recent pair is used. Click <b>Compare</b>."
        ),
        p("The verdict panel states the outcome, and the table breaks it down:"),
        table(
            ["Outcome", "What it means", "Chargeable?"],
            [
                ["<b>New this rental</b>",
                 "Below threshold in every handover photograph, above threshold in at least one "
                 "return photograph.",
                 "<b>Yes</b> &mdash; it arose during the rental."],
                ["<b>Pre-existing</b>", "Detected in both inspections.",
                 "No &mdash; the customer did not cause it."],
                ["<b>Not detected on return</b>",
                 "Found at handover but not on return. Usually a repair, a different camera "
                 "angle, or a borderline score either side of the threshold.",
                 "No."],
            ],
            [1.5, 3.9, 2.0],
        ),
        p(
            "Rows marked new are highlighted in red. <b>Export comparison PDF</b> produces the "
            "document you would attach to a damage claim."
        ),
        h2("12.1 The two PDF reports"),
    ]
    story += bullets([
        "<b>Inspection report</b> &mdash; from any inspection, click <b>Export PDF</b>. Contains "
        "the record, the vehicle, the detected damage with confidences and thresholds, and a "
        "page of photographs. Each image carries its SHA-256 fingerprint, its dimensions, which "
        "model analysed it and how long that took.",
        "<b>Comparison report</b> &mdash; from the Pre / post screen. Both inspections side by "
        "side with the damage delta, new damage highlighted.",
    ])
    story += [
        p(
            "The SHA-256 fingerprint is recorded when a photograph is uploaded and never "
            "recalculated. It lets you prove later that the image behind a finding is the image "
            "that was analysed &mdash; the property that makes a report usable in a dispute."
        ),
    ]

    # ---- 13. Troubleshooting ----
    story += [
        h1("13. Troubleshooting"),
        table(
            ["Symptom", "Cause and fix"],
            [
                ["Sign-in fails, or the page says it cannot connect",
                 "The backend is not running. Check terminal window 1 and start it again."],
                ["<font face='Courier'>Address already in use</font>",
                 "The startup scripts free their ports automatically, so this is rare. If it "
                 "happens, find the culprit with <font face='Courier'>lsof -i :8000</font> "
                 "(macOS/Linux) or <font face='Courier'>netstat -ano | findstr :8000</font> "
                 "(Windows) and stop it."],
                ["Windows: <font face='Courier'>'python' is not recognised</font>",
                 "Python is not on your PATH. Reinstall from python.org with <i>Add python.exe "
                 "to PATH</i> ticked, then open a <b>new</b> Command Prompt."],
                ["Windows: the window closes instantly",
                 "Something failed. Run the .bat file from an already-open Command Prompt "
                 "instead of double-clicking, so the error stays on screen."],
                ["Signed out unexpectedly",
                 "The 8-hour session expired. Sign in again."],
                ["Upload rejected: <i>not a readable image</i>",
                 "The file is not a JPEG, PNG or WebP, or is damaged. The format is checked by "
                 "opening the image, not by trusting the file extension."],
                ["Upload rejected for size",
                 "Over 15 MB. Raise <font face='Courier'>MAX_UPLOAD_MB</font> in "
                 "<font face='Courier'>backend/.env</font>, or shrink the photograph."],
                ["Amber placeholder banner will not go away",
                 "No trained model was found, or it failed to load. Confirm "
                 "<font face='Courier'>backend/models/car_damage_classifier.pth</font> exists, "
                 "restart the backend, and open the <b>Model</b> page."],
                ["Training says <font face='Courier'>no images found</font>",
                 "Step 7 has not been run, or was run in a different folder. Re-run "
                 "<font face='Courier'>training/download_dataset.py</font> from inside "
                 "<font face='Courier'>backend</font>."],
                ["Training is extremely slow",
                 "It is running on CPU. That is normal and still works &mdash; allow a couple of "
                 "hours, or use <font face='Courier'>--epochs 10</font> for a quicker, less "
                 "accurate model."],
                ["Evaluation says the mock predictor is loaded",
                 "The trained model is not in place. Complete step 8 and restart the backend "
                 "before running the evaluation."],
                ["It reports damage on a car that is clearly undamaged",
                 "Step 7b was skipped, so the model never learned what a clean car looks like "
                 "and cannot answer 'no damage'. Run "
                 "<font face='Courier'>training/extract_negatives.py</font>, retrain, and "
                 "check the <i>False alarms</i> card on the Model page."],
                ["The Model page shows no False alarms card",
                 "No clean cars were in the test set, so the rate could not be measured. This "
                 "is not a pass \u2014 it is an unmeasured risk. See step 7b."],
                ["The model reports an extra damage type that is not there",
                 "Common, and the safer direction to err in. Hover the damage label to see "
                 "that class's measured F1, and check the confidence bar: a bar only just past "
                 "its threshold is a weak claim. Every finding is meant to be confirmed by a "
                 "person."],
                ["<font face='Courier'>make_verify_pack.py</font> says the dataset is missing",
                 "Step 7 has not been run. The pack is drawn from the downloaded test split."],
                ["Training stopped before the epoch count you asked for",
                 "That is early stopping doing its job: validation had stopped improving. The "
                 "best epoch was kept. Use <font face='Courier'>--patience 0</font> to run "
                 "every epoch regardless."],
                ["Training was interrupted part-way",
                 "Nothing is lost. The best epoch so far is already on disk as "
                 "<font face='Courier'>models/car_damage_classifier.best.pth</font>; "
                 "<font face='Courier'>finalize_demo.sh</font> will promote it, or copy it over "
                 "<font face='Courier'>car_damage_classifier.pth</font> yourself."],
                ["Downloads hang or time out",
                 "Some networks block Python's own downloader. Both the dataset script and the "
                 "training script fall back to <font face='Courier'>curl</font> automatically, "
                 "so re-running the command usually succeeds."],
                ["Want to wipe everything and start again",
                 "Stop the backend, delete <font face='Courier'>backend/data/app.db</font> and "
                 "the <font face='Courier'>backend/storage/</font> folder, then start it again. "
                 "Accounts and vehicles are recreated; inspections are not."],
            ],
            [2.2, 5.4],
        ),
    ]

    # ---- 14. Quick reference ----
    story += [
        PageBreak(),
        h1("14. Quick reference"),
        h2("Every command, in order"),
        code(
            "# ---- Stage A: run the application (two terminal windows) ----\n"
            "./run-backend.sh          # window 1   (Windows: run-backend.bat)\n"
            "./run-frontend.sh         # window 2   (Windows: run-frontend.bat)\n"
            "#    then open http://localhost:4200\n"
            "\n"
            "# ---- Stage B: set up the model (third window, inside backend/) ----\n"
            "cd backend\n"
            ".venv/bin/pip install -r requirements-ml.txt        # 6. libraries\n"
            ".venv/bin/python training/download_dataset.py       # 7. damaged cars\n"
            "#    7b. undamaged cars - see section 7b for the curl command\n"
            ".venv/bin/python training/extract_negatives.py      # 7b. clean cars\n"
            ".venv/bin/python training/train_classifier.py \\\n"
            "    --data-root data/CarDD_COCO \\\n"
            "    --epochs 20 --patience 5                        # 8. train\n"
            "\n"
            "./finalize_demo.sh          # 8.1 + 9 + 10 in one step:\n"
            "                            #   installs the checkpoint, restarts the\n"
            "                            #   API on it, verifies it against held-out\n"
            "                            #   data, re-seeds the demo\n"
            "\n"
            "# ---- or do those three by hand ----\n"
            "#   restart the backend so it picks up the model\n"
            ".venv/bin/python training/evaluate.py \\\n"
            "    --data-root data/CarDD_COCO --report            # 9. verify\n"
            ".venv/bin/python seed_demo.py --reset               # 10. demo data\n"
            "\n"
            "# ---- checking it by hand (section 9.1) ----\n"
            ".venv/bin/python training/make_verify_pack.py       # answer-key pack\n"
            "#    then drag data/verify_samples/*.jpg into a new inspection\n"
            "\n"
            "# On Windows replace  .venv/bin/python  with  .venv\\Scripts\\python.exe\n"
            "#                and  .venv/bin/pip     with  .venv\\Scripts\\pip.exe"
        ),
        h2("Addresses"),
        table(
            ["Address", "What it is"],
            [
                ["<font face='Courier'>http://localhost:4200</font>",
                 "The dashboard &mdash; this is the one you use"],
                ["<font face='Courier'>http://localhost:8000/docs</font>",
                 "Interactive API documentation, for testing endpoints directly"],
                ["<font face='Courier'>http://localhost:8000/api/v1/model</font>",
                 "Which model is loaded right now. "
                 "<font face='Courier'>\"is_real\": true</font> means a trained model"],
            ],
            [2.8, 4.8],
        ),
        h2("Where things are kept"),
        table(
            ["Path", "Contents"],
            [
                ["<font face='Courier'>backend/data/app.db</font>",
                 "All records: users, vehicles, inspections, findings"],
                ["<font face='Courier'>backend/data/CarDD_COCO/</font>",
                 "The training dataset (only after step 7)"],
                ["<font face='Courier'>backend/data/CarDD_COCO/negatives/</font>",
                 "Undamaged cars, added in step 7b"],
                ["<font face='Courier'>backend/data/verify_samples/</font>",
                 "The hand-verification pack and its answer key (section 9.1)"],
                ["<font face='Courier'>backend/storage/inspections/</font>",
                 "Uploaded photographs and thumbnails"],
                ["<font face='Courier'>backend/models/</font>",
                 "The trained model (<font face='Courier'>car_damage_classifier.pth</font>), "
                 "the best-so-far checkpoint written during training "
                 "(<font face='Courier'>...best.pth</font>), and the evaluation report "
                 "(<font face='Courier'>evaluation.json</font> / "
                 "<font face='Courier'>.pdf</font>)"],
                ["<font face='Courier'>backend/finalize_demo.sh</font>",
                 "One-shot: install the model, restart the API, verify, re-seed"],
                ["<font face='Courier'>backend/.env</font>",
                 "Settings &mdash; passwords, limits, ports"],
                ["<font face='Courier'>docs/</font>",
                 "This manual and the technology document"],
            ],
            [3.0, 4.6],
        ),
    ]

    doc.build(story)
    print(f"Wrote {OUT / 'USER_MANUAL.pdf'}")


# =========================================================================
#  TECH STACK DOCUMENT
# =========================================================================
def build_tech_stack() -> None:
    doc = make_doc(
        OUT / "TECH_STACK.pdf",
        "Technology Stack - Vehicle Damage Inspection System",
        "Automated Pre- and Post-Rental Damage Inspection - prototype",
    )
    story = cover_page(
        "Technology Stack",
        "Architecture, components and design decisions",
        [
            "Developing a Deep Learning-Based Computer Vision Framework for Automated",
            "Pre- and Post-Rental Passenger Car Damage Inspection",
            "MSc Dissertation Prototype &mdash; APIIT Sri Lanka",
            "Stefania Crishani &nbsp;&middot;&nbsp; CB016792",
            f"Generated {date.today().strftime('%d %B %Y')}",
        ],
    )

    # ---- 1 ----
    story += [
        h1("1. Overview"),
        p(
            "The artefact is a two-tier web application: a Python service that owns the "
            "data, the inference and the reporting, and an Angular single-page dashboard "
            "that rental staff operate. The two communicate over a JSON REST API secured "
            "with JWT bearer tokens."
        ),
        table(
            ["Layer", "Technology", "Version", "Role"],
            [
                ["Presentation", "Angular", "17.3", "Staff dashboard, standalone components"],
                ["API", "FastAPI", "0.115", "REST endpoints, validation, OpenAPI"],
                ["ORM", "SQLAlchemy", "2.0", "Declarative models, typed mappings"],
                ["Database", "SQLite", "3.x", "Development store; PostgreSQL-compatible"],
                ["Inference", "PyTorch / torchvision", "2.5 / 0.20", "EfficientNet-B3 classifier"],
                ["Detection", "Ultralytics YOLOv8", "8.3", "Phase 2 &mdash; written, not yet enabled"],
                ["Imaging", "Pillow", "11.1", "Validation, thumbnails, preprocessing"],
                ["Reporting", "ReportLab", "4.2", "Evidentiary PDF generation"],
                ["Auth", "python-jose, passlib/bcrypt", "3.3 / 1.7", "JWT issue-verify, password hashing"],
                ["Migrations", "Alembic", "1.14", "Versioned schema changes"],
                ["Testing", "pytest, httpx", "8.3 / 0.28", "20 API and integration tests"],
            ],
            [1.4, 2.4, 1.2, 3.2],
        ),
    ]

    # ---- 2 ----
    story += [
        h1("2. Architecture"),
        figure(
            diagrams.architecture_diagram(width=CONTENT_WIDTH), 1,
            "System architecture. The Angular client talks only to the FastAPI service; "
            "the service reaches persistence and inference through two narrow seams, "
            "either of which can be replaced without disturbing the other layers.",
        ),
        p(
            "Every layer depends only on the layer beneath it. The API layer never touches "
            "the filesystem or a model directly; it calls a service. Services never import "
            "a concrete predictor; they call <font face='Courier'>get_predictor()</font> and "
            "receive something satisfying the <font face='Courier'>Predictor</font> "
            "interface."
        ),
    ]

    # ---- 3 ----
    story += [
        h1("3. Backend components"),
        table(
            ["Package", "Responsibility"],
            [
                ["<font face='Courier'>app/api/v1/</font>",
                 "Eight routers: auth, users, vehicles, inspections, images, comparisons, "
                 "dashboard, system. 35 endpoints, all documented via OpenAPI."],
                ["<font face='Courier'>app/core/</font>",
                 "Settings (pydantic-settings), JWT and bcrypt helpers, and the damage "
                 "taxonomy &mdash; class names, thresholds, colours, per-class test metrics."],
                ["<font face='Courier'>app/db/</font>",
                 "Engine and session factory, declarative base, schema creation and "
                 "first-run seeding."],
                ["<font face='Courier'>app/models/</font>",
                 "Five entities: User, Vehicle, Inspection, InspectionImage, Detection."],
                ["<font face='Courier'>app/schemas/</font>",
                 "Pydantic request/response contracts, decoupled from the ORM so internal "
                 "columns are never exposed by accident."],
                ["<font face='Courier'>app/services/</font>",
                 "storage (validate, hash, thumbnail), analysis (run inference, persist "
                 "findings), comparison (pre/post delta), report (PDF generation)."],
                ["<font face='Courier'>app/ml/</font>",
                 "The Predictor abstraction and its three implementations, plus the "
                 "registry that selects one at startup."],
            ],
            [1.9, 5.7],
        ),
        h2("Data model"),
        figure(
            diagrams.data_model_diagram(width=CONTENT_WIDTH), 2,
            "Data model. Five entities: every finding traces back through an image to an "
            "inspection, an inspector and a vehicle.",
        ),
        p(
            "<font face='Courier'>rental_ref</font> is what pairs a pre-rental inspection "
            "with its post-rental counterpart, and is the key the comparison endpoint uses. "
            "<font face='Courier'>sha256</font> is computed once at upload and never "
            "recomputed, giving each finding a verifiable link to the bytes analysed."
        ),
    ]

    # ---- 4 ----
    story += [
        PageBreak(),
        h1("4. Frontend components"),
        table(
            ["Area", "Contents"],
            [
                ["<font face='Courier'>core/</font>",
                 "Typed API models mirroring the backend schemas; ApiService (all HTTP); "
                 "AuthService (signal-based session state); a functional HTTP interceptor "
                 "that attaches the bearer token and signs out on 401; route guards."],
                ["<font face='Courier'>features/</font>",
                 "Lazy-loaded routes: login, dashboard, fleet list and detail, inspection "
                 "list / create / detail, pre-post comparison."],
                ["<font face='Courier'>shared/</font>",
                 "ConfidenceBar (score against its own threshold), DamageChip, StatusBadge, "
                 "AuthImage and AnnotatedImage (fetch authenticated bytes, draw findings)."],
                ["<font face='Courier'>layout/</font>",
                 "Application shell: sidebar navigation, top bar, responsive drawer."],
            ],
            [1.5, 6.1],
        ),
        p("Angular 17 features used deliberately:"),
    ]
    story += bullets([
        "<b>Standalone components</b> throughout &mdash; no NgModules.",
        "<b>Signals</b> for component state, with <font face='Courier'>computed()</font> "
        "for derived values.",
        "<b>Functional interceptors and guards</b>, the modern replacement for class-based "
        "ones.",
        "<b>Lazy route loading</b> &mdash; each feature is a separate bundle; the initial "
        "download is 84 kB compressed.",
        "<b>Component input binding</b> from route parameters, avoiding manual "
        "ActivatedRoute plumbing.",
    ])

    # ---- 5 ----
    story += [
        h1("5. The inference abstraction"),
        p(
            "This is the load-bearing design decision. Section 2.6 of the proposal invokes "
            "Sculley et al. (2015) on hidden technical debt: the risk is the model becoming "
            "<i>entangled</i> with the surrounding application, so that changing one forces "
            "changes to the other. The response here is a narrow interface &mdash; bytes "
            "in, a structured result out:"
        ),
        code(
            "class Predictor(ABC):\n"
            "    @abstractmethod\n"
            "    def predict(self, image_bytes: bytes) -> PredictionResult: ...\n"
            "\n"
            "    @property\n"
            "    def is_real(self) -> bool:   # False for stand-ins\n"
            "        return True"
        ),
        table(
            ["Implementation", "Weights required", "Output", "Status"],
            [
                ["<font face='Courier'>MockPredictor</font>", "None",
                 "Deterministic scores from a hash of the bytes", "Active by default"],
                ["<font face='Courier'>EfficientNetClassifier</font>",
                 "<font face='Courier'>car_damage_classifier.pth</font>",
                 "Six image-level class scores", "Ready; awaiting weights"],
                ["<font face='Courier'>YoloDetector</font>",
                 "<font face='Courier'>yolov8_damage.pt</font>",
                 "Class scores <b>with bounding boxes</b>", "Written; Phase 2"],
            ],
            [2.1, 2.2, 2.4, 1.7],
        ),
        p(
            "Selection is automatic: detector, then classifier, then mock &mdash; the first "
            "that loads wins. Consequently a clean checkout runs end-to-end with no "
            "weights, and gains real inference simply by a file appearing in "
            "<font face='Courier'>backend/models/</font>."
        ),
        callout(
            "<b>Why the mock is deterministic.</b> Scores derive from a SHA-256 of the image "
            "bytes, so the same photograph always scores identically. Random scores would "
            "make the pre/post comparison meaningless and the test suite flaky. "
            "<font face='Courier'>is_real</font> is False, and every surface that renders a "
            "prediction &mdash; dashboard, inspection, comparison, both PDFs &mdash; reads "
            "that flag and warns the user.",
            kind="ok",
        ),
    ]

    # ---- 6 ----
    story += [
        PageBreak(),
        h1("6. Damage taxonomy and measured performance"),
    ]

    evaluation = load_evaluation()
    training = load_training()

    if evaluation:
        rows = []
        for name in CLASS_ORDER:
            entry = evaluation["per_class"].get(name)
            if not entry:
                continue
            threshold = evaluation.get("thresholds", {}).get(name, 0.5)
            rows.append([
                name,
                f"{threshold:.3f}",
                str(entry["support"]),
                f"{entry['precision']:.3f}",
                f"{entry['recall']:.3f}",
                f"<b>{entry['f1']:.3f}</b>",
                f"{entry.get('average_precision', 0):.3f}",
                f"{entry.get('roc_auc', 0):.3f}",
            ])
        macro = evaluation["macro"]
        rows.append([
            "<b>macro average</b>", "", "",
            f"{macro['precision']:.3f}", f"{macro['recall']:.3f}",
            f"<b>{macro['f1']:.3f}</b>",
            f"{macro['average_precision']:.3f}", f"{macro['roc_auc']:.3f}",
        ])

        story += [
            p(
                "Six CarDD classes (Wang et al., 2023). The figures below were "
                "<b>measured</b>, not transcribed: "
                f"{evaluation['images']} images from the held-out "
                f"<i>{evaluation['split']}</i> split were scored through the deployed "
                "predictor by <font face='Courier'>training/evaluate.py</font> on "
                f"{evaluation.get('evaluated_at', 'the date recorded in the report')}."
            ),
            table(
                ["Class", "Thresh", "Support", "Precision", "Recall", "F1", "AP", "ROC-AUC"],
                rows,
                [1.9, 1.0, 1.1, 1.2, 1.0, 0.9, 0.9, 1.1],
            ),
            p(
                f"Exact-match ratio {evaluation['exact_match_ratio']:.3f} "
                "(all six classes simultaneously correct) and any-damage accuracy "
                f"{evaluation['any_damage_accuracy']:.3f} (damaged versus clean, the "
                "operationally relevant question). Inference latency "
                f"{evaluation['latency_ms']['mean']:.0f} ms mean, "
                f"{evaluation['latency_ms']['p95']:.0f} ms at the 95th percentile.",
            ),
        ]
    else:
        story += [
            p(
                "Six CarDD classes (Wang et al., 2023), each with the F1-optimal threshold "
                "found by the original notebook's precision-recall sweep. <b>These are the "
                "pre-fix baseline</b> - produced by the run in which the backbone was "
                "accidentally frozen (Section 8) - and are shown here only until "
                "<font face='Courier'>training/evaluate.py</font> has been run against a "
                "retrained checkpoint."
            ),
            table(
                ["Class", "Threshold", "F1 @ 0.5", "F1 @ tuned", "ROC-AUC"],
                [
                    [name,
                     f"{NOTEBOOK_BASELINE[name]['threshold']:.3f}",
                     f"{NOTEBOOK_BASELINE[name]['f1_at_0.5']:.3f}",
                     f"{NOTEBOOK_BASELINE[name]['f1']:.3f}",
                     f"{NOTEBOOK_BASELINE[name]['roc_auc']:.3f}"]
                    for name in CLASS_ORDER
                ],
                [2.0, 1.3, 1.3, 1.3, 1.3],
            ),
        ]

    if training:
        story += [
            p(
                f"Training: {training.get('epochs_run', training.get('epochs', '?'))} epochs run "
                f"of {training.get('epochs_requested', '?')} requested (early stopping), on "
                f"<font face='Courier'>{training['device']}</font>, batch size "
                f"{training['batch_size']}, {training['trainable_parameters']:,} trainable "
                f"parameters. The retained checkpoint is epoch "
                f"{training.get('best_epoch', '?')} "
                f"(validation loss {training.get('best_val_loss', '?')}); later epochs "
                f"overfitted."
            ),
        ]

    story += [
        p(
            "Per-class thresholds are not a refinement. Each class is reported positive only "
            "above its own F1-optimised cut-off, because a single flat 0.5 measurably "
            "underperforms on the rarer classes. The backend owns this table and serves it at "
            "<font face='Courier'>GET /api/v1/damage-classes</font>, so the dashboard renders "
            "thresholds, labels and colours from the same source the model is scored against "
            "and cannot drift from it."
        ),
    ]

    story += [
        h1("7. Deviations from the proposal"),
        p(
            "Three architectural choices differ from Section 3.7 of the proposal. Each is "
            "deliberate and each is reversible."
        ),
        h3("7.1 The .NET 8 tier was removed"),
        p(
            "The proposal places a .NET 8 Web API between the Angular client and a FastAPI "
            "inference microservice. This implementation collapses those tiers into one "
            "Python service."
        ),
        p(
            "The isolation the proposal argues for is preserved: inference sits behind the "
            "<font face='Courier'>Predictor</font> interface, and nothing outside "
            "<font face='Courier'>app/ml/</font> knows which backend is answering. What is "
            "removed is a network hop and a language boundary that bought no isolation the "
            "interface does not already provide. What is genuinely lost is the "
            ".NET-to-Angular integration pattern named in research sub-question 3 &mdash; "
            "this should be stated in the dissertation as a scope decision rather than left "
            "for a reader to notice."
        ),
        h3("7.2 SQLite in place of SQL Server, local files in place of Azure Blob"),
        p(
            "Both are single-module swaps. The ORM layer avoids every SQLite-specific "
            "construct, so <font face='Courier'>DATABASE_URL</font> can point at PostgreSQL "
            "or SQL Server without touching a model. All file access goes through "
            "<font face='Courier'>app/services/storage.py</font>, so blob storage means "
            "reimplementing one module. The benefit is that the prototype needs no "
            "infrastructure at all to run &mdash; relevant for a supervisor demonstration "
            "or a usability study on a laptop."
        ),
        h3("7.3 Classification now, detection later"),
        p(
            "The proposal specifies YOLOv8 with localised bounding boxes; the notebook "
            "delivers image-level multi-label classification. The system is built so that "
            "gap closes at zero cost: <font face='Courier'>Detection</font> carries four "
            "nullable bbox columns, the API returns "
            "<font face='Courier'>bbox: null</font> or a normalised box within the same "
            "response shape, and the annotated-image component already draws boxes when "
            "they are present. Enabling detection is a checkpoint file plus a restart "
            "&mdash; no migration, no API version change, no frontend change."
        ),
    ]

    # ---- 8 ----
    story += [
        PageBreak(),
        h1("8. A defect found in the training notebook"),
        p(
            "While porting <font face='Courier'>car-damage-classification.ipynb</font> to a "
            "reproducible script, a substantive bug surfaced. The layer-unfreezing block "
            "intends to fine-tune the last three EfficientNet blocks:"
        ),
        code(
            "if 'feature.6' in name or 'feature.7' in name or 'feature.8' in name:\n"
            "    param.requires_grad = True"
        ),
        p(
            "torchvision names these modules <font face='Courier'>features.6</font>, not "
            "<font face='Courier'>feature.6</font>. <b>The condition never matches.</b> The "
            "notebook's own output confirms it: 790,022 trainable parameters, which is "
            "exactly the replacement classifier head "
            "(1536&times;512 + 512 + 512&times;6 + 6) and nothing else."
        ),
        callout(
            "<b>Consequence.</b> The entire convolutional backbone remained frozen, so no "
            "fine-tuning of visual features took place. The reported metrics are those of a "
            "<i>linear probe on frozen ImageNet features</i>, not of a fine-tuned model. "
            "This is the most likely explanation for <font face='Courier'>crack</font> "
            "performing worst (F1 0.47, AP 0.37): cracks depend most on adapting low-level "
            "texture representations, which is precisely what was never trained."
        ),
        p(
            "<font face='Courier'>backend/training/train_classifier.py</font> corrects this "
            "(matching on <font face='Courier'>features.{i}.</font>) and is otherwise a "
            "faithful port. Retraining should improve the reported figures, and the "
            "before/after contrast is a legitimate result for the evaluation chapter."
        ),
    ]

    # ---- 9 ----
    story += [
        h1("8b. A dataset gap, and why it mattered more than the architecture"),
        p(
            "CarDD is a dataset for deciding <i>which</i> damage a photograph shows. Every one "
            "of its 4,000 images contains damage:"
        ),
        code(
            "train: 2816 images, 2816 with damage annotations,   0 with none\n"
            "val  :  810 images,  810 with damage annotations,   0 with none\n"
            "test :  374 images,  374 with damage annotations,   0 with none"
        ),
        p(
            "A model trained on it alone never observes an undamaged vehicle, so it has no "
            "representation of \u2018no damage\u2019. Asked about a clean car it returns "
            "whichever class clears its threshold first \u2014 all six scores collapse toward "
            "0.5, and the class with the lowest tuned threshold wins."
        ),
        h2("How it surfaced, and why the metrics hid it"),
        p(
            "The first trained model reported macro F1 0.786 and \u2018any-damage accuracy\u2019 "
            "0.987 on the held-out split. Both were correctly computed. Both were blind to this "
            "failure, because <b>the test split contained no undamaged cars either</b>: a metric "
            "measured over exclusively-damaged images cannot express a false-alarm rate, so "
            "\u2018any-damage accuracy\u2019 was measuring recall alone while being labelled as "
            "though it measured both directions."
        ),
        p(
            "It surfaced when a photograph of an undamaged Ford Mustang was uploaded through the "
            "dashboard and returned <i>Dent, 75.8%</i>. Re-evaluating against 269 clean cars "
            "quantified it:"
        ),
        table(
            ["Metric", "Damaged images only", "With clean cars in the test set"],
            [
                ["Macro F1", "0.786", "<b>0.677</b>"],
                ["dent precision", "0.799", "<b>0.344</b>"],
                ["scratch precision", "0.747", "<b>0.563</b>"],
                ["False alarms on clean cars", "not measurable", "<b>238 / 269 (88.5%)</b>"],
            ],
            [2.6, 2.2, 2.8],
        ),
        h2("The correction"),
    ]
    story += bullets([
        "<b>Negative examples added.</b> 2,681 photographs of undamaged vehicles (Stanford "
        "Cars) train with an all-zero label vector, split 70/20/10 in CarDD's own proportions "
        "so the false-alarm rate is measured on clean cars held out from training.",
        "<b>Loss weighting left alone.</b> Class weights are computed over the damaged subset "
        "only. Including the negatives would have roughly doubled every positive weight and "
        "pushed the model toward predicting damage more often \u2014 the opposite of the "
        "intent. The negatives contribute by example, not by reweighting.",
        "<b>The metric was renamed and gated.</b> `evaluate.py` reports an explicit "
        "false-alarm rate, and refuses to describe its headline figure as \u2018damaged versus "
        "clean\u2019 when no clean images are present. The dashboard shows the same, and warns "
        "when the rate is unmeasured rather than implying a pass.",
    ])
    story += [
        callout(
            "<b>For the dissertation.</b> The proposal (Section 3.3) already anticipated this: "
            "it lists five classes including <i>no-damage/background</i>. CarDD supplies no such "
            "class. The gap between the annotation schema the proposal specified and the one the "
            "public dataset provides is a real, citable finding \u2014 and a concrete instance "
            "of the deployment-gap argument in Section 2.6, where a model with strong benchmark "
            "numbers fails on the first input a real operator would give it."
        ),
        Spacer(1, 4),
                h1("9. Security"),
        table(
            ["Concern", "Measure"],
            [
                ["Password storage", "bcrypt via passlib; inputs capped at 72 bytes so the "
                 "algorithm cannot silently truncate and hash a prefix"],
                ["Session", "HS256 JWT, 8-hour expiry, verified on every protected request"],
                ["Authorisation", "Two roles. Inspectors may read all records but modify "
                 "only their own; user management and vehicle deletion are admin-only"],
                ["Upload validation", "Format determined by decoding the image, never from "
                 "the client-supplied content type or filename extension"],
                ["Path safety", "Stored filenames are server-generated UUIDs; the client "
                 "never supplies a path component"],
                ["Media access", "Photographs require a bearer token; the client fetches "
                 "bytes over XHR and binds an object URL"],
                ["CORS", "Explicit origin allow-list, configurable per environment"],
                ["Self-lockout", "An administrator cannot deactivate their own account or "
                 "change their own role"],
            ],
            [1.8, 5.8],
        ),
        callout(
            "The default <font face='Courier'>SECRET_KEY</font> and both seeded passwords "
            "are development placeholders published in the source. They must be changed "
            "before the system runs anywhere reachable by others."
        ),
    ]

    # ---- 10 ----
    story += [
        h1("10. Quality and known limitations"),
        h2("Verification"),
    ]
    story += bullets([
        "<b>20 backend tests</b>, all passing: authentication, role enforcement, "
        "registration normalisation, upload rejection, the full create-upload-analyse-"
        "report flow, analysis idempotency, mock determinism, and every comparison outcome.",
        "<b>Angular production build</b> clean, with no warnings or errors.",
        "<b>Alembic migration</b> verified to apply and roll back on a fresh database.",
    ])
    story += [
        h2("Limitations"),
        table(
            ["Limitation", "Impact and remedy"],
            [
                ["Synchronous inference",
                 "A large upload batch blocks the request; roughly 0.3&ndash;1 s per image "
                 "on CPU with real weights. A task queue is the fix if the usability study "
                 "exercises large batches."],
                ["Local filesystem storage",
                 "Not durable or shared across instances. Replace "
                 "<font face='Courier'>app/services/storage.py</font> with a blob backend."],
                ["Severity is heuristic",
                 "Derived from threshold headroom; the model has no severity supervision. "
                 "Labelled as a hint everywhere it appears, including in PDFs."],
                ["No cross-image deduplication",
                 "The same dent photographed from four angles counts as four pieces of "
                 "evidence for that class."],
                ["Image-level findings only",
                 "Until YOLOv8 weights exist, a finding names a photograph, not a location "
                 "on the panel."],
                ["Single-node deployment",
                 "SQLite and local files suit a prototype and a small usability study, not "
                 "concurrent production use."],
            ],
            [2.0, 5.6],
        ),
    ]

    doc.build(story)
    print(f"Wrote {OUT / 'TECH_STACK.pdf'}")


if __name__ == "__main__":
    build_manual()
    build_tech_stack()
