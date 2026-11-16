from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import rules
from app.models.application import Application
from app.models.base import utcnow
from app.models.document import Document, ExtractedMark, OcrResult
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
from app.services.subjects import clean, normalize_subject, canonical_required
from app.services.storage import read_document_bytes
from app.validators.photo import PhotoAnalysis, PhotoUnreadable, analyze_photo

logger = logging.getLogger("maatram.validation")

SessionFactory = Callable[[], Session]

CATEGORY_ORDER = {
    "identity": 0,
    "mark": 1,
    "completeness": 2,
    "duplicate": 3,
    "photo": 4,
    "format": 5,
    "ocr": 6,
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
    )


def _identity_checks(
    application: Application,
    extraction_name: str | None,
    extraction_register: str | None,
    extraction_year: int | None,
    name_confidence: float,
    register_confidence: float,
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
            )
        )

    if extraction_register:
        left = re.sub(r"[^A-Z0-9]", "", application.register_number.upper())
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
                entered_value=application.register_number,
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
            )
        )
    else:
        checks.append(
            Check(
                category="identity",
                field="Register number",
                result=Result.missing_upload.value,
                severity=Severity.warning.value,
                entered_value=application.register_number,
                detail="The register number could not be read from the mark sheet.",
            )
        )

    if extraction_year:
        matched = int(extraction_year) == int(application.exam_year)
        checks.append(
            Check(
                category="identity",
                field="Examination year",
                result=Result.match.value if matched else Result.mismatch.value,
                severity=Severity.info.value if matched else Severity.warning.value,
                entered_value=str(application.exam_year),
                uploaded_value=str(extraction_year),
                detail=(
                    "Matches the session printed on the mark sheet."
                    if matched
                    else "The year printed on the mark sheet differs from the application."
                ),
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


def _store_ocr(
    db: Session,
    document: Document,
    application: Application,
    extraction,
    *,
    status: str,
    error: str | None = None,
) -> None:
    result = document.ocr_result
    if result is None:
        result = OcrResult(document_id=document.id)
        db.add(result)
        document.ocr_result = result
    result.engine = extraction.engine or "tesseract"
    result.status = status
    result.raw_text = extraction.raw_text
    result.fields = {
        "name": extraction.name.value,
        "register_number": extraction.register_number.value,
        "exam_year": extraction.exam_year.value,
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

    db.execute(delete(ExtractedMark).where(ExtractedMark.document_id == document.id))
    for row in extraction.subjects:
        match = normalize_subject(row.subject_raw)
        db.add(
            ExtractedMark(
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
            )
        )


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
    photo_analyses: list[PhotoAnalysis] = []
    extraction = None

    documents = application.documents
    marksheets = [doc for doc in documents if doc.kind == DocumentKind.marksheet.value]
    photos = [doc for doc in documents if doc.kind == DocumentKind.photo.value]

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
                )
            )

    for document in marksheets:
        try:
            data = read_document_bytes(document)
            result = extract_document(data, document.mime_type)
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
                    field="Mark sheet reading",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=document.original_filename,
                    detail=str(exc),
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
                    field="Mark sheet reading",
                    result=Result.fail.value,
                    severity=Severity.critical.value,
                    uploaded_value=document.original_filename,
                    detail="The document could not be read. Ask for a clearer scan.",
                )
            )
            continue

        _store_ocr(db, document, application, result, status=RunStatus.completed.value)
        extractions.append(result)
        if extraction is None or result.name.confidence > extraction.name.confidence:
            extraction = result
        for warning in result.warnings:
            checks.append(
                Check(
                    category="ocr",
                    field="Mark sheet reading",
                    result=Result.pending.value,
                    severity=Severity.warning.value,
                    uploaded_value=document.original_filename,
                    detail=warning,
                    confidence=result.name.confidence or None,
                )
            )

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

    if extraction is not None:
        checks.extend(
            _identity_checks(
                application,
                extraction.name.value,
                extraction.register_number.value,
                extraction.exam_year.value,
                extraction.name.confidence,
                extraction.register_number.confidence,
            )
        )

    subjects = _dedupe_subjects(
        [row for result in extractions for row in result.subjects]
    )
    comparison = compare_marks(
        [
            EnteredMarkValue(
                subject=mark.subject,
                marks=mark.marks_obtained,
                max_marks=mark.max_marks,
            )
            for mark in application.entered_marks
        ],
        subjects,
    )
    checks.extend(comparison.checks)

    entered_keys = {
        clean(normalize_subject(mark.subject).canonical) for mark in application.entered_marks
    }
    extracted_keys = {
        clean(normalize_subject(row.subject_raw).canonical) for row in subjects
    }
    # A subject the applicant entered but the sheet lacks is already reported by
    # the comparison layer. Do not repeat the same gap as a completeness check.
    covered_missing = {
        clean(check.subject_norm or check.field)
        for check in comparison.checks
        if check.result == Result.missing_upload.value
    }
    for required in canonical_required():
        key = clean(required)
        if key not in entered_keys:
            checks.append(
                Check(
                    category="completeness",
                    field=required,
                    subject_norm=required,
                    result=Result.missing_entry.value,
                    severity=Severity.warning.value,
                    detail=f"{required} is required but was not entered on the application.",
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
                    detail=f"{required} is required but is missing from the mark sheet.",
                )
            )

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
        matched = comparison.matched
        verdict = (
            f"All checks passed. {_count(matched, 'subject')} "
            f"{_verb(matched, 'matches', 'match')} the mark sheet and identity details are consistent."
        )

    ocr_confidence = comparison_confidence(comparison.checks)
    run.status = RunStatus.completed.value
    run.overall = overall
    run.finished_at = utcnow()
    run.summary = {
        "verdict": verdict,
        "critical": critical,
        "warnings": warnings,
        "matched": comparison.matched,
        "mismatched": comparison.mismatched,
        "missing": comparison.missing,
        "extra": comparison.extra,
        "subjects_on_sheet": len(subjects),
        "marksheets": len(marksheets),
        "photos": len(photos),
        "photo_failures": photo_failures,
        "photo_warnings": photo_notes,
        "photo_metrics": [analysis.metrics for analysis in photo_analyses],
        "ocr_confidence": ocr_confidence,
        "engine": extraction.engine if extraction else None,
        "documents_read": len(extractions),
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
            "matched": comparison.matched,
            "mismatched": comparison.mismatched,
            "subjects": len(subjects),
            "photo_failures": photo_failures,
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
                selectinload(Application.entered_marks),
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
