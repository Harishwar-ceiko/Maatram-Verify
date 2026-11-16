from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_application_for_user, get_current_user
from app.db.session import get_db, get_session_factory
from app.models.application import Application, EnteredMark
from app.models.enums import ApplicationStatus, DocumentKind, Role, RunStatus
from app.models.user import User
from app.models.validation import ValidationRun
from app.reports.pdf import build_validation_report
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationList,
    ApplicationOut,
    DocumentOut,
    ExtractOut,
    MarkOut,
    ReviewOut,
    RunOut,
)
from app.services.audit import write_audit
from app.services.references import new_reference
from app.services.validation import run_validation

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _to_detail(application: Application, include_review: bool = False) -> ApplicationDetail:
    review = None
    if include_review and application.review_item is not None:
        item = application.review_item
        review = ReviewOut(
            id=item.id,
            status=item.status,
            priority=item.priority,
            reasons=item.reasons or [],
            run_id=item.run_id,
            assigned_to_email=item.assigned_user.email if item.assigned_user else None,
            decision_comment=item.decision_comment,
            decided_by_email=item.decided_by_user.email if item.decided_by_user else None,
            decided_at=item.decided_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
    return ApplicationDetail(
        id=application.id,
        reference=application.reference,
        program=application.program,
        applicant_name=application.applicant_name,
        register_number=application.register_number,
        exam_year=application.exam_year,
        board=application.board,
        status=application.status,
        created_at=application.created_at,
        submitted_at=application.submitted_at,
        marks=[MarkOut.model_validate(mark) for mark in application.entered_marks],
        documents=[DocumentOut.model_validate(doc) for doc in application.documents],
        latest_run=RunOut.model_validate(application.latest_run) if application.latest_run else None,
        extracted_marks=[
            ExtractOut.model_validate(mark)
            for document in application.documents
            for mark in document.extracted_marks
        ],
        review=review,
    )


@router.get("", response_model=ApplicationList)
def list_applications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApplicationList:
    statement = select(Application).options(
        selectinload(Application.entered_marks),
        selectinload(Application.documents),
        selectinload(Application.runs),
    )
    if user.role != Role.admin.value:
        statement = statement.where(Application.student_id == user.id)
    if status_filter:
        statement = statement.where(Application.status == status_filter)
    if q:
        like = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Application.reference.ilike(like),
                Application.applicant_name.ilike(like),
                Application.register_number.ilike(like),
                Application.program.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.scalars(
        statement.order_by(Application.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).unique().all()
    return ApplicationList(items=[ApplicationOut.model_validate(row) for row in rows], total=total)


@router.post("", response_model=ApplicationDetail, status_code=201)
def create_application(
    payload: ApplicationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    reference = new_reference()
    for _ in range(5):
        if not db.scalar(select(Application.id).where(Application.reference == reference)):
            break
        reference = new_reference()
    else:  # pragma: no cover - astronomically unlikely
        raise HTTPException(status_code=500, detail="Could not allocate an application number.")

    application = Application(
        reference=reference,
        student_id=user.id,
        program=payload.program,
        applicant_name=payload.applicant_name,
        register_number=payload.register_number,
        exam_year=payload.exam_year,
        board=payload.board.strip(),
        status=ApplicationStatus.submitted.value,
        submitted_at=datetime.now(timezone.utc),
    )
    application.entered_marks = [
        EnteredMark(
            subject=mark.subject,
            marks_obtained=mark.marks_obtained,
            max_marks=mark.max_marks,
            grade=mark.grade,
        )
        for mark in payload.marks
    ]
    db.add(application)
    db.flush()
    write_audit(
        db,
        action="application.created",
        entity_type="application",
        entity_id=application.id,
        application_id=application.id,
        actor_id=user.id,
        actor_email=user.email,
        detail={"reference": application.reference, "subjects": len(payload.marks)},
        request=request,
    )
    db.commit()
    db.refresh(application)
    return _to_detail(application)


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    application = get_application_for_user(application_id, db, user)
    return _to_detail(application, include_review=user.role == Role.admin.value)


@router.get("/{application_id}/report.pdf")
def download_report(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    application = get_application_for_user(application_id, db, user)
    run = application.latest_run
    if run is None or run.status != RunStatus.completed.value:
        raise HTTPException(
            status_code=409,
            detail="Run the checks before downloading a report.",
        )
    try:
        data = build_validation_report(application, run)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    write_audit(
        db,
        action="report.downloaded",
        entity_type="application",
        entity_id=application.id,
        application_id=application.id,
        actor_id=user.id,
        actor_email=user.email,
        detail={"run_id": run.id, "overall": run.overall, "bytes": len(data)},
        request=request,
    )
    db.commit()
    filename = f"{application.reference}-validation.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{application_id}/validate", response_model=RunOut, status_code=202)
def validate_application(
    application_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    session_factory=Depends(get_session_factory),
) -> RunOut:
    application = get_application_for_user(application_id, db, user)

    if application.status in (
        ApplicationStatus.approved.value,
        ApplicationStatus.rejected.value,
    ):
        raise HTTPException(
            status_code=409,
            detail="This application has already been decided and cannot be re-checked.",
        )

    kinds = {document.kind for document in application.documents}
    if DocumentKind.marksheet.value not in kinds:
        raise HTTPException(
            status_code=422,
            detail="Attach a mark sheet before running the checks.",
        )
    if DocumentKind.photo.value not in kinds:
        raise HTTPException(
            status_code=422,
            detail="Attach a profile photograph before running the checks.",
        )

    active = db.scalar(
        select(ValidationRun.id).where(
            ValidationRun.application_id == application.id,
            ValidationRun.status.in_([RunStatus.pending.value, RunStatus.running.value]),
        )
    )
    if active:
        raise HTTPException(status_code=409, detail="Checks are already running on this application.")

    run = ValidationRun(application_id=application.id, status=RunStatus.pending.value)
    application.status = ApplicationStatus.processing.value
    db.add(run)
    db.flush()
    write_audit(
        db,
        action="validation.started",
        entity_type="validation_run",
        entity_id=run.id,
        application_id=application.id,
        actor_id=user.id,
        actor_email=user.email,
        detail={"documents": len(application.documents)},
        request=request,
    )
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_validation, run.id, session_factory)
    return RunOut.model_validate(run)


@router.delete("/{application_id}", status_code=204)
def delete_application(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    application = get_application_for_user(application_id, db, user)
    if application.status not in (ApplicationStatus.draft.value, ApplicationStatus.submitted.value):
        raise HTTPException(status_code=409, detail="A reviewed application cannot be deleted.")
    reference = application.reference
    db.delete(application)
    write_audit(
        db,
        action="application.deleted",
        entity_type="application",
        entity_id=application_id,
        application_id=application_id,
        actor_id=user.id,
        actor_email=user.email,
        detail={"reference": reference},
        request=request,
    )
    db.commit()
    return None
