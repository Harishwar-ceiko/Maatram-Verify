"""Cross-document identity consistency and class-progression checks.

Everything here is deterministic: rapidfuzz similarity, exact dates and set
overlap. The matrix records what each attached document says; the checks turn
only real disagreements into findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from rapidfuzz import fuzz

from app.core.config import rules
from app.models.application import EducationRecord
from app.models.enums import Result, Severity
from app.services.comparison import Check
from app.services.subjects import clean, normalize_subject


@dataclass(slots=True)
class SourceRecord:
    """The identity fields a single document produced, ready for the matrix."""

    source: str
    kind: str
    document_id: int | None = None
    filename: str | None = None
    name: str | None = None
    date_of_birth: str | None = None
    year_of_birth: int | None = None
    father_name: str | None = None
    address: str | None = None
    confidence: float | None = None


def _similarity(left: str | None, right: str | None) -> float | None:
    if not left or not right:
        return None
    return round(float(fuzz.token_set_ratio(clean(left), clean(right))), 1)


def _value_entry(
    source: SourceRecord,
    value: str,
    *,
    status: str,
    similarity: float | None = None,
) -> dict[str, Any]:
    return {
        "source": source.source,
        "kind": source.kind,
        "document_id": source.document_id,
        "filename": source.filename,
        "value": value,
        "status": status,
        "similarity": similarity,
    }


def _application_entry(value: str) -> dict[str, Any]:
    return {
        "source": "Application",
        "kind": "application",
        "document_id": None,
        "filename": None,
        "value": value,
        "status": "baseline",
        "similarity": None,
    }


def _dob_value(source: SourceRecord) -> str | None:
    if source.date_of_birth:
        return source.date_of_birth
    if source.year_of_birth:
        return str(source.year_of_birth)
    return None


def _dob_matches(application_dob: date, value: str) -> bool:
    text = str(value).strip()
    if len(text) == 4 and text.isdigit():
        return int(text) == application_dob.year
    try:
        return date.fromisoformat(text) == application_dob
    except ValueError:
        return False


def _fuzzy_row(
    *,
    key: str,
    label: str,
    entered: str,
    sources: list[SourceRecord],
    value_of,
    threshold: float,
) -> dict[str, Any]:
    values = [_application_entry(entered)]
    matched_flags: list[bool] = []
    for source in sources:
        value = value_of(source)
        if not value:
            continue
        score = _similarity(entered, value)
        matched = score is not None and score >= threshold
        matched_flags.append(matched)
        values.append(
            _value_entry(
                source,
                str(value),
                status="match" if matched else "mismatch",
                similarity=score,
            )
        )

    if not matched_flags:
        status = "not_available"
        detail = "No attached document carries this field."
    elif all(matched_flags):
        status = "match"
        detail = (
            "The document value agrees with the application."
            if len(matched_flags) == 1
            else (
                f"All {len(matched_flags)} document values agree with the "
                "application."
            )
        )
    else:
        status = "mismatch"
        differ = len([flag for flag in matched_flags if not flag])
        detail = (
            "The document value differs from the application."
            if len(matched_flags) == 1
            else (
                f"{differ} of {len(matched_flags)} document values differ from "
                "the application."
            )
        )
    return {
        "field": key,
        "label": label,
        "status": status,
        "detail": detail,
        "values": values,
    }


def _dob_row(application, sources: list[SourceRecord]) -> dict[str, Any]:
    entered = application.date_of_birth.isoformat()
    values = [_application_entry(entered)]
    matched_flags: list[bool] = []
    for source in sources:
        value = _dob_value(source)
        if not value:
            continue
        matched = _dob_matches(application.date_of_birth, value)
        matched_flags.append(matched)
        values.append(
            _value_entry(
                source,
                value,
                status="match" if matched else "mismatch",
            )
        )
    if not matched_flags:
        status = "not_available"
        detail = "No attached document carries a date of birth."
    elif all(matched_flags):
        status = "match"
        detail = "The date of birth agrees with the application."
    else:
        status = "mismatch"
        detail = "The date of birth does not agree with the application."
    return {
        "field": "date_of_birth",
        "label": "Date of birth",
        "status": status,
        "detail": detail,
        "values": values,
    }


def build_identity_matrix(
    application,
    sources: list[SourceRecord],
) -> dict[str, Any]:
    """Build the four-field matrix shown in the report and dashboard."""

    config = rules()["validation"]
    name_threshold = float(config["name_fuzzy_threshold"])
    father_threshold = float(
        config.get("father_name_fuzzy_threshold", name_threshold)
    )
    address_threshold = float(config.get("address_fuzzy_threshold", 70))

    fields = [
        _fuzzy_row(
            key="name",
            label="Name",
            entered=application.applicant_name,
            sources=sources,
            value_of=lambda source: source.name,
            threshold=name_threshold,
        ),
        _dob_row(application, sources),
        _fuzzy_row(
            key="father_name",
            label="Father's name",
            entered=application.father_name,
            sources=sources,
            value_of=lambda source: source.father_name,
            threshold=father_threshold,
        ),
        _fuzzy_row(
            key="address",
            label="Address",
            entered=application.address,
            sources=sources,
            value_of=lambda source: source.address,
            threshold=address_threshold,
        ),
    ]
    checked = sum(1 for row in fields if row["status"] != "not_available")
    mismatched = sum(1 for row in fields if row["status"] == "mismatch")
    return {
        "fields": fields,
        "checked": checked,
        "mismatched": mismatched,
    }


def class_year_checks(records: dict[int, EducationRecord]) -> list[Check]:
    """Adjacent class records must progress forwards, one year per class."""

    config = rules()["validation"].get("class_years", {})
    max_gap = int(config.get("max_gap_years", 3))
    levels = sorted(level for level, record in records.items() if record is not None)
    checks: list[Check] = []

    for left_level, right_level in zip(levels, levels[1:]):
        left = records[left_level]
        right = records[right_level]
        expected = right_level - left_level
        gap = int(right.exam_year) - int(left.exam_year)
        field = f"Class {left_level} to Class {right_level} years"
        shown = f"{left.exam_year} → {right.exam_year}"
        meta = {
            "kind": "class_years",
            "from": left_level,
            "to": right_level,
            "gap": gap,
        }

        if gap < expected:
            checks.append(
                Check(
                    category="consistency",
                    field=field,
                    result=Result.mismatch.value,
                    severity=Severity.critical.value,
                    entered_value=shown,
                    measured_value=f"{gap} year{'s' if gap != 1 else ''}",
                    required_value=f"at least {expected} year{'s' if expected != 1 else ''}",
                    detail=(
                        f"Class {left_level} is dated {left.exam_year} and Class "
                        f"{right_level} is dated {right.exam_year}; the class years "
                        "are out of order."
                    ),
                    meta={
                        **meta,
                        "clause": (
                            f"the Class {left_level} and Class {right_level} "
                            "examination years are out of order"
                        ),
                    },
                )
            )
        elif gap > max_gap:
            checks.append(
                Check(
                    category="consistency",
                    field=field,
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    entered_value=shown,
                    measured_value=f"{gap} years",
                    required_value=f"at most {max_gap} years",
                    difference=gap - max_gap,
                    detail=(
                        f"There is a {gap}-year gap between Class {left_level} and "
                        f"Class {right_level}. That is too long to be a normal "
                        "class progression."
                    ),
                    meta={
                        **meta,
                        "clause": (
                            f"the gap between the Class {left_level} and Class "
                            f"{right_level} examination years is too large"
                        ),
                    },
                )
            )
        elif gap > expected:
            checks.append(
                Check(
                    category="consistency",
                    field=field,
                    result=Result.pending.value,
                    severity=Severity.warning.value,
                    entered_value=shown,
                    measured_value=f"{gap} years",
                    required_value=f"{expected} year{'s' if expected != 1 else ''}",
                    detail=(
                        f"There is a {gap}-year gap between Class {left_level} and "
                        f"Class {right_level}. A reviewer should confirm the break."
                    ),
                    meta={
                        **meta,
                        "clause": (
                            f"the Class {left_level} to Class {right_level} "
                            "progression has a year gap"
                        ),
                    },
                )
            )
        else:
            checks.append(
                Check(
                    category="consistency",
                    field=field,
                    result=Result.pass_.value,
                    severity=Severity.info.value,
                    entered_value=shown,
                    detail=(
                        f"The examination years follow the expected {expected}-year "
                        "class progression."
                    ),
                    meta=meta,
                )
            )
    return checks


def _group(record: EducationRecord, ignored: set[str]) -> set[str]:
    subjects: set[str] = set()
    for mark in record.marks:
        canonical = normalize_subject(mark.subject).canonical
        key = clean(canonical)
        if key and key not in ignored:
            subjects.add(canonical)
    return subjects


def subject_group_checks(records: dict[int, EducationRecord]) -> list[Check]:
    """Warn when the Class 11 and Class 12 subject groups have little overlap."""

    config = rules()["validation"].get("subject_group", {})
    if not config.get("enabled", True):
        return []
    if 11 not in records or 12 not in records:
        return []
    ignored = {
        clean(normalize_subject(str(subject)).canonical)
        for subject in config.get("ignored_subjects", [])
    }
    class_11 = _group(records[11], ignored)
    class_12 = _group(records[12], ignored)
    if not class_11 or not class_12:
        return []
    union = class_11 | class_12
    overlap = len(class_11 & class_12) / len(union) if union else 1.0
    minimum = float(config.get("min_overlap", 0.5))
    field = "Class 11 and 12 subject group"
    meta = {
        "kind": "subject_group",
        "class_11": sorted(class_11),
        "class_12": sorted(class_12),
        "overlap": round(overlap * 100, 1),
    }
    if overlap >= minimum:
        return [
            Check(
                category="consistency",
                field=field,
                result=Result.pass_.value,
                severity=Severity.info.value,
                entered_value=", ".join(sorted(class_11)),
                uploaded_value=", ".join(sorted(class_12)),
                measured_value=f"{overlap * 100:.0f}% overlap",
                required_value=f"at least {minimum * 100:.0f}% overlap",
                detail="The Class 11 and Class 12 subject groups are consistent.",
                meta=meta,
            )
        ]
    added = sorted(class_12 - class_11)
    dropped = sorted(class_11 - class_12)
    parts = []
    if added:
        parts.append(f"added in Class 12: {', '.join(added)}")
    if dropped:
        parts.append(f"dropped after Class 11: {', '.join(dropped)}")
    return [
        Check(
            category="consistency",
            field=field,
            result=Result.pending.value,
            severity=Severity.warning.value,
            entered_value=", ".join(sorted(class_11)),
            uploaded_value=", ".join(sorted(class_12)),
            measured_value=f"{overlap * 100:.0f}% overlap",
            required_value=f"at least {minimum * 100:.0f}% overlap",
            detail=(
                "The Class 11 and Class 12 subject groups differ"
                + (f" ({'; '.join(parts)})" if parts else "")
                + ". A reviewer should confirm the stream change."
            ),
            meta={
                **meta,
                "clause": "the Class 11 and Class 12 subject groups differ",
            },
        )
    ]
