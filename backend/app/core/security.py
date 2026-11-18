from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    # bcrypt consumes at most 72 bytes; reject rather than silently truncate.
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raise ValueError("password must be at most 72 bytes")
    rounds = 12
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.secret_key or "", algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key or "", algorithms=[ALGORITHM])
    except JWTError as exc:  # pragma: no cover - exercised through API tests
        raise ValueError("invalid token") from exc


def _fernet() -> Fernet:
    key = get_settings().file_encryption_key
    if not key:
        raise RuntimeError("FILE_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode("utf-8"))


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    return _fernet().decrypt(data)


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
