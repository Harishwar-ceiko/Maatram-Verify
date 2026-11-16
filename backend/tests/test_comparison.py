from __future__ import annotations

from app.ocr.types import SubjectRow
from app.services.comparison import EnteredMarkValue, compare_marks


def row(subject: str, marks: float | None, confidence: float = 94.0) -> SubjectRow:
    return SubjectRow(
        subject_raw=subject,
        marks_obtained=marks,
        max_marks=100,
        grade="A",
        confidence=confidence,
        page=1,
    )


ENTERED = [
    EnteredMarkValue("Mathematics", 88),
    EnteredMarkValue("English", 92),
    EnteredMarkValue("Physics", 81),
    EnteredMarkValue("Chemistry", 79),
]


def test_all_four_subjects_match():
    result = compare_marks(
        ENTERED,
        [row("Mathematics", 88), row("English", 92), row("Physics", 81), row("Chemistry", 79)],
    )
    assert result.matched == 4
    assert result.mismatched == 0
    assert result.missing == 0
    assert result.all_match
    assert {check.result for check in result.checks} == {"match"}


def test_mismatch_carries_the_difference():
    result = compare_marks(
        [EnteredMarkValue("Mathematics", 85)],
        [row("Maths", 88)],
    )
    assert result.mismatched == 1
    check = result.checks[0]
    assert check.result == "mismatch"
    assert check.difference == 3
    assert check.entered_value == "85"
    assert check.uploaded_value == "88"
    assert "difference +3" in check.detail


def test_missing_subject_on_sheet_is_critical():
    result = compare_marks(
        [EnteredMarkValue("Physics", 81)],
        [row("Mathematics", 88)],
    )
    assert result.missing == 1
    missing = next(check for check in result.checks if check.result == "missing_upload")
    assert missing.severity == "critical"
    assert missing.field == "Physics"


def test_extra_subject_on_sheet_is_flagged():
    result = compare_marks(
        [EnteredMarkValue("Mathematics", 88)],
        [row("Mathematics", 88), row("Biology", 74)],
    )
    extra = next(check for check in result.checks if check.result == "missing_entry")
    assert extra.field == "Biology"
    assert extra.uploaded_value == "74"
    assert result.extra == 1


def test_low_confidence_row_goes_to_review_not_match():
    result = compare_marks(
        [EnteredMarkValue("Mathematics", 88)],
        [row("Mathematics", 88, confidence=41)],
    )
    assert result.low_confidence == 1
    assert result.matched == 0
    assert result.checks[0].result == "pending"
    assert "41% confidence" in result.checks[0].detail


def test_tolerance_is_read_from_rules(monkeypatch):
    from app.services import comparison

    config = comparison.rules()
    monkeypatch.setitem(config["subjects"], "mark_tolerance", 1)
    result = compare_marks(
        [EnteredMarkValue("Mathematics", 88)],
        [row("Mathematics", 87)],
    )
    assert result.checks[0].result == "match"
    monkeypatch.setitem(config["subjects"], "mark_tolerance", 0)
