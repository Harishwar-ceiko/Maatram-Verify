from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import rules
from app.core.security import encrypt_text
from app.models.application import Application, EducationRecord
from app.models.base import utcnow
from app.models.document import AadhaarRecord, Document, ExtractedMark, OcrResult
from app.models.enums import (
    ApplicationStatus,
    DocumentKind,
    Result,
    ReviewStatus,
    RunStatus,
    Severity,
)
from app.models.review import ReviewItem
from app.models.validation import Finding, ValidationRun
from app.ocr.extract import extract_document
from app.ocr.types import OcrUnavailable, SubjectRow
from app.services.audit import write_audit
from app.services.comparison import Check, EnteredMarkValue, compare_marks, comparison_confidence
from app.services.consistency import (
    SourceRecord,
    build_identity_matrix,
    class_year_checks,
    subject_group_checks,
)
from app.services.subjects import clean, normalize_subject
from app.services.storage import read_document_bytes
from app.validators.aadhaar import dob_comparison, mask_number, verhoeff_valid
from app.validators.photo import PhotoAnalysis, PhotoUnreadable, analyze_photo

logger = logging.getLogger("maatram.validation")

SessionFactory = Callable[[], Session]

MARK_SHEET_KINDS = {
    DocumentKind.marksheet_10.value,
    DocumentKind.marksheet_11.value,
    DocumentKind.marksheet_12.value,
    DocumentKind.marksheet.value,
}
SUPPORTING_KINDS = {
    DocumentKind.aadhaar.value,
    DocumentKind.income_certificate.value,
    DocumentKind.community_certificate.value,
    DocumentKind.first_graduate_certificate.value,
}

CATEGORY_ORDER = {
    "identity": 0,
    "mark": 1,
    "document": 2,
    "completeness": 3,
    "consistency": 4,
    "duplicate": 5,
    "photo": 6,
    "format": 7,
    "ocr": 8,
}


def _count(count: int, noun: str, plural: str | None = None) -> str:
    return f"{count} {noun if count == 1 else (plural or f'{noun}s')}"


def _verb(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def _join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _critical_clauses(checks: list[Check]) -> list[str]:
    """Turn critical findings into a sentence a registrar would actually say.

    Missing subjects are reported once even though both the mark and the
    completeness check can flag them, and the wording avoids restating the
    detail already shown in each row.
    """

    critical = [check for check in checks if check.severity == Severity.critical.value]
    clauses: list[str] = []

    mismatches = [
        check for check in critical if check.category == "mark" and check.result == Result.mismatch.value
    ]
    if mismatches:
        total = len(mismatches)
        clauses.append(
            f"{_count(total, 'mark')} {_verb(total, 'differs', 'differ')} from the mark sheet"
        )

    missing = _unique(
        [
            check.field
            for check in critical
            if check.result == Result.missing_upload.value
            and check.category in ("mark", "completeness")
        ]
    )
    if missing:
        clauses.append(
            f"{_join(missing)} {_verb(len(missing), 'is', 'are')} missing from the mark sheet"
        )

    identity = _unique(
        [check.field.lower() for check in critical if check.category == "identity"]
    )
    if identity:
        clauses.append(
            f"the {_join(identity)} {_verb(len(identity), 'does', 'do')} not match the application"
        )

    consistency_clauses = [
        str((check.meta or {}).get("clause"))
        for check in critical
        if check.category == "consistency" and (check.meta or {}).get("clause")
    ]
    if consistency_clauses:
        clauses.extend(_unique(consistency_clauses))

    photo = [check for check in critical if check.category == "photo"]
    if photo:
        names = _unique(
            [
                re.sub(r"^photo\s+", "", check.field, flags=re.IGNORECASE).lower()
                for check in photo
            ]
        )
        clauses.append(
            f"the photograph failed the {_join(names)} "
            f"check{'' if len(names) == 1 else 's'}"
        )

    duplicates = [check for check in critical if check.category == "duplicate"]
    if duplicates:
        total = len(duplicates)
        clauses.append(
            f"{_count(total, 'duplicate file')} {_verb(total, 'is', 'are')} attached"
        )

    document_clauses = [
        str((check.meta or {}).get("clause"))
        for check in critical
        if check.category == "document" and (check.meta or {}).get("clause")
    ]
    if document_clauses:
        clauses.extend(_unique(document_clauses))

    # A document check without a written clause still needs a sentence.
    unnamed = [
        check.field.lower()
        for check in critical
        if check.category == "document" and not (check.meta or {}).get("clause")
    ]
    if unnamed:
        clauses.append(f"{_join(_unique(unnamed))} could not be verified")

    other = [
        check.field.lower()
        for check in critical
        if check.category in ("format", "ocr")
    ]
    if other:
        clauses.append(f"{_join(_unique(other))} could not be checked")

    return clauses


def _finding(
    application: Application,
    *,
    category: str,
    field: str,
    result: str,
    severity: str = Severity.info.value,
    entered_value: str | None = None,
    uploaded_value: str | None = None,
    measured_value: str | None = None,
    required_value: str | None = None,
    difference: float | None = None,
    detail: str | None = None,
    confidence: float | None = None,
    subject_norm: str | None = None,
    meta: dict[str, Any] | None = None,
    sort_order: int = 0,
) -> Finding:
    return Finding(
        application_id=application.id,
        category=category,
        field=field,
        subject_norm=subject_norm,
        result=result,
        entered_value=entered_value,
        uploaded_value=uploaded_value,
        measured_value=measured_value,
        required_value=required_value,
        difference=difference,
        detail=detail,
        severity=severity,
        confidence=confidence,
        sort_order=sort_order,
        meta=meta,
    )


def _from_check(application: Application, check: Check, order: int) -> Finding:
    return _finding(
        application,
        category=check.category,
        field=check.field,
        result=check.result,
        severity=check.severity,
        entered_value=check.entered_value,
        uploaded_value=check.uploaded_value,
        measured_value=check.measured_value,
        required_value=check.required_value,
        difference=check.difference,
        detail=check.detail,
        confidence=check.confidence,
        subject_norm=check.subject_norm,
        meta=check.meta,
        sort_order=order,
    )


def _doc_meta(document: Document) -> dict[str, Any]:
    return {
        "kind": document.kind,
        "document_id": document.id,
        "label": document.kind_label,
    }


def _class_level(kind: str) -> int | None:
    if kind == DocumentKind.marksheet.value:
        return 12
    level = (
        rules()
        .get("documents", {})
        .get("kinds", {})
        .get(kind, {})
        .get("class_level")
    )
    return int(level) if level is not None else None


def _field_label(field: str) -> str:
    labels = rules().get("documents", {}).get("field_labels", {})
    return str(labels.get(field, field.replace("_", " ").title()))


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _field_value(extraction, field: str) -> Any:
    if field == "name":
        return extraction.name.value
    if field == "register_number":
        return extraction.register_number.value
    if field == "exam_year":
        return extraction.exam_year.value
    if field == "subjects":
        return extraction.subjects
    return extraction.attributes.get(field)


def _add_months(value: date, months: int) -> date:
    import calendar

    index = value.month - 1 + months
    year = value.year + index // 12
    month = index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _document_name_check(
    application: Application,
    document: Document,
    extraction,
) -> list[Check]:
    name = extraction.name.value
    if not name:
        return []
    threshold = float(rules()["validation"]["name_fuzzy_threshold"])
    score = fuzz.token_set_ratio(clean(application.applicant_name), clean(name))
    matched = score >= threshold
    return [
        Check(
            category="identity",
            field="Applicant name",
            result=Result.match.value if matched else Result.mismatch.value,
            severity=Severity.info.value if matched else Severity.critical.value,
            entered_value=application.applicant_name,
            uploaded_value=name,
            measured_value=f"{score:.0f}% similarity",
            required_value=f"at least {threshold:.0f}%",
            confidence=extraction.name.confidence,
            detail=(
                "The name matches the application."
                if matched
                else "The name printed on this document does not match the application."
            ),
            meta=_doc_meta(document),
        )
    ]


def _source_record(document: Document, extraction, source: str) -> SourceRecord | None:
    """Capture the identity fields one document produced for the matrix."""

    attributes = extraction.attributes or {}
    record = SourceRecord(
        source=source,
        kind=document.kind,
        document_id=document.id,
        filename=document.original_filename,
        name=extraction.name.value or attributes.get("name"),
        date_of_birth=attributes.get("date_of_birth"),
        year_of_birth=attributes.get("year_of_birth"),
        father_name=attributes.get("father_name"),
        address=attributes.get("address"),
        confidence=extraction.name.confidence or None,
    )
    if not any(
        (
            record.name,
            record.date_of_birth,
            record.year_of_birth,
            record.father_name,
            record.address,
        )
    ):
        return None
    return record


def _consistency_findings(
    application: Application,
    sources: list[SourceRecord],
) -> list[Check]:
    """Compare the father's name and address printed on each document.

    Names and dates of birth already have per-document checks. The father's
    name and address are only printed on a few kinds, so they are compared here
    once a document has been read.
    """

    config = rules()["validation"]
    father_threshold = float(
        config.get("father_name_fuzzy_threshold", config["name_fuzzy_threshold"])
    )
    address_threshold = float(config.get("address_fuzzy_threshold", 70))
    checks: list[Check] = []

    for source in sources:
        meta = {
            "kind": source.kind,
            "document_id": source.document_id,
            "label": source.source,
        }
        if source.father_name:
            score = fuzz.token_set_ratio(
                clean(application.father_name), clean(source.father_name)
            )
            matched = score >= father_threshold
            checks.append(
                Check(
                    category="consistency",
                    field="Father's name",
                    result=Result.match.value if matched else Result.mismatch.value,
                    severity=(
                        Severity.info.value if matched else Severity.critical.value
                    ),
                    entered_value=application.father_name,
                    uploaded_value=source.father_name,
                    measured_value=f"{score:.0f}% similarity",
                    required_value=f"at least {father_threshold:.0f}%",
                    confidence=source.confidence,
                    detail=(
                        "Matches the father's name on the application."
                        if matched
                        else (
                            "The father's name printed on this document does not "
                            "match the application."
                        )
                    ),
                    meta=(
                        meta
                        if matched
                        else {
                            **meta,
                            "clause": (
                                "the father's name on the "
                                f"{source.source.lower()} does not match the application"
                            ),
                        }
                    ),
                )
            )
        if source.address:
            score = fuzz.token_set_ratio(
                clean(application.address), clean(source.address)
            )
            matched = score >= address_threshold
            checks.append(
                Check(
                    category="consistency",
                    field="Address",
                    result=Result.match.value if matched else Result.pending.value,
                    severity=(
                        Severity.info.value if matched else Severity.warning.value
                    ),
                    entered_value=application.address,
                    uploaded_value=source.address,
                    measured_value=f"{score:.0f}% similarity",
                    required_value=f"at least {address_threshold:.0f}%",
                    confidence=source.confidence,
                    detail=(
                        "Matches the address on the application."
                        if matched
                        else (
                            "The address printed on this document differs from the "
                            "application. A reviewer should confirm it."
                        )
                    ),
                    meta=(
                        meta
                        if matched
                        else {
                            **meta,
                            "clause": (
                                "the address on the "
                                f"{source.source.lower()} differs from the application"
                            ),
                        }
                    ),
                )
            )
    return checks


def _photo_to_checks(document: Document, analysis: PhotoAnalysis) -> list[Check]:
    checks: list[Check] = []
    for item in analysis.checks:
        checks.append(
            Check(
                category="photo",
                field=item.field,
                result=Result.pass_.value if item.passed else Result.fail.value,
                severity=item.severity,
                uploaded_value=document.original_filename,
                measured_value=item.measured,
                required_value=item.required,
                detail=item.detail,
                meta=_doc_meta(document),
            )
        )
    return checks


def _photo_failure(document: Document, detail: str) -> Check:
    return Check(
        category="photo",
        field="Photograph",
        result=Result.fail.value,
        severity=Severity.critical.value,
        uploaded_value=document.original_filename,
        detail=detail,
        meta=_doc_meta(document),
    )


def _identity_checks(
    application: Application,
    class_record: EducationRecord,
    extraction_name: str | None,
    extraction_register: str | None,
    extraction_year: int | None,
    name_confidence: float,
    register_confidence: float,
    *,
    meta: dict[str, Any] | None = None,
) -> list[Check]:
    config = rules()["validation"]
    checks: list[Check] = []

    if extraction_name:
        score = fuzz.token_set_ratio(clean(application.applicant_name), clean(extraction_name))
        matched = score >= float(config["name_fuzzy_threshold"])
        checks.append(
            Check(
                category="identity",
                field="Applicant name",
                result=Result.match.value if matched else Result.mismatch.value,
                severity=Severity.info.value if matched else Severity.critical.value,
                entered_value=application.applicant_name,
                uploaded_value=extraction_name,
                measured_value=f"{score:.0f}% similarity",
                required_value=f"at least {config['name_fuzzy_threshold']}%",
                confidence=name_confidence,
                detail=(
                    "Matches the name printed on the mark sheet."
                    if matched
                    else "The name on the mark sheet does not match the application."
                ),
                meta=meta,
            )
        )
    else:
        checks.append(
            Check(
                category="identity",
                field="Applicant name",
                result=Result.missing_upload.value,
                severity=Severity.warning.value,
                entered_value=application.applicant_name,
                detail="The candidate name could not be read from the mark sheet.",
                meta=meta,
            )
        )

    if extraction_register:
        left = re.sub(r"[^A-Z0-9]", "", class_record.register_number.upper())
        right = re.sub(r"[^A-Z0-9]", "", extraction_register.upper())
        matched = left == right
        low = register_confidence < float(config["register_number_min_confidence"])
        checks.append(
            Check(
                category="identity",
                field="Register number",
                result=(
                    Result.pending.value
                    if low
                    else (Result.match.value if matched else Result.mismatch.value)
                ),
                severity=(
                    Severity.warning.value
                    if low
                    else (Severity.info.value if matched else Severity.critical.value)
                ),
                entered_value=class_record.register_number,
                uploaded_value=extraction_register,
                confidence=register_confidence,
                detail=(
                    "The register number was read with low confidence; confirm it by eye."
                    if low
                    else (
                        "Matches the register number printed on the mark sheet."
                        if matched
                        else "The register number on the mark sheet does not match the application."
                    )
                ),
                meta=meta,
            )
        )
    else:
        checks.append(
            Check(
                category="identity",
                field="Register number",
                result=Result.missing_upload.value,
                severity=Severity.warning.value,
                entered_value=class_record.register_number,
                detail="The register number could not be read from the mark sheet.",
                meta=meta,
            )
        )

    if extraction_year:
        matched = int(extraction_year) == int(class_record.exam_year)
        checks.append(
            Check(
                category="identity",
                field="Examination year",
                result=Result.match.value if matched else Result.mismatch.value,
                severity=Severity.info.value if matched else Severity.warning.value,
                entered_value=str(class_record.exam_year),
                uploaded_value=str(extraction_year),
                detail=(
                    "Matches the session printed on the mark sheet."
                    if matched
                    else "The year printed on the mark sheet differs from the application."
                ),
                meta=meta,
            )
        )
    return checks


def _dedupe_subjects(rows: list[SubjectRow]) -> list[SubjectRow]:
    """Two uploaded sheets often repeat the same statement. Keep the clearest
    read of each subject/mark pair so the comparison does not invent extras."""

    seen: dict[tuple[str, float | None, float | None], SubjectRow] = {}
    for row in rows:
        key = (
            clean(normalize_subject(row.subject_raw).canonical),
            row.marks_obtained,
            row.max_marks,
        )
        if key not in seen or row.confidence > seen[key].confidence:
            seen[key] = row
    return list(seen.values())


def _correction_keys(subject_raw: str, subject_norm: str | None = None) -> list[str]:
    keys = [
        clean(subject_norm or ""),
        clean(normalize_subject(subject_raw).canonical),
        clean(subject_raw),
    ]
    return list(dict.fromkeys(key for key in keys if key))


def _correction_map(rows: list[ExtractedMark]) -> dict[str, dict[str, Any]]:
    """Index a previous run's admin corrections by the subject they belong to.

    The OCR read is replaced on every run, but a correction is a person's
    decision about that row, so it must survive the re-read. The key stays the
    subject the row was read as, never the corrected subject.
    """

    corrections: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.corrected_subject is None and row.corrected_marks is None:
            continue
        payload = {
            "subject": row.corrected_subject,
            "marks": row.corrected_marks,
            "by": row.corrected_by,
            "at": row.corrected_at,
        }
        for key in _correction_keys(row.subject_raw, row.subject_norm):
            corrections[key] = payload
    return corrections


def _effective_rows(rows: list[ExtractedMark]) -> list[SubjectRow]:
    return [
        SubjectRow(
            subject_raw=row.effective_subject,
            marks_obtained=row.effective_marks,
            max_marks=row.max_marks,
            grade=row.grade,
            confidence=row.confidence,
            page=row.page,
            bbox=row.bbox,
        )
        for row in rows
    ]


def _store_ocr(
    db: Session,
    document: Document,
    application: Application,
    extraction,
    *,
    status: str,
    error: str | None = None,
) -> list[SubjectRow]:
    result = document.ocr_result
    if result is None:
        result = OcrResult(document_id=document.id)
        db.add(result)
        document.ocr_result = result
    result.engine = extraction.engine or "tesseract"
    result.status = status
    result.raw_text = extraction.raw_text
    result.fields = {
        "kind": extraction.kind,
        "classification": extraction.classification,
        "name": extraction.name.value,
        "register_number": extraction.register_number.value,
        "exam_year": extraction.exam_year.value,
        "attributes": extraction.attributes,
        "warnings": extraction.warnings,
    }
    result.confidence = {
        "name": extraction.name.confidence,
        "register_number": extraction.register_number.confidence,
        "exam_year": extraction.exam_year.confidence,
        "subjects": [
            {"subject": row.subject_raw, "confidence": row.confidence}
            for row in extraction.subjects
        ],
    }
    result.page_count = len(extraction.pages)
    result.error = error
    result.duration_ms = extraction.duration_ms

    previous = list(
        db.scalars(
            select(ExtractedMark).where(ExtractedMark.document_id == document.id)
        ).all()
    )
    if status != RunStatus.completed.value:
        # A failed read must not erase the last good extraction or the
        # corrections a reviewer already made against it.
        return _effective_rows(previous)

    corrections = _correction_map(previous)
    db.execute(delete(ExtractedMark).where(ExtractedMark.document_id == document.id))
    stored: list[ExtractedMark] = []
    for row in extraction.subjects:
        match = normalize_subject(row.subject_raw)
        correction: dict[str, Any] = {}
        for key in _correction_keys(row.subject_raw, match.canonical):
            if key in corrections:
                correction = corrections[key]
                break
        mark = ExtractedMark(
            document_id=document.id,
            application_id=application.id,
            subject_raw=row.subject_raw,
            subject_norm=match.canonical,
            marks_obtained=row.marks_obtained,
            max_marks=row.max_marks,
            grade=row.grade,
            confidence=row.confidence,
            page=row.page,
            bbox=row.bbox,
            corrected_subject=correction.get("subject"),
            corrected_marks=correction.get("marks"),
            corrected_by=correction.get("by"),
            corrected_at=correction.get("at"),
        )
        db.add(mark)
        stored.append(mark)
    return _effective_rows(stored)


def _store_aadhaar(
    db: Session,
    document: Document,
    application: Application,
    extraction,
) -> None:
    number = extraction.sensitive.get("aadhaar_number")
    if not number:
        if document.aadhaar_record is not None:
            db.delete(document.aadhaar_record)
            document.aadhaar_record = None
        return
    record = document.aadhaar_record
    if record is None:
        record = AadhaarRecord(
            document_id=document.id,
            application_id=application.id,
        )
        db.add(record)
        document.aadhaar_record = record
    record.number_encrypted = encrypt_text(str(number))
    record.last4 = str(number)[-4:]
    record.checksum_valid = bool(extraction.sensitive.get("checksum_valid"))
    record.qr_status = str(extraction.sensitive.get("qr_status") or "not_detected")
    record.qr_last4 = extraction.sensitive.get("qr_last4")


def _required_field_checks(document: Document, extraction) -> list[Check]:
    config = rules()["documents"]["kinds"].get(document.kind, {})
    if not config.get("generic_required", True):
        return []
    checks: list[Check] = []
    label = document.kind_label
    for field in config.get("required_fields", []):
        if not _missing(_field_value(extraction, field)):
            continue
        field_label = _field_label(field)
        checks.append(
            Check(
                category="document",
                field=field_label,
                result=Result.missing_upload.value,
                severity=Severity.critical.value,
                uploaded_value=document.original_filename,
                detail=(
                    f"{field_label} could not be read from the {label.lower()}. "
                    "Ask for a clearer scan or enter the value during review."
                ),
                meta={
                    **_doc_meta(document),
                    "field": field,
                    "clause": f"the {field_label.lower()} could not be read from the {label.lower()}",
                },
            )
        )
    return checks


def _issue_date_check(
    document: Document,
    issued: date | None,
    *,
    months: int | None = None,
    tolerance_days: int = 0,
    label: str,
) -> list[Check]:
    if issued is None:
        return []
    today = date.today()
    meta = _doc_meta(document)
    if issued > today + timedelta(days=tolerance_days):
        return [
            Check(
                category="document",
                field="Issue date",
                result=Result.fail.value,
                severity=Severity.critical.value,
                uploaded_value=issued.isoformat(),
                required_value="not in the future",
                detail=f"The {label} is dated {issued.isoformat()}, which is in the future.",
                meta={
                    **meta,
                    "clause": f"the {label} is dated in the future",
                },
            )
        ]
    if months:
        expiry = _add_months(issued, months)
        if today > expiry:
            return [
                Check(
                    category="document",
                    field="Issue date",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=issued.isoformat(),
                    measured_value=f"expired {expiry.isoformat()}",
                    required_value=f"issued within the last {months} months",
                    detail=(
                        f"The {label} expired on {expiry.isoformat()}. "
                        f"Only certificates issued in the last {months} months are accepted."
                    ),
                    meta={
                        **meta,
                        "clause": f"the {label} expired on {expiry.isoformat()}",
                    },
                )
            ]
    return [
        Check(
            category="document",
            field="Issue date",
            result=Result.pass_.value,
            severity=Severity.info.value,
            uploaded_value=issued.isoformat(),
            detail=f"The {label} is current.",
            meta=meta,
        )
    ]


def _income_checks(
    application: Application,
    document: Document,
    extraction,
) -> list[Check]:
    checks = _document_name_check(application, document, extraction)
    config = rules()["income"]
    amount = extraction.attributes.get("annual_income")
    limit = float(config["max_annual_income"])
    meta = _doc_meta(document)
    if amount is not None:
        shown = f"INR {float(amount):,.0f}"
        if float(amount) > limit:
            checks.append(
                Check(
                    category="document",
                    field="Annual income",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=shown,
                    required_value=f"at most INR {limit:,.0f}",
                    difference=round(float(amount) - limit, 2),
                    detail=(
                        f"The certificate records {shown} annual income, above the "
                        f"INR {limit:,.0f} limit."
                    ),
                    meta={
                        **meta,
                        "clause": (
                            f"the income certificate shows {shown}, above the "
                            f"INR {limit:,.0f} limit"
                        ),
                    },
                )
            )
        else:
            checks.append(
                Check(
                    category="document",
                    field="Annual income",
                    result=Result.pass_.value,
                    severity=Severity.info.value,
                    uploaded_value=shown,
                    required_value=f"at most INR {limit:,.0f}",
                    detail=f"{shown} is within the INR {limit:,.0f} limit.",
                    meta=meta,
                )
            )
    issued = extraction.attributes.get("issue_date")
    checks.extend(
        _issue_date_check(
            document,
            date.fromisoformat(issued) if issued else None,
            months=int(config["validity_months"]),
            tolerance_days=int(config.get("future_tolerance_days", 0)),
            label="income certificate",
        )
    )
    return checks


def _community_checks(
    application: Application,
    document: Document,
    extraction,
) -> list[Check]:
    checks = _document_name_check(application, document, extraction)
    config = rules()["community"]
    value = extraction.attributes.get("community")
    meta = _doc_meta(document)
    if value:
        known = [str(item).upper() for item in config["known_values"]]
        normalised = str(value).upper()
        recognised = normalised in known or any(
            item and item in normalised for item in known if len(item) > 2
        )
        if recognised:
            checks.append(
                Check(
                    category="document",
                    field="Community",
                    result=Result.pass_.value,
                    severity=Severity.info.value,
                    uploaded_value=str(value),
                    detail="The certificate states a recognised community category.",
                    meta=meta,
                )
            )
        else:
            checks.append(
                Check(
                    category="document",
                    field="Community",
                    result=Result.pending.value,
                    severity=Severity.warning.value,
                    uploaded_value=str(value),
                    detail=(
                        f"The community {value!r} is not in the configured list. "
                        "A reviewer should confirm it."
                    ),
                    meta={
                        **meta,
                        "clause": (
                            f"the community certificate states {value}, which is not "
                            "in the accepted list"
                        ),
                    },
                )
            )
    issued = extraction.attributes.get("issue_date")
    checks.extend(
        _issue_date_check(
            document,
            date.fromisoformat(issued) if issued else None,
            tolerance_days=int(config.get("future_tolerance_days", 0)),
            label="community certificate",
        )
    )
    return checks


def _first_graduate_checks(
    application: Application,
    document: Document,
    extraction,
) -> list[Check]:
    checks = _document_name_check(application, document, extraction)
    config = rules()["first_graduate"]
    status = extraction.attributes.get("first_graduate")
    meta = _doc_meta(document)
    if status in ("yes", "no"):
        declared = "yes" if application.is_first_graduate else "no"
        shown = "First graduate" if status == "yes" else "Not a first graduate"
        if status == declared:
            checks.append(
                Check(
                    category="document",
                    field="First graduate status",
                    result=Result.pass_.value,
                    severity=Severity.info.value,
                    uploaded_value=shown,
                    entered_value="First graduate" if application.is_first_graduate else "Not claimed",
                    detail="The certificate agrees with the application.",
                    meta=meta,
                )
            )
        elif declared == "yes":
            checks.append(
                Check(
                    category="document",
                    field="First graduate status",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=shown,
                    entered_value="First graduate",
                    detail=(
                        "The application claims first graduate status but the "
                        "certificate says the applicant is not a first graduate."
                    ),
                    meta={
                        **meta,
                        "clause": (
                            "the first graduate certificate contradicts the "
                            "first graduate claim"
                        ),
                    },
                )
            )
        else:
            checks.append(
                Check(
                    category="document",
                    field="First graduate status",
                    result=Result.pending.value,
                    severity=Severity.warning.value,
                    uploaded_value=shown,
                    entered_value="Not claimed",
                    detail=(
                        "The certificate records first graduate status, but the "
                        "application did not claim it. A reviewer should confirm."
                    ),
                    meta={**meta, "clause": "the first graduate claim is unconfirmed"},
                )
            )
    issued = extraction.attributes.get("issue_date")
    checks.extend(
        _issue_date_check(
            document,
            date.fromisoformat(issued) if issued else None,
            tolerance_days=int(config.get("future_tolerance_days", 0)),
            label="first graduate certificate",
        )
    )
    return checks


def _aadhaar_checks(
    application: Application,
    document: Document,
    extraction,
) -> list[Check]:
    checks: list[Check] = []
    meta = _doc_meta(document)
    qr_config = rules()["aadhaar"]["qr"]
    number = extraction.sensitive.get("aadhaar_number")
    masked = extraction.attributes.get("aadhaar_number") or mask_number(number)
    if number:
        checksum_valid = bool(extraction.sensitive.get("checksum_valid") or verhoeff_valid(str(number)))
        if checksum_valid:
            checks.append(
                Check(
                    category="document",
                    field="Aadhaar number",
                    result=Result.pass_.value,
                    severity=Severity.info.value,
                    uploaded_value=masked,
                    detail=(
                        "The printed number passes the Verhoeff checksum. "
                        "Only the last four digits are displayed."
                    ),
                    meta=meta,
                )
            )
        else:
            checks.append(
                Check(
                    category="document",
                    field="Aadhaar number",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=masked,
                    detail="The printed Aadhaar number failed the Verhoeff checksum.",
                    meta={
                        **meta,
                        "clause": "the Aadhaar number failed the Verhoeff checksum",
                    },
                )
            )
    checks.extend(_document_name_check(application, document, extraction))

    extracted_dob = None
    stored_dob = extraction.attributes.get("date_of_birth")
    if stored_dob:
        try:
            extracted_dob = date.fromisoformat(str(stored_dob))
        except ValueError:
            extracted_dob = None
    comparison = dob_comparison(
        application.date_of_birth,
        extracted_dob,
        extraction.attributes.get("year_of_birth"),
    )
    if comparison:
        checks.append(
            Check(
                category="identity",
                field="Date of birth",
                result=(
                    Result.match.value if comparison["matched"] else Result.mismatch.value
                ),
                severity=(
                    Severity.info.value
                    if comparison["matched"]
                    else Severity.critical.value
                ),
                entered_value=comparison["entered"],
                uploaded_value=comparison["uploaded"],
                measured_value=comparison["measured"],
                detail=comparison["detail"],
                meta=meta,
            )
        )

    qr_status = extraction.attributes.get("qr_status") or "not_detected"
    if qr_status == "match":
        checks.append(
            Check(
                category="document",
                field="QR code",
                result=Result.pass_.value,
                severity=Severity.info.value,
                uploaded_value=extraction.attributes.get("qr_last4"),
                detail="The QR payload matches the printed Aadhaar number.",
                meta=meta,
            )
        )
    elif qr_status == "mismatch":
        checks.append(
            Check(
                category="document",
                field="QR code",
                result=Result.fail.value,
                severity=Severity.critical.value,
                uploaded_value=extraction.attributes.get("qr_last4"),
                detail="The QR payload does not match the printed Aadhaar number.",
                meta={
                    **meta,
                    "clause": "the Aadhaar QR code does not match the printed number",
                },
            )
        )
    elif qr_status == "unreadable":
        required = bool(qr_config.get("required"))
        checks.append(
            Check(
                category="document",
                field="QR code",
                result=Result.fail.value if required else Result.pending.value,
                severity=(
                    Severity.critical.value if required else Severity.warning.value
                ),
                detail="A QR code was found but its payload could not be read.",
                meta=meta,
            )
        )
    else:
        required = bool(qr_config.get("required"))
        checks.append(
            Check(
                category="document",
                field="QR code",
                result=Result.fail.value if required else Result.pending.value,
                severity=(
                    Severity.critical.value if required else Severity.warning.value
                ),
                detail="No readable QR code was found; the printed number was still checked.",
                meta=meta,
            )
        )
    return checks


def _supporting_checks(
    application: Application,
    document: Document,
    extraction,
) -> list[Check]:
    kind = document.kind
    if kind == DocumentKind.aadhaar.value:
        return _aadhaar_checks(application, document, extraction)
    if kind == DocumentKind.income_certificate.value:
        return _income_checks(application, document, extraction)
    if kind == DocumentKind.community_certificate.value:
        return _community_checks(application, document, extraction)
    if kind == DocumentKind.first_graduate_certificate.value:
        return _first_graduate_checks(application, document, extraction)
    return []


def _sync_review(
    db: Session,
    application: Application,
    run: ValidationRun,
    checks: list[Check],
    reasons: list[str],
) -> None:
    critical = [check for check in checks if check.severity == Severity.critical.value]
    warnings = [check for check in checks if check.severity == Severity.warning.value]
    passed = not critical and not warnings
    existing = application.review_item
    if existing is None:
        existing = db.scalar(
            select(ReviewItem).where(ReviewItem.application_id == application.id)
        )
    now = utcnow()

    if passed:
        application.status = ApplicationStatus.verified.value
        if existing is not None and existing.status in (
            ReviewStatus.open.value,
            ReviewStatus.in_review.value,
        ):
            existing.status = ReviewStatus.approved.value
            existing.decision_comment = (
                "Closed automatically after a passing validation run."
            )
            existing.decided_at = now
        return

    application.status = ApplicationStatus.needs_review.value
    if existing is None:
        existing = ReviewItem(application_id=application.id, status=ReviewStatus.open.value)
        db.add(existing)
        application.review_item = existing
    existing.run_id = run.id
    existing.status = ReviewStatus.open.value
    existing.reasons = reasons[:20]
    existing.priority = 20 if critical else 50
    existing.decision_comment = None
    existing.decided_by = None
    existing.decided_at = None


def _perform(db: Session, application: Application, run: ValidationRun) -> None:
    checks: list[Check] = []
    reasons: list[str] = []
    extractions = []
    sources: list[SourceRecord] = []
    photo_analyses: list[PhotoAnalysis] = []
    config = rules()
    comparison_checks: list[Check] = []
    totals = {"matched": 0, "mismatched": 0, "missing": 0, "extra": 0}
    subjects_total = 0

    documents = list(application.documents)
    marksheets = [doc for doc in documents if doc.kind in MARK_SHEET_KINDS]
    photos = [doc for doc in documents if doc.kind == DocumentKind.photo.value]
    supporting = [doc for doc in documents if doc.kind in SUPPORTING_KINDS]
    records = {record.class_level: record for record in application.education_records}

    for document in documents:
        if document.duplicate_of_id:
            checks.append(
                Check(
                    category="duplicate",
                    field="Duplicate upload",
                    result=Result.fail.value,
                    severity=Severity.warning.value,
                    uploaded_value=document.original_filename,
                    detail=(
                        f"This file matches another upload (document #{document.duplicate_of_id}). "
                        "A duplicate may mean the wrong file was attached."
                    ),
                    meta=_doc_meta(document),
                )
            )

    for document in marksheets:
        level = _class_level(document.kind)
        meta = _doc_meta(document)
        label = f"Class {level} mark sheet" if level else document.kind_label
        class_record = records.get(level) if level is not None else None
        if class_record is None:
            checks.append(
                Check(
                    category="document",
                    field=f"Class {level} record",
                    result=Result.missing_entry.value,
                    severity=Severity.warning.value,
                    uploaded_value=document.original_filename,
                    detail=(
                        f"A {label} was attached, but no Class {level} record was entered "
                        "on the application."
                    ),
                    meta={
                        **meta,
                        "clause": (
                            f"a {label} was attached but no Class {level} record was entered"
                        ),
                    },
                )
            )
            continue

        try:
            data = read_document_bytes(document)
            result = extract_document(data, document.mime_type, document.kind)
        except (OcrUnavailable, FileNotFoundError) as exc:
            failed = _plain_failure(document.original_filename)
            _store_ocr(
                db,
                document,
                application,
                failed,
                status=RunStatus.failed.value,
                error=str(exc),
            )
            checks.append(
                Check(
                    category="ocr",
                    field=f"{label} reading",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=document.original_filename,
                    detail=str(exc),
                    meta=meta,
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - one corrupt file must not sink the run
            logger.exception("OCR failed for document %s", document.id)
            failed = _plain_failure(document.original_filename)
            _store_ocr(
                db,
                document,
                application,
                failed,
                status=RunStatus.failed.value,
                error=str(exc),
            )
            checks.append(
                Check(
                    category="ocr",
                    field=f"{label} reading",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=document.original_filename,
                    detail="The document could not be read. Ask for a clearer scan.",
                    meta=meta,
                )
            )
            continue

        effective_rows = _store_ocr(
            db, document, application, result, status=RunStatus.completed.value
        )
        extractions.append(result)
        source = _source_record(
            document,
            result,
            f"Class {level} mark sheet" if level else document.kind_label,
        )
        if source is not None:
            sources.append(source)
        for warning in result.warnings:
            checks.append(
                Check(
                    category="ocr",
                    field=f"{label} reading",
                    result=Result.pending.value,
                    severity=Severity.warning.value,
                    uploaded_value=document.original_filename,
                    detail=warning,
                    confidence=result.name.confidence or None,
                    meta=meta,
                )
            )

        checks.extend(
            _identity_checks(
                application,
                class_record,
                result.name.value,
                result.register_number.value,
                result.exam_year.value,
                result.name.confidence,
                result.register_number.confidence,
                meta=meta,
            )
        )

        entered_marks = list(class_record.marks)
        rows = _dedupe_subjects(effective_rows)
        comparison = compare_marks(
            [
                EnteredMarkValue(
                    subject=mark.subject,
                    marks=mark.marks_obtained,
                    max_marks=mark.max_marks,
                )
                for mark in entered_marks
            ],
            rows,
        )
        for check in comparison.checks:
            check.meta = {**(check.meta or {}), **meta}
        checks.extend(comparison.checks)
        comparison_checks.extend(comparison.checks)
        totals["matched"] += comparison.matched
        totals["mismatched"] += comparison.mismatched
        totals["missing"] += comparison.missing
        totals["extra"] += comparison.extra
        subjects_total += len(rows)

        entered_keys = {
            clean(normalize_subject(mark.subject).canonical) for mark in entered_marks
        }
        extracted_keys = {
            clean(normalize_subject(row.subject_raw).canonical) for row in rows
        }
        # A subject the applicant entered but the sheet lacks is already reported
        # by the comparison layer. Do not repeat the same gap as completeness.
        covered_missing = {
            clean(check.subject_norm or check.field)
            for check in comparison.checks
            if check.result == Result.missing_upload.value
        }
        required_subjects = config["subjects"]["classes"].get(
            str(level), config["subjects"]["required"]
        )
        for required in required_subjects:
            key = clean(required)
            if key not in entered_keys:
                checks.append(
                    Check(
                        category="completeness",
                        field=required,
                        subject_norm=required,
                        result=Result.missing_entry.value,
                        severity=Severity.warning.value,
                        detail=(
                            f"{required} is required for Class {level} but was not "
                            "entered on the application."
                        ),
                        meta=meta,
                    )
                )
            if key not in extracted_keys and key not in covered_missing:
                checks.append(
                    Check(
                        category="completeness",
                        field=required,
                        subject_norm=required,
                        result=Result.missing_upload.value,
                        severity=Severity.critical.value,
                        detail=(
                            f"{required} is required for Class {level} but is missing "
                            "from the mark sheet."
                        ),
                        meta=meta,
                    )
                )

    if not any(_class_level(document.kind) == 12 for document in marksheets):
        checks.append(
            Check(
                category="completeness",
                field="Class 12 mark sheet",
                result=Result.missing_upload.value,
                severity=Severity.critical.value,
                detail="A Class 12 mark sheet is required before the checks can pass.",
                meta={"kind": DocumentKind.marksheet_12.value, "label": "Class 12 mark sheet"},
            )
        )

    for document in supporting:
        meta = _doc_meta(document)
        label = document.kind_label
        try:
            data = read_document_bytes(document)
            result = extract_document(data, document.mime_type, document.kind)
        except (OcrUnavailable, FileNotFoundError) as exc:
            failed = _plain_failure(document.original_filename)
            _store_ocr(
                db,
                document,
                application,
                failed,
                status=RunStatus.failed.value,
                error=str(exc),
            )
            checks.append(
                Check(
                    category="ocr",
                    field=f"{label} reading",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=document.original_filename,
                    detail=str(exc),
                    meta=meta,
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - one corrupt file must not sink the run
            logger.exception("OCR failed for document %s", document.id)
            failed = _plain_failure(document.original_filename)
            _store_ocr(
                db,
                document,
                application,
                failed,
                status=RunStatus.failed.value,
                error=str(exc),
            )
            checks.append(
                Check(
                    category="ocr",
                    field=f"{label} reading",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=document.original_filename,
                    detail="The document could not be read. Ask for a clearer scan.",
                    meta=meta,
                )
            )
            continue

        _store_ocr(db, document, application, result, status=RunStatus.completed.value)
        extractions.append(result)
        if document.kind == DocumentKind.aadhaar.value:
            _store_aadhaar(db, document, application, result)
        source = _source_record(document, result, document.kind_label)
        if source is not None:
            sources.append(source)
        for warning in result.warnings:
            checks.append(
                Check(
                    category="ocr",
                    field=f"{label} reading",
                    result=Result.pending.value,
                    severity=Severity.warning.value,
                    uploaded_value=document.original_filename,
                    detail=warning,
                    meta=meta,
                )
            )
        checks.extend(_required_field_checks(document, result))
        checks.extend(_supporting_checks(application, document, result))

    identity_matrix = build_identity_matrix(application, sources)
    checks.extend(_consistency_findings(application, sources))
    checks.extend(class_year_checks(records))
    checks.extend(subject_group_checks(records))

    for document in photos:
        try:
            photo_data = read_document_bytes(document)
            analysis = analyze_photo(photo_data, document.mime_type)
        except FileNotFoundError:
            checks.append(
                _photo_failure(
                    document,
                    "The stored photograph is missing. Upload it again to run the photo checks.",
                )
            )
            continue
        except PhotoUnreadable as exc:
            checks.append(_photo_failure(document, str(exc)))
            continue
        except Exception:  # noqa: BLE001 - a broken photo must not sink the run
            logger.exception("Photo check failed for document %s", document.id)
            checks.append(
                _photo_failure(
                    document,
                    "The photograph could not be checked. Ask for a clearer JPEG or PNG.",
                )
            )
            continue
        photo_analyses.append(analysis)
        checks.extend(_photo_to_checks(document, analysis))

    checks.sort(key=lambda check: CATEGORY_ORDER.get(check.category, 9))
    for index, check in enumerate(checks):
        finding = _from_check(application, check, index)
        finding.run_id = run.id
        db.add(finding)
        if check.severity in (Severity.critical.value, Severity.warning.value):
            label = check.field
            reasons.append(f"{label}: {check.detail or check.result}")

    critical = sum(1 for check in checks if check.severity == Severity.critical.value)
    warnings = sum(1 for check in checks if check.severity == Severity.warning.value)
    photo_failures = sum(
        1
        for check in checks
        if check.category == "photo" and check.severity == Severity.critical.value
    )
    photo_notes = sum(
        1
        for check in checks
        if check.category == "photo" and check.severity == Severity.warning.value
    )
    if critical:
        overall = "fail"
        lead = _join(_critical_clauses(checks)) or "The application did not pass the checks"
        lead = lead[0].upper() + lead[1:]
        verdict = f"{lead}. Sent to the review queue."
        if warnings:
            verdict += f" {_count(warnings, 'warning')} also noted."
    elif warnings:
        overall = "review"
        verdict = (
            f"No critical issues. {_count(warnings, 'warning')} "
            f"{_verb(warnings, 'needs', 'need')} a reviewer's confirmation."
        )
    else:
        overall = "pass"
        verdict = (
            f"All checks passed. {_count(totals['matched'], 'subject')} "
            f"{_verb(totals['matched'], 'matches', 'match')} the mark sheet and "
            "identity details are consistent."
        )

    document_summaries = []
    for document in documents:
        related = [
            check
            for check in checks
            if (check.meta or {}).get("document_id") == document.id
        ]
        document_critical = sum(
            1 for check in related if check.severity == Severity.critical.value
        )
        document_warnings = sum(
            1 for check in related if check.severity == Severity.warning.value
        )
        if document_critical:
            status = "fail"
        elif document_warnings:
            status = "review"
        elif related:
            status = "pass"
        else:
            status = "pending"
        document_summaries.append(
            {
                "id": document.id,
                "kind": document.kind,
                "label": document.kind_label,
                "filename": document.original_filename,
                "status": status,
                "findings": len(related),
                "critical": document_critical,
                "warnings": document_warnings,
                "classification": document.classification,
                "masked_aadhaar": document.masked_aadhaar,
            }
        )

    ocr_confidence = comparison_confidence(comparison_checks)
    run.status = RunStatus.completed.value
    run.overall = overall
    run.finished_at = utcnow()
    run.summary = {
        "verdict": verdict,
        "critical": critical,
        "warnings": warnings,
        "matched": totals["matched"],
        "mismatched": totals["mismatched"],
        "missing": totals["missing"],
        "extra": totals["extra"],
        "subjects_on_sheet": subjects_total,
        "marksheets": len(marksheets),
        "photos": len(photos),
        "supporting_documents": len(supporting),
        "document_failures": sum(1 for item in document_summaries if item["status"] == "fail"),
        "photo_failures": photo_failures,
        "photo_warnings": photo_notes,
        "photo_metrics": [analysis.metrics for analysis in photo_analyses],
        "ocr_confidence": ocr_confidence,
        "identity_matrix": identity_matrix,
        "identity_mismatches": identity_matrix["mismatched"],
        "consistency_findings": sum(
            1 for check in checks if check.category == "consistency"
        ),
        "engine": next((result.engine for result in extractions if result.engine), None),
        "documents_read": len(extractions),
        "documents": document_summaries,
    }
    _sync_review(db, application, run, checks, reasons)

    write_audit(
        db,
        action="validation.completed",
        entity_type="validation_run",
        entity_id=run.id,
        application_id=application.id,
        detail={
            "overall": overall,
            "critical": critical,
            "warnings": warnings,
            "matched": totals["matched"],
            "mismatched": totals["mismatched"],
            "subjects": subjects_total,
            "photo_failures": photo_failures,
            "identity_mismatches": identity_matrix["mismatched"],
            "supporting_documents": len(supporting),
            "document_failures": sum(
                1 for item in document_summaries if item["status"] == "fail"
            ),
        },
    )


def _plain_failure(filename: str):
    from app.ocr.types import Extraction

    extraction = Extraction(engine="tesseract", raw_text="")
    extraction.warnings = [f"{filename} could not be read."]
    return extraction


def run_validation(run_id: int, session_factory: SessionFactory) -> None:
    """Background entry point. Owns its session end to end, so FastAPI request
    dependencies and their transactions are already closed by the time OCR runs."""

    db = session_factory()
    try:
        run = db.get(ValidationRun, run_id)
        if run is None:
            return
        application = db.scalar(
            select(Application)
            .options(
                selectinload(Application.education_records).selectinload(
                    EducationRecord.marks
                ),
                selectinload(Application.documents).selectinload(Document.ocr_result),
                selectinload(Application.review_item),
            )
            .where(Application.id == run.application_id)
        )
        if application is None:
            run.status = RunStatus.failed.value
            run.error = "The application was removed before validation finished."
            db.commit()
            return

        run.status = RunStatus.running.value
        run.started_at = utcnow()
        application.status = ApplicationStatus.processing.value
        db.commit()

        try:
            _perform(db, application, run)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - surface a usable failure
            db.rollback()
            logger.exception("Validation run %s failed", run_id)
            run = db.get(ValidationRun, run_id)
            if run is not None:
                run.status = RunStatus.failed.value
                run.error = str(exc)[:500]
                run.finished_at = utcnow()
                failed_application = db.get(Application, run.application_id)
                if failed_application is not None:
                    failed_application.status = ApplicationStatus.needs_review.value
                write_audit(
                    db,
                    action="validation.failed",
                    entity_type="validation_run",
                    entity_id=run_id,
                    application_id=run.application_id,
                    detail={"error": str(exc)[:200]},
                )
                db.commit()
    finally:
        db.close()
