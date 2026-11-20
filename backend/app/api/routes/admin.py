from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import rules
from app.db.session import get_db, get_session_factory
from app.models.accuracy import AccuracyRun
from app.models.application import Application
from app.models.document import Document, ExtractedMark
from app.models.enums import ApplicationStatus, ReviewStatus, Role, RunStatus
from app.models.review import AuditLog, ReviewItem
from app.models.user import User
from app.models.validation import Finding, ValidationRun
from app.schemas.application import (
    ApplicationList,
    ApplicationOut,
    MarkCorrection,
    ReviewDecision,
)
from app.services.audit import write_audit
from app.services.evaluation import latest_run_summary, run_evaluation
from app.services.validation import run_validation

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    status_rows = db.execute(
        select(Application.status, func.count()).group_by(Application.status)
    ).all()
    by_status = {status: count for status, count in status_rows}
    total = sum(by_status.values())
    students = db.scalar(select(func.count()).select_from(User).where(User.role == Role.student.value)) or 0
    open_reviews = (
        db.scalar(
            select(func.count()).select_from(ReviewItem).where(ReviewItem.status == "open")
        )
        or 0
    )
    mismatches = (
        db.scalar(select(func.count()).select_from(Finding).where(Finding.result == "mismatch")) or 0
    )
    photo_fails = (
        db.scalar(
            select(func.count())
            .select_from(Finding)
            .where(Finding.category == "photo", Finding.result == "fail")
        )
        or 0
    )
    recent = db.scalars(
        select(Application).order_by(Application.created_at.desc()).limit(6)
    ).all()
    processing = (
        db.scalar(
            select(func.count())
            .select_from(ValidationRun)
            .where(
                ValidationRun.status.in_(
                    [RunStatus.pending.value, RunStatus.running.value]
                )
            )
        )
        or 0
    )
    run_rows = db.execute(
        select(ValidationRun, Application)
        .join(Application, Application.id == ValidationRun.application_id)
        .where(
            ValidationRun.status.in_(
                [RunStatus.completed.value, RunStatus.failed.value]
            )
        )
        .order_by(ValidationRun.created_at.desc(), ValidationRun.id.desc())
        .limit(8)
    ).all()
    activity = []
    for run, application in run_rows:
        summary = run.summary or {}
        activity.append(
            {
                "id": run.id,
                "application_id": application.id,
                "reference": application.reference,
                "applicant_name": application.applicant_name,
                "class_12_year": application.class_12.exam_year if application.class_12 else None,
                "status": run.status,
                "overall": run.overall,
                "verdict": summary.get("verdict"),
                "matched": summary.get("matched", 0),
                "mismatched": summary.get("mismatched", 0),
                "critical": summary.get("critical", 0),
                "warnings": summary.get("warnings", 0),
                "engine": summary.get("engine"),
                "ocr_confidence": summary.get("ocr_confidence"),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "error": run.error,
            }
        )
    return {
        "total_applications": total,
        "students": students,
        "by_status": by_status,
        "open_reviews": open_reviews,
        "mismatch_findings": mismatches,
        "photo_failures": photo_fails,
        "recent": [ApplicationOut.model_validate(row).model_dump(mode="json") for row in recent],
        "verified": by_status.get(ApplicationStatus.verified.value, 0)
        + by_status.get(ApplicationStatus.approved.value, 0),
        "processing": processing,
        "activity": activity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/reviews")
def review_queue(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    status_filter: str = Query(default="active", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    allowed = {status.value for status in ReviewStatus} | {"active", "all"}
    if status_filter not in allowed:
        raise HTTPException(status_code=422, detail="Unknown review status.")

    counts = {status.value: 0 for status in ReviewStatus}
    for status, count in db.execute(
        select(ReviewItem.status, func.count()).group_by(ReviewItem.status)
    ).all():
        if status in counts:
            counts[status] = count
    counts["active"] = counts[ReviewStatus.open.value] + counts[ReviewStatus.in_review.value]
    counts["all"] = sum(counts[status.value] for status in ReviewStatus)

    conditions = []
    if status_filter == "active":
        conditions.append(
            ReviewItem.status.in_(
                [ReviewStatus.open.value, ReviewStatus.in_review.value]
            )
        )
    elif status_filter != "all":
        conditions.append(ReviewItem.status == status_filter)

    total = (
        db.scalar(
            select(func.count()).select_from(ReviewItem).where(*conditions)
        )
        or 0
    )
    rows = db.execute(
        select(ReviewItem, Application, ValidationRun)
        .join(Application, Application.id == ReviewItem.application_id)
        .outerjoin(ValidationRun, ValidationRun.id == ReviewItem.run_id)
        .where(*conditions)
        .order_by(ReviewItem.priority.asc(), ReviewItem.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    actor_ids = {
        actor_id
        for item, _, _ in rows
        for actor_id in (item.assigned_to, item.decided_by)
        if actor_id is not None
    }
    emails = (
        dict(
            db.execute(
                select(User.id, User.email).where(User.id.in_(actor_ids))
            ).all()
        )
        if actor_ids
        else {}
    )

    items = []
    for item, application, run in rows:
        summary = (run.summary or {}) if run is not None else {}
        items.append(
            {
                "id": item.id,
                "application_id": application.id,
                "reference": application.reference,
                "applicant_name": application.applicant_name,
                "class_12_year": application.class_12.exam_year if application.class_12 else None,
                "application_status": application.status,
                "status": item.status,
                "priority": item.priority,
                "reasons": item.reasons or [],
                "run_id": item.run_id,
                "overall": run.overall if run is not None else None,
                "matched": summary.get("matched", 0),
                "mismatched": summary.get("mismatched", 0),
                "critical": summary.get("critical", 0),
                "warnings": summary.get("warnings", 0),
                "ocr_confidence": summary.get("ocr_confidence"),
                "assigned_to_email": emails.get(item.assigned_to),
                "decided_by_email": emails.get(item.decided_by),
                "decision_comment": item.decision_comment,
                "decided_at": item.decided_at.isoformat() if item.decided_at else None,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "run_finished_at": run.finished_at.isoformat() if run and run.finished_at else None,
            }
        )
    return {
        "items": items,
        "counts": counts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _review_for_decision(db: Session, review_id: int) -> tuple[ReviewItem, Application]:
    item = db.get(ReviewItem, review_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found.")
    if item.status not in (ReviewStatus.open.value, ReviewStatus.in_review.value):
        raise HTTPException(status_code=409, detail="This review item was already decided.")
    application = db.get(Application, item.application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return item, application


def _decide_review(
    review_id: int,
    decision: str,
    payload: ReviewDecision,
    request: Request,
    db: Session,
    admin: User,
) -> dict:
    item, application = _review_for_decision(db, review_id)
    now = datetime.now(timezone.utc)
    item.status = decision
    item.decision_comment = payload.comment
    item.decided_by = admin.id
    item.decided_at = now
    if item.assigned_to is None:
        item.assigned_to = admin.id
    application.status = (
        ApplicationStatus.approved.value
        if decision == ReviewStatus.approved.value
        else ApplicationStatus.rejected.value
    )
    write_audit(
        db,
        action=f"review.{decision}",
        entity_type="review_item",
        entity_id=item.id,
        application_id=application.id,
        actor_id=admin.id,
        actor_email=admin.email,
        detail={
            "reference": application.reference,
            "run_id": item.run_id,
            "comment": payload.comment,
        },
        request=request,
    )
    db.commit()
    return {
        "id": item.id,
        "status": item.status,
        "application_id": application.id,
        "application_status": application.status,
        "decided_at": now.isoformat(),
        "decided_by_email": admin.email,
    }


@router.post("/reviews/{review_id}/approve")
def approve_review(
    review_id: int,
    payload: ReviewDecision,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    return _decide_review(
        review_id, ReviewStatus.approved.value, payload, request, db, admin
    )


@router.post("/reviews/{review_id}/reject")
def reject_review(
    review_id: int,
    payload: ReviewDecision,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    return _decide_review(
        review_id, ReviewStatus.rejected.value, payload, request, db, admin
    )


@router.patch("/documents/{document_id}/marks/{mark_id}")
def correct_extracted_mark(
    document_id: int,
    mark_id: int,
    payload: MarkCorrection,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    session_factory=Depends(get_session_factory),
) -> dict:
    """Store an admin correction and re-check the application.

    The corrected value is kept separately from the OCR read so the original
    evidence stays visible. The next run applies it when comparing marks and
    when showing the extracted rows, so a corrected subject can clear exactly
    the finding it was meant to fix.
    """

    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    mark = db.get(ExtractedMark, mark_id)
    if mark is None or mark.document_id != document.id:
        raise HTTPException(
            status_code=404, detail="Extracted mark not found on this document."
        )
    application = db.get(Application, document.application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if application.status in (
        ApplicationStatus.approved.value,
        ApplicationStatus.rejected.value,
    ):
        raise HTTPException(
            status_code=409,
            detail="This application has already been decided and cannot be corrected.",
        )
    active = db.scalar(
        select(ValidationRun.id).where(
            ValidationRun.application_id == application.id,
            ValidationRun.status.in_(
                [RunStatus.pending.value, RunStatus.running.value]
            ),
        )
    )
    if active:
        raise HTTPException(
            status_code=409, detail="Checks are already running on this application."
        )

    subject = " ".join(payload.subject.split()) if payload.subject else None
    before = {
        "subject": mark.corrected_subject or mark.subject_raw,
        "marks_obtained": (
            mark.corrected_marks
            if mark.corrected_marks is not None
            else mark.marks_obtained
        ),
    }
    if subject:
        mark.corrected_subject = subject
    mark.corrected_marks = payload.marks_obtained
    mark.corrected_by = admin.id
    mark.corrected_at = datetime.now(timezone.utc)
    after = {
        "subject": mark.corrected_subject or mark.subject_raw,
        "marks_obtained": mark.corrected_marks,
    }

    run = ValidationRun(application_id=application.id, status=RunStatus.pending.value)
    application.status = ApplicationStatus.processing.value
    db.add(run)
    db.flush()
    write_audit(
        db,
        action="mark.corrected",
        entity_type="extracted_mark",
        entity_id=mark.id,
        application_id=application.id,
        actor_id=admin.id,
        actor_email=admin.email,
        detail={
            "reference": application.reference,
            "document_id": document.id,
            "document_label": document.kind_label,
            "filename": document.original_filename,
            "run_id": run.id,
            "before": before,
            "after": after,
        },
        request=request,
    )
    db.commit()
    db.refresh(run)
    db.refresh(mark)

    background.add_task(run_validation, run.id, session_factory)
    return {
        "mark": {
            "id": mark.id,
            "document_id": mark.document_id,
            "subject_raw": mark.subject_raw,
            "subject_norm": mark.subject_norm,
            "marks_obtained": mark.marks_obtained,
            "max_marks": mark.max_marks,
            "grade": mark.grade,
            "confidence": mark.confidence,
            "page": mark.page,
            "corrected_subject": mark.corrected_subject,
            "corrected_marks": mark.corrected_marks,
        },
        "run": {"id": run.id, "status": run.status},
    }


@router.get("/students", response_model=list[dict])
def students(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict]:
    rows = db.scalars(select(User).where(User.role == Role.student.value).order_by(User.created_at.desc())).all()
    counts = dict(
        db.execute(
            select(Application.student_id, func.count()).group_by(Application.student_id)
        ).all()
    )
    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "created_at": user.created_at.isoformat(),
            "applications": counts.get(user.id, 0),
            "volunteer_activities": user.volunteer_activities,
            "achievements": user.achievements,
        }
        for user in rows
    ]


@router.get("/audit")
def audit_log(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    action: str | None = None,
    application_id: int | None = None,
) -> dict:
    statement = select(AuditLog)
    if action:
        statement = statement.where(AuditLog.action == action)
    if application_id:
        statement = statement.where(AuditLog.application_id == application_id)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "total": total,
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "application_id": row.application_id,
                "actor_email": row.actor_email,
                "detail": row.detail or {},
                "ip": row.ip,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


def _run_headline(run: AccuracyRun) -> dict:
    summary = run.summary or {}
    return {
        "id": run.id,
        "dataset": run.dataset,
        "total_cases": run.total_cases,
        "status": summary.get("status", "completed"),
        "created_at": run.created_at.isoformat(),
        "field_accuracy": summary.get("field_accuracy"),
        "document_accuracy": (summary.get("documents") or {}).get("field_accuracy"),
        "mismatch_recall": (summary.get("mismatch") or {}).get("recall"),
        "photo_accuracy": (summary.get("photos") or {}).get("rule_accuracy"),
    }


@router.get("/accuracy")
def accuracy(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    runs = db.scalars(
        select(AccuracyRun)
        .order_by(AccuracyRun.created_at.desc(), AccuracyRun.id.desc())
        .limit(8)
    ).all()
    return {
        "latest": latest_run_summary(runs[0] if runs else None),
        "history": [_run_headline(run) for run in runs],
        "running": bool(runs and (runs[0].summary or {}).get("status") == "running"),
    }


@router.post("/accuracy/run", status_code=202)
def start_accuracy_run(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    latest = db.scalar(select(AccuracyRun).order_by(AccuracyRun.id.desc()))
    if latest is not None and (latest.summary or {}).get("status") == "running":
        raise HTTPException(status_code=409, detail="An accuracy run is already in progress.")

    run = AccuracyRun(
        dataset=rules()["evaluation"]["dataset"],
        total_cases=0,
        summary={
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        report_md="",
        created_by=admin.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(run_evaluation, run.id, admin.id)
    return {"id": run.id, "status": "running"}
