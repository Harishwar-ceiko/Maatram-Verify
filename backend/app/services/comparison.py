from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Sequence

from rapidfuzz import fuzz

from app.core.config import rules
from app.ocr.types import SubjectRow
from app.services.subjects import clean, normalize_subject


@dataclass(slots=True)
class EnteredMarkValue:
    subject: str
    marks: float
    max_marks: float | None = None


@dataclass(slots=True)
class Check:
    category: str
    field: str
    result: str
    severity: str = "info"
    entered_value: str | None = None
    uploaded_value: str | None = None
    measured_value: str | None = None
    required_value: str | None = None
    difference: float | None = None
    detail: str | None = None
    confidence: float | None = None
    subject_norm: str | None = None
    meta: dict | None = None


@dataclass(slots=True)
class MarkComparison:
    checks: list[Check] = field(default_factory=list)
    matched: int = 0
    mismatched: int = 0
    missing: int = 0
    low_confidence: int = 0
    extra: int = 0

    @property
    def all_match(self) -> bool:
        return not (self.mismatched or self.missing or self.low_confidence)


def format_marks(value: float | None) -> str | None:
    if value is None:
        return None
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _match_row(entered_key: str, rows: Sequence[SubjectRow]) -> SubjectRow | None:
    exact = [row for row in rows if clean(normalize_subject(row.subject_raw).canonical) == entered_key]
    if exact:
        # A statement can repeat a subject across pages; take the clearest read.
        return max(exact, key=lambda row: row.confidence)
    if not rows:
        return None
    scored = [
        (row, fuzz.WRatio(entered_key, clean(normalize_subject(row.subject_raw).canonical)))
        for row in rows
    ]
    row, score = max(scored, key=lambda item: item[1])
    threshold = float(rules()["subjects"]["fuzzy_threshold"])
    return row if score >= threshold else None


def compare_marks(
    entered: Sequence[EnteredMarkValue],
    extracted: Sequence[SubjectRow],
    *,
    low_confidence: float | None = None,
) -> MarkComparison:
    config = rules()
    tolerance = float(config["subjects"]["mark_tolerance"])
    confidence_floor = (
        float(low_confidence)
        if low_confidence is not None
        else float(config["ocr"]["low_confidence"])
    )

    comparison = MarkComparison()
    used: set[int] = set()

    for index, mark in enumerate(entered):
        match = normalize_subject(mark.subject)
        subject_key = clean(match.canonical)
        uploaded = _match_row(subject_key, extracted)
        if uploaded is not None:
            used.add(id(uploaded))

        field_name = match.canonical
        if uploaded is None:
            comparison.missing += 1
            comparison.checks.append(
                Check(
                    category="mark",
                    field=field_name,
                    subject_norm=match.canonical,
                    result="missing_upload",
                    severity="critical",
                    entered_value=format_marks(mark.marks),
                    detail=(
                        "The subject entered on the application was not found on the mark sheet."
                    ),
                )
            )
            continue

        if uploaded.marks_obtained is None:
            comparison.missing += 1
            comparison.checks.append(
                Check(
                    category="mark",
                    field=field_name,
                    subject_norm=match.canonical,
                    result="missing_upload",
                    severity="critical",
                    entered_value=format_marks(mark.marks),
                    uploaded_value=uploaded.subject_raw,
                    detail="The subject is present but no readable mark was found.",
                    confidence=uploaded.confidence,
                )
            )
            continue

        difference = round(uploaded.marks_obtained - mark.marks, 2)
        common = dict(
            category="mark",
            field=field_name,
            subject_norm=match.canonical,
            entered_value=format_marks(mark.marks),
            uploaded_value=format_marks(uploaded.marks_obtained),
            measured_value=format_marks(uploaded.marks_obtained),
            required_value=format_marks(mark.marks),
            difference=difference,
            confidence=uploaded.confidence,
        )

        if uploaded.confidence < confidence_floor:
            comparison.low_confidence += 1
            comparison.checks.append(
                Check(
                    **common,
                    result="pending",
                    severity="warning",
                    detail=(
                        f"This row was read with {uploaded.confidence:.0f}% confidence. "
                        "Confirm it by eye before accepting the comparison."
                    ),
                )
            )
        elif abs(difference) <= tolerance + 1e-9:
            comparison.matched += 1
            comparison.checks.append(
                Check(
                    **common,
                    result="match",
                    severity="info",
                    detail="Matches the mark sheet.",
                )
            )
        else:
            comparison.mismatched += 1
            comparison.checks.append(
                Check(
                    **common,
                    result="mismatch",
                    severity="critical",
                    detail=(
                        f"Entered {format_marks(mark.marks)} but the sheet reads "
                        f"{format_marks(uploaded.marks_obtained)} "
                        f"(difference {difference:+g})."
                    ),
                )
            )

    entered_keys = {clean(normalize_subject(mark.subject).canonical) for mark in entered}
    for row in extracted:
        if id(row) in used:
            continue
        canonical = normalize_subject(row.subject_raw).canonical
        if clean(canonical) in entered_keys:
            continue
        comparison.extra += 1
        comparison.checks.append(
            Check(
                category="mark",
                field=canonical,
                subject_norm=canonical,
                result="missing_entry",
                severity="warning",
                uploaded_value=format_marks(row.marks_obtained),
                detail="This subject appears on the mark sheet but was not entered on the application.",
                confidence=row.confidence,
            )
        )

    return comparison


def comparison_confidence(checks: Sequence[Check]) -> float:
    values = [check.confidence for check in checks if check.confidence is not None]
    return round(mean(values), 1) if values else 0.0
