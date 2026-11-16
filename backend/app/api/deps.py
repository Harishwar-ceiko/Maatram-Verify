from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.application import Application
from app.models.enums import Role
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _unauthorized(detail: str = "Sign in to continue.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise _unauthorized()
    try:
        payload = decode_token(token)
    except ValueError:
        raise _unauthorized("Your session expired. Sign in again.")
    subject = payload.get("sub")
    if not subject:
        raise _unauthorized()
    user = db.get(User, int(subject))
    if user is None or not user.is_active:
        raise _unauthorized("This account is not active.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user


def get_application_for_user(
    application_id: int, db: Session, user: User
) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if user.role != Role.admin.value and application.student_id != user.id:
        raise HTTPException(status_code=403, detail="This application belongs to another student.")
    return application


def owned_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Application:
    return get_application_for_user(application_id, db, user)


def admin_owned_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> Application:
    return get_application_for_user(application_id, db, user)


def list_students(db: Session) -> list[User]:
    return list(db.scalars(select(User).where(User.role == Role.student.value)).all())
