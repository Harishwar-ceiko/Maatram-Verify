"""Deterministic validation report rendered with ReportLab.

The report is built only from stored results: entered marks, findings from the
rule engine and document metadata. It never calls a model and never invents a
value that is not on the application or in the run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#171610")
INK_SOFT = colors.HexColor("#3a372f")
MUTED = colors.HexColor("#6e695c")
LINE = colors.HexColor("#c4beae")
LINE_SOFT = colors.HexColor("#ddd7c7")
PAPER = colors.HexColor("#fbfaf5")
PAPER_DEEP = colors.HexColor("#f0ebdd")
ACCENT = colors.HexColor("#a63a1b")
PASS = colors.HexColor("#1e6a4c")
FAIL = colors.HexColor("#a32318")
WARN = colors.HexColor("#8a5a00")
PASS_WASH = colors.HexColor("#e7f0ea")
FAIL_WASH = colors.HexColor("#f6e3de")
WARN_WASH = colors.HexColor("#f6edd9")

PAGE_W, PAGE_H = A4
MARGIN_X = 46
MARGIN_TOP = 44
MARGIN_BOTTOM = 48
CONTENT_W = PAGE_W - 2 * MARGIN_X

TONES = {
    "pass": (PASS, PASS_WASH),
    "review": (WARN, WARN_WASH),
    "fail": (FAIL, FAIL_WASH),
}

STATUS_LABELS = {
    "draft": "Draft",
    "submitted": "Submitted",
    "processing": "Processing",
    "needs_review": "Needs review",
    "verified": "Verified",
    "approved": "Approved",
    "rejected": "Rejected",
    "pending": "Pending",
    "running": "Running",
    "completed": "Completed",
    "failed": "Failed",
}

RESULT_LABELS = {
    "match": "Match",
    "mismatch": "Mismatch",
    "pass": "Pass",
    "fail": "Fail",
    "missing_upload": "Missing in file",
    "missing_entry": "Missing in entry",
    "skipped": "Skipped",
    "pending": "Pending",
}

RESULT_TONES = {
    "match": PASS,
    "pass": PASS,
    "mismatch": FAIL,
    "fail": FAIL,
    "missing_upload": WARN,
    "missing_entry": WARN,
    "skipped": MUTED,
    "pending": MUTED,
}


def _base_styles() -> dict[str, ParagraphStyle]:
    return {
        "kicker": ParagraphStyle(
            "kicker",
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9,
            textColor=ACCENT,
            spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "title",
            fontName="Times-Roman",
            fontSize=25,
            leading=27,
            textColor=INK,
            spaceBefore=5,
        ),
        "meta": ParagraphStyle(
            "meta",
            fontName="Helvetica",
            fontSize=7.8,
            leading=12,
            textColor=MUTED,
            alignment=TA_RIGHT,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="Times-Roman",
            fontSize=14.5,
            leading=17,
            textColor=INK,
            spaceBefore=0,
            spaceAfter=0,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=8.7,
            leading=12.4,
            textColor=INK_SOFT,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="Helvetica",
            fontSize=7.6,
            leading=10.6,
            textColor=MUTED,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica",
            fontSize=7.4,
            leading=9.4,
            textColor=MUTED,
        ),
        "value": ParagraphStyle(
            "value",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=INK,
        ),
        "th": ParagraphStyle(
            "th",
            fontName="Helvetica-Bold",
            fontSize=6.6,
            leading=8,
            textColor=MUTED,
        ),
        "th_r": ParagraphStyle(
            "th_r",
            fontName="Helvetica-Bold",
            fontSize=6.6,
            leading=8,
            textColor=MUTED,
            alignment=TA_RIGHT,
        ),
        "td": ParagraphStyle(
            "td",
            fontName="Helvetica",
            fontSize=7.9,
            leading=10.6,
            textColor=INK_SOFT,
        ),
        "td_bold": ParagraphStyle(
            "td_bold",
            fontName="Helvetica-Bold",
            fontSize=7.9,
            leading=10.6,
            textColor=INK,
        ),
        "td_r": ParagraphStyle(
            "td_r",
            fontName="Courier",
            fontSize=7.9,
            leading=10.6,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
        "stat": ParagraphStyle(
            "stat",
            fontName="Times-Roman",
            fontSize=20,
            leading=21,
            textColor=INK,
        ),
        "stat_small": ParagraphStyle(
            "stat_small",
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "verdict": ParagraphStyle(
            "verdict",
            fontName="Times-Roman",
            fontSize=11.5,
            leading=15,
            textColor=INK,
        ),
    }


def _p(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape("" if text is None else str(text)), style)


def _table_style(header: bool = True, zebra: bool = False) -> TableStyle:
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.55, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.55, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), PAPER_DEEP),
    ]
    if zebra:
        for index in range(2, 30, 2):
            commands.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#f7f4ea")))
    return TableStyle(commands)


def _status_label(value: str | None) -> str:
    if not value:
        return "Not run"
    return STATUS_LABELS.get(value, value.replace("_", " ").title())


def _result_label(value: str) -> str:
    return RESULT_LABELS.get(value, value.replace("_", " ").title())


def _result_para(value: str, style: ParagraphStyle) -> Paragraph:
    tone = RESULT_TONES.get(value, MUTED)
    return Paragraph(
        f'<font color="{tone.hexval()}"><b>{escape(_result_label(value))}</b></font>',
        style,
    )


def _format_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d %b %Y, %H:%M")


def _overall_tone(overall: str | None) -> tuple[colors.Color, colors.Color]:
    return TONES.get(overall or "", (MUTED, PAPER_DEEP))


def _page_drawing(application, run, styles):
    reference = application.reference
    issued = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    kicker = _p("MAATRAM VERIFY · ADMISSION DOCUMENT VALIDATION", styles["kicker"])
    title = _p("Validation report", styles["title"])
    meta = Paragraph(
        f'<font name="Courier">{escape(reference)}</font><br/>'
        f"Issued {escape(issued)}<br/>"
        f"Run #{run.id} · {escape(_status_label(run.status))}",
        styles["meta"],
    )
    head = Table([[title, meta]], colWidths=[CONTENT_W * 0.62, CONTENT_W * 0.38])
    head.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return [
        kicker,
        head,
        Spacer(1, 7),
        HRFlowable(width="100%", thickness=1.1, color=INK, spaceBefore=0, spaceAfter=14),
    ]


def _summary_block(application, run, styles):
    summary = run.summary or {}
    overall = run.overall or "review"
    tone, wash = _overall_tone(overall)
    verdict = summary.get("verdict") or "The checks are recorded in this report."

    stats = Table(
        [
            [
                _p("RESULT", styles["th"]),
                _p("MARKS MATCHED", styles["th"]),
                _p("MISMATCHED", styles["th"]),
                _p("FINDINGS", styles["th"]),
            ],
            [
                Paragraph(
                    f'<font color="{tone.hexval()}"><b>{escape(overall.upper())}</b></font>',
                    styles["stat"],
                ),
                _p(summary.get("matched", 0), styles["stat"]),
                _p(summary.get("mismatched", 0), styles["stat"]),
                Paragraph(
                    f'<font color="{FAIL.hexval()}">{summary.get("critical", 0)}</font> critical<br/>'
                    f'<font color="{WARN.hexval()}">{summary.get("warnings", 0)}</font> warnings',
                    styles["stat_small"],
                ),
            ],
        ],
        colWidths=[CONTENT_W * 0.25] * 4,
    )
    stats.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 1), wash),
                ("BOX", (0, 0), (-1, -1), 0.55, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE_SOFT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    band = Table(
        [[Paragraph(escape(verdict), styles["verdict"])]],
        colWidths=[CONTENT_W],
    )
    band.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), wash),
                ("LINEBEFORE", (0, 0), (0, -1), 3, tone),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [stats, Spacer(1, 6), band, Spacer(1, 16)]


def _identity_block(application, run, styles):
    summary = run.summary or {}
    rows = [
        [
            _p("Applicant", styles["label"]),
            _p(application.applicant_name, styles["value"]),
            _p("Register no.", styles["label"]),
            _p(application.register_number, styles["value"]),
        ],
        [
            _p("Programme", styles["label"]),
            _p(application.program, styles["value"]),
            _p("Examination year", styles["label"]),
            _p(application.exam_year, styles["value"]),
        ],
        [
            _p("Board", styles["label"]),
            _p(application.board or "Not stated", styles["value"]),
            _p("Application status", styles["label"]),
            _p(_status_label(application.status), styles["value"]),
        ],
        [
            _p("Checked", styles["label"]),
            _p(_format_date(run.finished_at), styles["value"]),
            _p("Read with", styles["label"]),
            _p(
                f"{(summary.get('engine') or 'tesseract').title()}"
                + (
                    f" · {summary.get('ocr_confidence')}% mean confidence"
                    if summary.get("ocr_confidence") is not None
                    else ""
                ),
                styles["value"],
            ),
        ],
    ]
    table = Table(rows, colWidths=[66, 186, 78, 173], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE_SOFT),
            ]
        )
    )
    return table


def _marks_block(application, run, styles):
    findings = [finding for finding in run.findings if finding.category == "mark"]
    if not findings:
        return [Spacer(1, 8), _p("No mark comparison was recorded for this run.", styles["body"])]

    rows = [
        [
            _p("Subject", styles["th"]),
            _p("Entered", styles["th_r"]),
            _p("Read from sheet", styles["th_r"]),
            _p("Result", styles["th"]),
            _p("Detail", styles["th"]),
        ]
    ]
    for finding in findings:
        entered = finding.entered_value or "—"
        read = finding.uploaded_value or finding.measured_value or "—"
        rows.append(
            [
                _p(finding.field, styles["td_bold"]),
                _p(entered, styles["td_r"]),
                _p(read, styles["td_r"]),
                _result_para(finding.result, styles["td"]),
                _p(finding.detail or "", styles["td"]),
            ]
        )
    table = Table(rows, colWidths=[108, 52, 66, 62, 215], repeatRows=1)
    table.setStyle(_table_style())
    return [table]


def _identity_checks_block(run, styles):
    findings = [finding for finding in run.findings if finding.category == "identity"]
    if not findings:
        return []
    rows = [
        [
            _p("Field", styles["th"]),
            _p("Entered", styles["th"]),
            _p("Printed on sheet", styles["th"]),
            _p("Result", styles["th"]),
        ]
    ]
    for finding in findings:
        measured = finding.measured_value or ""
        rows.append(
            [
                _p(finding.field, styles["td_bold"]),
                _p(finding.entered_value or "—", styles["td"]),
                _p(finding.uploaded_value or "—", styles["td"]),
                Paragraph(
                    f'{_result_label(finding.result)}'
                    + (f'<br/><font color="{MUTED.hexval()}" size="6.8">{escape(str(measured))}</font>' if measured else ""),
                    styles["td"],
                ),
            ]
        )
    table = Table(rows, colWidths=[104, 150, 140, 109], repeatRows=1)
    table.setStyle(_table_style())
    return [table]


def _photo_block(run, styles):
    findings = [finding for finding in run.findings if finding.category == "photo"]
    if not findings:
        return [_p("No photograph checks were recorded for this run.", styles["body"])]
    rows = [
        [
            _p("Check", styles["th"]),
            _p("Result", styles["th"]),
            _p("Measured", styles["th"]),
            _p("Required", styles["th"]),
            _p("Note", styles["th"]),
        ]
    ]
    for finding in findings:
        rows.append(
            [
                _p(finding.field, styles["td_bold"]),
                _result_para(finding.result, styles["td"]),
                _p(finding.measured_value or "—", styles["td"]),
                _p(finding.required_value or "—", styles["td"]),
                _p(finding.detail or "", styles["td"]),
            ]
        )
    table = Table(rows, colWidths=[79, 52, 108, 104, 160], repeatRows=1)
    table.setStyle(_table_style())
    return [table]


def _other_findings(run, styles):
    known = {"mark", "identity", "photo"}
    findings = [finding for finding in run.findings if finding.category not in known]
    if not findings:
        return None
    rows = [
        [
            _p("Category", styles["th"]),
            _p("Check", styles["th"]),
            _p("Result", styles["th"]),
            _p("Detail", styles["th"]),
        ]
    ]
    for finding in findings:
        rows.append(
            [
                _p(finding.category.title(), styles["td"]),
                _p(finding.field, styles["td_bold"]),
                _result_para(finding.result, styles["td"]),
                _p(finding.detail or "", styles["td"]),
            ]
        )
    table = Table(rows, colWidths=[68, 126, 70, 239], repeatRows=1)
    table.setStyle(_table_style())
    return table


def _documents_block(application, styles):
    documents = list(application.documents)
    if not documents:
        return [_p("No documents are attached to this application.", styles["body"])]
    rows = [
        [
            _p("Kind", styles["th"]),
            _p("File", styles["th"]),
            _p("Size", styles["th_r"]),
            _p("Pages", styles["th_r"]),
            _p("Checksum", styles["th"]),
        ]
    ]
    for document in documents:
        kind = document.kind.replace("_", " ").title()
        if document.duplicate_of_id:
            kind = f"{kind} · duplicate"
        rows.append(
            [
                _p(kind, styles["td"]),
                _p(document.original_filename, styles["td"]),
                _p(f"{document.size_bytes / 1024:.1f} KB", styles["td_r"]),
                _p(document.page_count, styles["td_r"]),
                _p(document.sha256[:12], styles["td_r"]),
            ]
        )
    table = Table(rows, colWidths=[92, 235, 56, 38, 82], repeatRows=1)
    table.setStyle(_table_style())
    return [table]


def _section(title: str, styles, min_height: float = 118) -> list:
    return [
        CondPageBreak(min_height),
        _p(title, styles["h2"]),
        HRFlowable(width="100%", thickness=0.55, color=LINE, spaceBefore=5, spaceAfter=9),
    ]


def _footer(canvas: canvas.Canvas) -> None:
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, 38, PAGE_W - MARGIN_X, 38)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.8)
    canvas.drawString(
        MARGIN_X,
        27,
        "Maatram Verify · MH26-01 · Deterministic OCR and rule checks · No generative AI",
    )
    canvas.drawRightString(PAGE_W - MARGIN_X, 27, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def build_validation_report(application, run) -> bytes:
    """Render a complete A4 report for one completed validation run."""

    if run is None:
        raise ValueError("a completed validation run is required")
    if run.status != "completed":
        raise ValueError("the validation run has not completed")

    styles = _base_styles()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=f"{application.reference} · Validation report",
        author="Maatram Verify",
        subject="Admission document validation",
        creator="Maatram Verify deterministic pipeline",
    )

    def on_page(canvas: canvas.Canvas, _doc) -> None:
        _footer(canvas)
        if canvas.getPageNumber() > 1:
            canvas.saveState()
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 6.8)
            canvas.drawString(
                MARGIN_X,
                PAGE_H - 28,
                f"{application.reference} · {application.applicant_name} · Validation report",
            )
            canvas.drawRightString(
                PAGE_W - MARGIN_X, PAGE_H - 28, f"Run #{run.id}"
            )
            canvas.setStrokeColor(LINE_SOFT)
            canvas.line(MARGIN_X, PAGE_H - 34, PAGE_W - MARGIN_X, PAGE_H - 34)
            canvas.restoreState()

    story: list = []
    story += _page_drawing(application, run, styles)
    story += _summary_block(application, run, styles)
    story += _section("Applicant and filing", styles)
    story += [_identity_block(application, run, styles), Spacer(1, 15)]
    story += _section("Mark verification", styles)
    story += _marks_block(application, run, styles)
    story += [Spacer(1, 15)]
    story += _section("Identity checks", styles)
    identity = _identity_checks_block(run, styles)
    story += identity if identity else [_p("No identity checks were recorded.", styles["body"])]
    story += [Spacer(1, 15)]
    story += _section("Documents on file", styles)
    story += _documents_block(application, styles)
    other = _other_findings(run, styles)
    if other is not None:
        story += [Spacer(1, 15)]
        story += _section("Completeness, duplicates and format", styles)
        story += [other]
    story += [Spacer(1, 15)]
    story += _section("Photograph", styles, min_height=330)
    story += _photo_block(run, styles)
    story += [
        Spacer(1, 16),
        HRFlowable(width="100%", thickness=0.55, color=LINE, spaceBefore=0, spaceAfter=8),
        _p(
            "How this report was produced. Every value above comes from the application record, "
            "the stored document or the deterministic rule engine. Tesseract reads the mark sheet; "
            "OpenCV measures the photograph; subject names are normalised with a fixed alias list "
            "and fuzzy matching. No generative model is used at any stage. A result of REVIEW or "
            "FAIL requires a person to confirm or correct the record before a decision is made.",
            styles["small"],
        ),
        Spacer(1, 6),
        _p(
            f"Run #{run.id} · Started {_format_date(run.started_at)} · Finished {_format_date(run.finished_at)} · "
            f"Application {application.reference}",
            styles["small"],
        ),
    ]

    document.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buffer.getvalue()
