from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_application_for_user, get_current_user
from app.core.config import get_settings, rules
from app.db.session import get_db
from app.models.application import Application
from app.models.document import Document
from app.models.enums import DocumentKind, Role
from app.models.user import User
from app.schemas.application import DocumentOut, UploadResult
from app.services import storage
from app.services.audit import write_audit

router = APIRouter(prefix="/api", tags=["documents"])


def _document_or_404(db: Session, document_id: int, user: User) -> tuple[Document, Application]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    application = db.get(Application, document.application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if user.role != Role.admin.value and application.student_id != user.id:
        raise HTTPException(status_code=403, detail="This document belongs to another applicant.")
    return document, application


@router.post(
    "/applications/{application_id}/documents",
    response_model=UploadResult,
    status_code=201,
)
async def upload_document(
    application_id: int,
    request: Request,
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadResult:
    application = get_application_for_user(application_id, db, user)
    if kind not in (DocumentKind.marksheet.value, DocumentKind.photo.value):
        raise HTTPException(status_code=422, detail="kind must be marksheet or photo.")

    config = rules()
    cap = min(get_settings().max_upload_mb, config["uploads"]["max_mb"]) * 1024 * 1024
    data = await file.read(cap + 1)
    if len(data) > cap:
        raise HTTPException(status_code=413, detail=f"File is larger than {cap // (1024 * 1024)} MB.")
    try:
        fmt, pages, size = storage.validate_upload(data, kind)
    except storage.UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    digest = storage.checksum(data)
    phash, width, height = storage.phash_bytes(data, fmt)

    replaced: list[Document] = []
    if kind == DocumentKind.photo.value:
        replaced = list(
            db.scalars(
                select(Document).where(
                    Document.application_id == application.id,
                    Document.kind == DocumentKind.photo.value,
                )
            )
        )

    excluded_ids = {document.id for document in replaced}
    student_documents = list(
        db.scalars(
            select(Document)
            .join(Application, Application.id == Document.application_id)
            .where(Application.student_id == application.student_id)
        )
    )

    exact = next(
        (
            item
            for item in student_documents
            if item.sha256 == digest and item.id not in excluded_ids
        ),
        None,
    )
    near = None
    if exact is None and phash:
        limit = config["validation"]["duplicate_phash_distance"]
        near = next(
            (
                item
                for item in student_documents
                if item.phash
                and item.id not in excluded_ids
                and storage.hamming_hex(item.phash, phash) <= limit
            ),
            None,
        )

    stored_name, _path = storage.store_bytes(application.id, data)
    document = Document(
        application_id=application.id,
        kind=kind,
        original_filename=storage.sanitize_filename(file.filename or f"{kind}.{fmt}"),
        stored_name=stored_name,
        mime_type=storage.MIME[fmt],
        size_bytes=size,
        sha256=digest,
        phash=phash,
        page_count=pages,
        width=width,
        height=height,
        encrypted=True,
        duplicate_of_id=(exact or near).id if (exact or near) else None,
        uploaded_by_id=user.id,
    )
    db.add(document)
    db.flush()

    warnings: list[str] = []
    if exact is not None:
        warnings.append(
            f"This is byte-for-byte the same file as {exact.original_filename}. "
            "The duplicate is recorded and will be flagged."
        )
    elif near is not None:
        warnings.append(
            f"This looks nearly identical to {near.original_filename}. "
            "The near duplicate is recorded and will be flagged."
        )

    for old in replaced:
        storage.delete_document_file(old)
        db.delete(old)
        write_audit(
            db,
            action="document.replaced",
            entity_type="document",
            entity_id=old.id,
            application_id=application.id,
            actor_id=user.id,
            actor_email=user.email,
            detail={"filename": old.original_filename, "kind": kind},
            request=request,
        )

    write_audit(
        db,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        application_id=application.id,
        actor_id=user.id,
        actor_email=user.email,
        detail={
            "filename": document.original_filename,
            "kind": kind,
            "bytes": size,
            "sha256": digest[:12],
            "duplicate_of": document.duplicate_of_id,
        },
        request=request,
    )
    db.commit()
    db.refresh(document)
    return UploadResult(document=DocumentOut.model_validate(document), warnings=warnings)


@router.get("/documents/{document_id}/file")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    document, _application = _document_or_404(db, document_id, user)
    try:
        data = storage.read_document_bytes(document)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="The stored file is missing.") from exc
    filename = quote(document.original_filename)
    return Response(
        content=data,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document, application = _document_or_404(db, document_id, user)
    filename = document.original_filename
    kind = document.kind
    try:
        storage.delete_document_file(document)
    except OSError:
        pass
    db.delete(document)
    write_audit(
        db,
        action="document.deleted",
        entity_type="document",
        entity_id=document_id,
        application_id=application.id,
        actor_id=user.id,
        actor_email=user.email,
        detail={"filename": filename, "kind": kind},
        request=request,
    )
    db.commit()
    return None


@router.get("/documents/{document_id}/meta")
def document_meta(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    document, _application = _document_or_404(db, document_id, user)
    path: Path = storage.document_path(document)
    return {
        "id": document.id,
        "filename": document.original_filename,
        "kind": document.kind,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "page_count": document.page_count,
        "width": document.width,
        "height": document.height,
        "encrypted": document.encrypted,
        "stored": path.exists(),
        "duplicate_of_id": document.duplicate_of_id,
    }
