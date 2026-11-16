from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings, rules
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.audit import write_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()
login_limiter = SlidingWindowLimiter(
    settings.login_rate_limit, settings.login_rate_window_seconds
)


def _token_payload(user: User) -> TokenResponse:
    token = create_access_token(str(user.id), {"role": user.role, "email": user.email})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower().strip()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=Role.student.value,
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        action="auth.register",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        actor_email=user.email,
        detail={"role": user.role},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return _token_payload(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower().strip()
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = login_limiter.allow(f"{client_ip}:{email}")
    if not allowed:
        write_audit(
            db,
            action="auth.rate_limited",
            entity_type="user",
            actor_email=email,
            detail={"retry_after": retry_after},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        write_audit(
            db,
            action="auth.login_failed",
            entity_type="user",
            actor_email=email,
            detail={"reason": "invalid_credentials"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is not active.")

    user.last_login_at = datetime.now(timezone.utc)
    write_audit(
        db,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        actor_email=user.email,
        detail={"role": user.role},
        request=request,
    )
    db.commit()
    db.refresh(user)
    login_limiter.reset(f"{client_ip}:{email}")
    return _token_payload(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/session")
def session_info(user: User = Depends(get_current_user)) -> dict:
    config = rules()
    return {
        "user": UserOut.model_validate(user).model_dump(mode="json"),
        "permissions": {
            "can_review": user.role == Role.admin.value,
            "can_upload": True,
        },
        "app": {
            "name": config["app"]["name"],
            "problem": config["app"]["problem"],
        },
    }
