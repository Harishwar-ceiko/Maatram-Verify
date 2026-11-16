from __future__ import annotations

from app.ocr.fields import visual_rows
from app.ocr.types import OcrPage, Word
from app.ocr.fields import extract_fields


def word(text: str, left: int, top: int, width: int = 40, height: int = 12, confidence: float = 94.0) -> Word:
    return Word(text=text, confidence=confidence, left=left, top=top, width=width, height=height)


def sample_page() -> OcrPage:
    words = [
        word("CANDIDATE", 10, 100, 70),
        word("REGISTER", 300, 100, 60),
        word("NO.", 366, 100, 20),
        word("ANANYA", 10, 132, 52),
        word("SUBRAMANIAN", 70, 132, 90),
        word("REG2026A014", 300, 132, 95),
        word("Subject", 10, 200, 45),
        word("Maximum", 300, 200, 55),
        word("Obtained", 420, 200, 55),
        word("Grade", 520, 200, 38),
        word("Mathematics", 10, 235, 80),
        word("100", 300, 235, 24),
        word("88", 420, 235, 18),
        word("A", 520, 235, 10),
        word("English", 10, 270, 48),
        word("100", 300, 270, 24),
        word("92", 420, 270, 18),
        word("A+", 520, 270, 18),
        word("Physics", 10, 305, 42),
        word("100", 300, 305, 24),
        word("81", 420, 305, 18),
        word("A", 520, 305, 10),
        word("Chemistry", 10, 340, 60),
        word("100", 300, 340, 24),
        word("79", 420, 340, 18),
        word("B+", 520, 340, 18),
        word("Grand", 10, 390, 38),
        word("total", 55, 390, 28),
        word("400", 300, 390, 24),
        word("340", 420, 390, 24),
    ]
    text = "\n".join(
        [
            "CANDIDATE REGISTER NO.",
            "ANANYA SUBRAMANIAN REG2026A014",
            "Examination March 2026",
            "Subject Maximum Obtained Grade",
            "Mathematics 100 88 A",
            "English 100 92 A+",
            "Physics 100 81 A",
            "Chemistry 100 79 B+",
            "Grand total 400 340",
        ]
    )
    return OcrPage(number=1, width=700, height=500, words=words, text=text, psm=6)


def test_visual_rows_merge_columns_on_the_same_baseline():
    rows = visual_rows(sample_page().words)
    labels = next(row for row in rows if "CANDIDATE" in row.text)
    assert "REGISTER" in labels.text
    assert len(rows) == 8


def test_identity_is_read_inside_its_column():
    extraction = extract_fields([sample_page()])
    assert extraction.name.value == "ANANYA SUBRAMANIAN"
    assert extraction.name.confidence > 90
    assert extraction.register_number.value == "REG2026A014"
    assert extraction.exam_year.value == 2026


def test_subject_table_maps_header_columns():
    extraction = extract_fields([sample_page()])
    subjects = {row.subject_raw: row for row in extraction.subjects}
    assert set(subjects) == {"Mathematics", "English", "Physics", "Chemistry"}
    assert subjects["Mathematics"].marks_obtained == 88
    assert subjects["Mathematics"].max_marks == 100
    assert subjects["English"].grade == "A+"
    assert subjects["Chemistry"].confidence > 80


def test_total_row_is_not_treated_as_a_subject():
    extraction = extract_fields([sample_page()])
    assert all("total" not in row.subject_raw.lower() for row in extraction.subjects)


def test_line_fallback_finds_label_values_without_geometry():
    page = OcrPage(
        number=1,
        width=700,
        height=500,
        words=[],
        text="Candidate: Ravi Kumar\nRegister No: REG7777\nExamination 2025",
    )
    extraction = extract_fields([page])
    assert extraction.name.value == "Ravi Kumar"
    assert extraction.register_number.value == "REG7777"
    assert extraction.exam_year.value == 2025
    assert extraction.subjects == []
    assert any("No subject rows" in warning for warning in extraction.warnings)
