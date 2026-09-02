"""Generate FEATURE_GUIDE.pdf - what the system does and how to test it.

Written for someone with no technical background: rental staff, a supervisor,
an examiner. It assumes the system is already running (that is the User Manual's
job) and covers only what you can see and click.

    ../backend/.venv/bin/python build_feature_guide.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# Reuse the shared look so all three documents match.
from build_docs import (  # noqa: E402
    BRAND,
    BRAND_LIGHT,
    CONTENT_WIDTH,
    MUTED,
    OUT,
    RULE,
    S,
    bullets,
    callout,
    code,
    cover_page,
    h1,
    h2,
    h3,
    make_doc,
    p,
    steps,
    table,
)

EVALUATION = OUT.parent / "backend" / "models" / "evaluation.json"


def metrics() -> dict:
    """Read the measured numbers so the guide never quotes stale figures."""
    if EVALUATION.exists():
        try:
            return json.loads(EVALUATION.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {}


def test_step(number: str, title: str, actions: list[str], expected: list[str]) -> KeepTogether:
    """One acceptance test: what to do, what should happen, and a box to tick."""
    flow = [
        Paragraph(f"<b>Test {number} &mdash; {title}</b>", S["h3"]),
        Paragraph("<b>Do this:</b>", S["small"]),
    ]
    flow += [Paragraph(a, S["bullet"], bulletText=f"{i}.") for i, a in enumerate(actions, 1)]
    flow += [Spacer(1, 3), Paragraph("<b>You should see:</b>", S["small"])]
    flow += [Paragraph(e, S["bullet"], bulletText="\u2013") for e in expected]

    verdict = Table(
        [[Paragraph("<b>Result:</b> &nbsp;&nbsp; [ &nbsp; ] Works &nbsp;&nbsp;&nbsp; "
                    "[ &nbsp; ] Does not work &nbsp;&nbsp;&nbsp; "
                    "Notes: _________________________________________", S["small"])]],
        colWidths=[CONTENT_WIDTH],
    )
    verdict.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8FB")),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    flow += [Spacer(1, 4), verdict, Spacer(1, 12)]
    return KeepTogether(flow)


def feature_row(name: str, what: str, where: str) -> list:
    return [Paragraph(f"<b>{name}</b>", S["cell"]),
            Paragraph(what, S["cell"]),
            Paragraph(where, S["cell"])]


def build() -> None:
    m = metrics()
    fa = m.get("false_alarm_rate")
    fa_text = f"{fa * 100:.1f}%" if fa is not None else "not yet measured"
    clean_n = m.get("clean_images", "?")
    macro_f1 = m.get("macro", {}).get("f1", "?")
    dvc = m.get("any_damage_accuracy", "?")
    n_images = m.get("images", "?")

    doc = make_doc(
        OUT / "FEATURE_GUIDE.pdf",
        "Feature Guide & Test Script - Vehicle Damage Inspection",
        "What the system does, and how to check that it does it",
    )
    story = cover_page(
        "Feature Guide<br/>&amp; Test Script",
        "What the system does, and how to check that it does it",
        [
            "Written for anyone &mdash; no technical background needed",
            "Automated Pre- and Post-Rental Passenger Car Damage Inspection",
            "MSc Dissertation Prototype &mdash; APIIT Sri Lanka",
            "Stefania Crishani &nbsp;&middot;&nbsp; CB016792",
            f"Generated {date.today().strftime('%d %B %Y')}",
        ],
    )

    # ---------------- Introduction ----------------
    story += [
        h1("Before you begin"),
        p(
            "This booklet has two halves. The first describes <b>what the system can do</b>, "
            "in plain language. The second is a <b>test script</b>: a numbered list of things "
            "to try, what should happen each time, and a box to tick. Work through it in order "
            "and you will have exercised every feature."
        ),
        p("You do not need to understand how it works to use this booklet. You need only:"),
    ]
    story += bullets([
        "A web browser.",
        "The system already running &mdash; someone should have started it for you. If the "
        "address below does not load, ask them; that part is covered in the User Manual.",
        "About 20 minutes.",
    ])
    story += [
        Spacer(1, 6),
        table(
            ["What", "Value"],
            [
                ["Address", "<font face='Courier'>http://localhost:4200</font>"],
                ["Email", "<font face='Courier'>admin@drivetime.lk</font>"],
                ["Password", "<font face='Courier'>ChangeMe123!</font>"],
            ],
            [1.6, 6.0],
        ),
        callout(
            "<b>You cannot break anything.</b> This is a practice system with made-up vehicles "
            "and rentals. Add, photograph and delete whatever you like. If it ever gets into a "
            "state you dislike, whoever set it up can reset it in one command.",
            kind="ok",
        ),
    ]

    # ---------------- The problem ----------------
    story += [
        h1("1. What problem this solves"),
        p(
            "When a rental car goes out and comes back, someone walks around it looking for "
            "damage. That takes up to fifteen minutes, depends on the light, the inspector's "
            "eyesight and how long their shift has been, and produces notes that are hard to "
            "compare later. When a customer disputes a charge, there is often no clear record "
            "of what the car looked like when it left."
        ),
        p("This system does three things about that:"),
    ]
    story += bullets([
        "<b>It looks at your photographs and names the damage it sees</b> &mdash; dents, "
        "scratches, cracks, shattered glass, broken lamps, flat tyres.",
        "<b>It compares the car before and after the rental</b> and tells you which damage is "
        "new and which was already there.",
        "<b>It produces a PDF report</b> you can put in the rental file or hand to a customer.",
    ])
    story += [
        callout(
            "<b>It assists; it does not decide.</b> Every finding is meant to be confirmed by a "
            "person before it reaches a customer. The system is a second pair of eyes that "
            "never gets tired and always writes things down &mdash; not a replacement for "
            "yours."
        ),
    ]

    # ---------------- Feature catalogue ----------------
    story += [
        PageBreak(),
        h1("2. Everything the system can do"),
        p("The five items down the left-hand side of the screen are the whole system."),
        table(
            ["Where", "What it is for"],
            [
                feature_row("Dashboard", "The overview you land on. How many inspections have "
                                        "been done, what damage has been found across the "
                                        "fleet, and the most recent checks.", "")[:2] + [
                    Paragraph("Landing page", S["cell"])],
                feature_row("Inspections", "Every condition check ever recorded, with filters "
                                          "for pre-rental, post-rental, and by rental "
                                          "reference.", "Sidebar"),
                feature_row("Fleet", "The vehicles you can inspect. Add new ones, search, and "
                                     "open any vehicle to see its full history.", "Sidebar"),
                feature_row("Pre / post", "The comparison screen. Choose a vehicle and it tells "
                                          "you what damage is new since handover.", "Sidebar"),
                feature_row("Model", "How accurate the system has been measured to be, "
                                     "including what it gets wrong.", "Sidebar"),
            ],
            [1.5, 4.8, 1.3],
        ),
        h2("2.1 Recording an inspection"),
    ]
    story += bullets([
        "<b>Two kinds of inspection.</b> <i>Pre-rental</i> is the condition at handover. "
        "<i>Post-rental</i> is the condition on return.",
        "<b>A rental reference ties them together.</b> Type the same reference on both and the "
        "system knows they are two halves of one rental. This is the single most important "
        "field on the form.",
        "<b>Photographs are dragged in</b>, several at once. You tell it which angle each batch "
        "was taken from, so the report says 'Driver side' rather than 'photo 3'.",
        "<b>Analysis happens automatically</b> when you upload. Results appear in a second or "
        "two per photograph.",
        "<b>Odometer, location and notes</b> are optional, and go on the report.",
    ])
    story += [
        h2("2.2 Reading the findings"),
        p(
            "Each photograph gets a row per damage type with a coloured bar. Two things on that "
            "bar matter:"
        ),
    ]
    story += bullets([
        "<b>The coloured bar</b> is how confident the system is.",
        "<b>The small grey tick mark</b> is the level that type of damage has to reach before "
        "it counts. Each type has its own mark, because some are easier to spot than others. "
        "Only a bar that reaches its own tick is reported as damage.",
    ])
    story += [
        p(
            "Damage that is reported appears in full colour and is listed at the top of the "
            "inspection. Everything else is greyed out. Hover over any damage name and it will "
            "tell you how reliable the system is at spotting that particular type."
        ),
        p(
            "<b>Severity</b> (minor / moderate / severe) is a rough hint based on how confident "
            "the system is &mdash; not a measurement of how big the damage is. Treat it as a "
            "nudge about where to look first, nothing more."
        ),
        h2("2.3 The comparison &mdash; what this is really for"),
        p("Choose a vehicle on the <b>Pre / post</b> screen and it sorts damage into three:"),
        table(
            ["Outcome", "Plain meaning", "Charge the customer?"],
            [
                ["<b>New this rental</b>", "Not there at handover; there on return.",
                 "<b>Yes</b> &mdash; it happened during the rental."],
                ["<b>Pre-existing</b>", "Was already there when the car went out.",
                 "No &mdash; not their doing."],
                ["<b>Not detected on return</b>",
                 "Seen at handover but not on return. Usually repaired, or photographed from a "
                 "different angle.", "No."],
            ],
            [1.6, 3.6, 2.4],
        ),
        h2("2.4 Reports"),
    ]
    story += bullets([
        "<b>Inspection report</b> &mdash; one vehicle, one check. The record, the vehicle, the "
        "damage found with confidence figures, and a page of the photographs.",
        "<b>Comparison report</b> &mdash; before and after side by side, with new damage "
        "highlighted in red. This is the one to attach to a disputed charge.",
    ])
    story += [
        p(
            "Every photograph carries a long code called a <i>fingerprint</i>, recorded the "
            "moment it is uploaded. If anyone ever asks whether the picture in the report is "
            "really the picture that was examined, that code is the proof."
        ),
        h2("2.5 Accounts"),
        table(
            ["Account", "What they can do"],
            [
                ["<b>Inspector</b>", "Run inspections, view everything, edit their own records."],
                ["<b>Administrator</b>", "All of that, plus manage users and edit anyone's "
                                         "records."],
            ],
            [1.6, 6.0],
        ),
    ]

    # ---------------- Honest limits ----------------
    story += [
        h1("3. What it is <i>not</i> good at"),
        p(
            "Knowing the weak spots is part of using it properly. None of this is hidden in the "
            "system &mdash; it is all on the <b>Model</b> page."
        ),
        table(
            ["Limitation", "What it means for you"],
            [
                ["<b>Cracks are often missed</b>",
                 "It finds fewer than half of them. Cracks are thin and low-contrast. Check for "
                 "cracks yourself; do not rely on the system for these."],
                ["<b>It sometimes adds a damage type that is not there</b>",
                 "Usually 'scratch' alongside a correct finding. Look at the photograph before "
                 "acting on any single finding."],
                ["<b>It only sees what you photograph</b>",
                 "An unphotographed panel is not an undamaged panel. Photograph everything you "
                 "would check by hand."],
                ["<b>It does not measure size or cost</b>",
                 "It says 'there is a dent', not 'the dent is 4cm' or 'this costs £200'."],
                ["<b>It does not read number plates or identify people</b>",
                 "By design. It records vehicle condition only."],
            ],
            [2.2, 5.4],
        ),
    ]

    # ---------------- TEST SCRIPT ----------------
    story += [
        PageBreak(),
        h1("4. Test script"),
        p(
            "Work through these in order. Each one says what to do and what should happen. Tick "
            "the box, and write a note if something looks wrong. Tests 1 to 8 cover normal use; "
            "9 to 12 check that the system is honest about its own accuracy."
        ),
        callout(
            "Tests 9 to 12 are the important ones if you are deciding whether to trust this "
            "system. Anyone can make a demo look good; these check whether it tells you the "
            "truth about itself.",
        ),
        Spacer(1, 6),
        h2("Part A &mdash; Everyday use"),
        test_step(
            "1", "Signing in",
            ["Open <font face='Courier'>http://localhost:4200</font> in your browser.",
             "Click the <b>admin&#64;drivetime.lk</b> row under <i>Seeded accounts</i> "
             "&mdash; it fills the form for you.",
             "Click <b>Sign in</b>."],
            ["The dashboard appears, with your name at the top right.",
             "Five items down the left: Dashboard, Inspections, Fleet, Pre / post, Model."],
        ),
        test_step(
            "2", "The dashboard tells you something useful",
            ["Look at the four boxes across the top.",
             "Look at <b>Damage detected across the fleet</b>.",
             "Click any row under <b>Recent inspections</b>."],
            ["The four boxes show counts, not zeroes or blanks.",
             "The damage chart lists damage types with coloured bars.",
             "Clicking a row opens that inspection."],
        ),
        test_step(
            "3", "Adding a vehicle",
            ["Click <b>Fleet</b>, then <b>+ Add vehicle</b>.",
             "Registration <font face='Courier'>test-0001</font>, make "
             "<font face='Courier'>Toyota</font>, model <font face='Courier'>Corolla</font>.",
             "Click <b>Save vehicle</b>."],
            ["The vehicle appears in the list as <b>TEST-0001</b> &mdash; it is tidied to "
             "capitals automatically.",
             "Trying to add the same registration again is refused."],
        ),
        test_step(
            "4", "Recording a handover (pre-rental)",
            ["Click <b>+ New inspection</b>.",
             "Choose <b>Pre-rental</b>, pick <b>TEST-0001</b>.",
             "Rental reference: <font face='Courier'>TEST-100</font>. Remember it.",
             "Click <b>Create and add photographs</b>.",
             "Choose a capture angle, then drag in two or three car photographs and click "
             "<b>Upload and analyse</b>."],
            ["Each photograph appears with a list of damage types and coloured bars.",
             "Anything found is listed at the top under <b>Damage detected</b>.",
             "The status changes to <b>Completed</b>."],
        ),
        test_step(
            "5", "Recording the return (post-rental)",
            ["Click <b>+ New inspection</b> again.",
             "Choose <b>Post-rental</b>, the same vehicle <b>TEST-0001</b>.",
             "Rental reference: <font face='Courier'>TEST-100</font> &mdash; exactly the same "
             "as before.",
             "Upload some different photographs, ideally of a more damaged car."],
            ["A second inspection is created for the same vehicle.",
             "Both now appear in the vehicle's history."],
        ),
        test_step(
            "6", "The comparison &mdash; the main event",
            ["Click <b>Pre / post</b> in the sidebar.",
             "Choose <b>TEST-0001</b>, type <font face='Courier'>TEST-100</font>, click "
             "<b>Compare</b>."],
            ["A verdict panel says whether new damage was found.",
             "A <b>Damage delta</b> table lists each damage type as <i>New this rental</i>, "
             "<i>Pre-existing</i> or <i>Not detected on return</i>.",
             "New damage rows are highlighted in red.",
             "Both sets of photographs appear side by side underneath."],
        ),
        test_step(
            "7", "Exporting a report",
            ["Open any inspection and click <b>Export PDF</b>.",
             "Go back to <b>Pre / post</b> and click <b>Export comparison PDF</b>.",
             "Open both files."],
            ["Both download and open as proper PDFs.",
             "They contain the vehicle, the inspector, the date, the damage found, and the "
             "photographs.",
             "The comparison report highlights new damage."],
        ),
        test_step(
            "8", "The history is kept",
            ["Click <b>Fleet</b>, then open <b>TEST-0001</b>."],
            ["Both inspections are listed with dates, types and findings.",
             "<b>Condition summary</b> reflects the most recent one."],
        ),
    ]

    # ---- Part B: honesty checks ----
    story += [
        PageBreak(),
        h2("Part B &mdash; Is it telling you the truth?"),
        p(
            "These four tests are what separate a system you can rely on from one that merely "
            "looks impressive."
        ),
        test_step(
            "9", "It publishes its own accuracy, including its failures",
            ["Click <b>Model</b> in the sidebar.",
             "Read the boxes across the top.",
             "Scroll to <b>Spot check</b> and click <b>Mistakes only</b>."],
            [f"It reports being tested on {n_images} photographs it had never seen before.",
             f"<b>Damaged vs clean</b> is about {dvc}, and <b>Macro F1</b> about {macro_f1}.",
             "The per-class table shows one damage type scoring clearly worse than the others "
             "(crack) &mdash; it does not hide this.",
             "<b>Mistakes only</b> lists photographs it got wrong, beside the correct answer. "
             "A system that could not show you its mistakes would not be trustworthy."],
        ),
        test_step(
            "10", "It does not cry wolf on an undamaged car",
            ["On the <b>Model</b> page, find the <b>False alarms</b> box.",
             "Then: photograph a car with no damage &mdash; any clean car, your own phone is "
             "fine.",
             "Create an inspection and upload that photograph."],
            [f"The <b>False alarms</b> box shows about <b>{fa_text}</b>, measured over "
             f"{clean_n} undamaged cars, and is green.",
             "Your own clean car photograph comes back with <b>no damage reported</b>.",
             "<b>If it reports damage on a clean car, stop and tell whoever set this up.</b> "
             "That is the most serious failure this system can have &mdash; it would mean "
             "accusing customers of damage they did not cause."],
        ),
        test_step(
            "11", "It gives the same answer twice",
            ["Upload the same photograph to two different inspections.",
             "Compare the percentages on each."],
            ["The percentages are identical, digit for digit.",
             "If the same photograph gave different answers on different days, no report based "
             "on it could be defended in a dispute."],
        ),
        test_step(
            "12", "It gets known photographs right",
            ["Ask whoever set the system up for the <b>verification pack</b> &mdash; a folder "
             "of photographs with a written answer key.",
             "Create an inspection and upload all of them.",
             "Compare each result against the answer key."],
            ["It finds the real damage in nearly every photograph.",
             "Where it is wrong, it has usually <i>added</i> an extra damage type rather than "
             "missed the real one.",
             "It is noticeably weaker on cracks &mdash; expected, and stated on the Model page."],
        ),
    ]

    # ---------------- Glossary ----------------
    story += [
        PageBreak(),
        h1("5. Words you will see, in plain English"),
        table(
            ["Term", "What it means"],
            [
                ["<b>Pre-rental</b>", "The check done when the car goes out to a customer."],
                ["<b>Post-rental</b>", "The check done when it comes back."],
                ["<b>Rental reference</b>",
                 "A code you invent that links the two checks of one rental. Use the same one "
                 "on both."],
                ["<b>Confidence</b>",
                 "How sure the system is, as a percentage. Higher means more sure."],
                ["<b>Threshold</b>",
                 "The level confidence must reach before something is reported as damage. Each "
                 "damage type has its own, shown as a small tick on the bar."],
                ["<b>False alarm</b>",
                 "Reporting damage on a car that has none. The failure that matters most."],
                ["<b>Precision</b>",
                 "Of the damage it reported, how much was really there. Low precision means "
                 "false accusations."],
                ["<b>Recall</b>",
                 "Of the damage that was really there, how much it found. Low recall means "
                 "missed damage."],
                ["<b>F1</b>",
                 "One number balancing precision and recall. 1.0 is perfect; below about 0.5 is "
                 "unreliable on its own."],
                ["<b>Held-out photographs</b>",
                 "Pictures deliberately kept away from the system while it was learning, so "
                 "testing it on them is a fair exam rather than a memory test."],
                ["<b>Severity hint</b>",
                 "A rough minor/moderate/severe label based on confidence. Not a measurement of "
                 "how big the damage is."],
                ["<b>Fingerprint (SHA-256)</b>",
                 "A code unique to each photograph, recorded on upload. Proves the picture in "
                 "the report is the picture that was examined."],
            ],
            [1.6, 6.0],
        ),
        h1("6. If something goes wrong"),
        table(
            ["What you see", "What to do"],
            [
                ["The page will not load, or signing in fails",
                 "The system is not running. Ask whoever set it up to start it."],
                ["An amber banner saying <i>Placeholder predictions</i>",
                 "No trained model is loaded, so all findings are meaningless. Do not use any "
                 "result until this is resolved."],
                ["It reports damage on a clearly undamaged car",
                 "Stop and report it. See Test 10."],
                ["A photograph is rejected",
                 "It must be a JPEG, PNG or WebP image under 15 MB. Photos straight from a "
                 "phone are fine."],
                ["You are signed out unexpectedly",
                 "Sessions last 8 hours. Sign in again."],
                ["You want to start over",
                 "Ask whoever set it up; it is a single command and nothing real is lost."],
            ],
            [2.4, 5.2],
        ),
        Spacer(1, 10),
        callout(
            "<b>The one rule worth remembering.</b> The system is a second pair of eyes that "
            "never gets tired and always writes things down. It is not a judge. Look at the "
            "photograph before you act on any finding, and never charge a customer on the "
            "strength of a number alone.",
            kind="ok",
        ),
    ]

    doc.build(story)
    print(f"Wrote {OUT / 'FEATURE_GUIDE.pdf'}")


if __name__ == "__main__":
    build()
