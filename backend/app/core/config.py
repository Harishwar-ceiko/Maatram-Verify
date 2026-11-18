from __future__ import annotations

import base64
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
ASSETS_DIR = BACKEND_DIR / "assets"
SYNTHETIC_DIR = BACKEND_DIR / "synthetic"
REPORTS_DIR = BACKEND_DIR / "reports"
RULES_PATH = BACKEND_DIR / "app" / "config" / "rules.yaml"


class Settings(BaseSettings):
    """Environment settings. Every value has a safe local default except keys,
    which are generated once into backend/data and never committed."""

    app_env: str = "development"
    secret_key: str | None = None
    access_token_expire_minutes: int = 120
    database_url: str | None = None
    fernet_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FERNET_KEY", "FILE_ENCRYPTION_KEY"),
    )
    max_upload_mb: int = 15
    storage_dir: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_DIR", "UPLOAD_DIR"),
    )
    ocr_engine: str = "tesseract"
    tesseract_cmd: str | None = None
    cors_origins: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "FRONTEND_ORIGIN"),
    )
    seed_on_start: bool = False
    login_rate_limit: int = 8
    login_rate_window_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def database_path(self) -> Path:
        if self.database_url:
            return BACKEND_DIR / "data"
        return DATA_DIR

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(DATA_DIR / 'admissions.db').as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        """Comma-separated CORS_ORIGINS parsed into the exact origins to allow."""

        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    def resolved_storage_dir(self) -> Path:
        path = Path(self.storage_dir) if self.storage_dir else DATA_DIR / "uploads"
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path


def _persisted_secret(filename: str, factory) -> str:
    """Keep a generated dev secret on disk so tokens survive restarts without
    ever putting a real secret in the repository."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    value = factory()
    path.write_text(value, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return value


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.app_env.lower() == "production":
        missing = [
            env_name
            for env_name, value in (
                ("SECRET_KEY", settings.secret_key),
                ("FERNET_KEY", settings.fernet_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required production environment variable(s): "
                + ", ".join(missing)
            )
    elif settings.app_env != "test":
        if not settings.secret_key:
            settings.secret_key = _persisted_secret(
                "dev_secret", lambda: secrets.token_urlsafe(48)
            )
        if not settings.fernet_key:
            from cryptography.fernet import Fernet

            settings.fernet_key = _persisted_secret(
                "dev_fernet.key", lambda: Fernet.generate_key().decode()
            )
    else:
        settings.secret_key = settings.secret_key or "test-secret-key"
        settings.fernet_key = settings.fernet_key or base64.urlsafe_b64encode(
            b"0" * 32
        ).decode()
    return settings


@lru_cache
def get_rules() -> dict[str, Any]:
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def rules() -> dict[str, Any]:
    return get_rules()
