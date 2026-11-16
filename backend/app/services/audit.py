from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.review import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    actor_id: int | None = None,
    actor_email: str | None = None,
    entity_id: int | None = None,
    application_id: int | None = None,
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    client_ip = None
    user_agent = None
    if request is not None:
        client_ip = request.client.host if request.client else None
        user_agent = (request.headers.get("user-agent") or "")[:255] or None
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        application_id=application_id,
        actor_id=actor_id,
        actor_email=actor_email,
        detail=detail or {},
        ip=client_ip,
        user_agent=user_agent,
        created_at=utcnow(),
    )
    db.add(entry)
    return entry
