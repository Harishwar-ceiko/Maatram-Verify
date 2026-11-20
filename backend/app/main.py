
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import __version__
from app.api.routes import admin, applications, auth, documents, meta
from app.core.config import get_settings, rules
from app.core.security import hash_password
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.enums import Role
from app.models.user import User

logger = logging.getLogger("maatram")


def bootstrap_reviewer() -> None:
    email = os.getenv("REVIEWER_EMAIL", "").strip().lower()
    password = os.getenv("REVIEWER_PASSWORD", "")
    name = os.getenv("REVIEWER_NAME", "Maatram Reviewer").strip()

    if not email and not password:
        return

    if not email or not password:
        raise RuntimeError("Set both REVIEWER_EMAIL and REVIEWER_PASSWORD.")

    if len(password.encode("utf-8")) > 72:
        raise RuntimeError("Reviewer password is too long.")

    with SessionLocal() as db:
        reviewer = db.scalar(select(User).where(User.email == email))

        if reviewer is None:
            reviewer = User(
                email=email,
                full_name=name or "Maatram Reviewer",
                password_hash=hash_password(password),
                role=Role.admin.value,
                is_active=True,
            )
            db.add(reviewer)
        else:
            reviewer.full_name = name or "Maatram Reviewer"
            reviewer.password_hash = hash_password(password)
            reviewer.role = Role.admin.value
            reviewer.is_active = True

        db.commit()

    logger.info("Reviewer account configured.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.resolved_storage_dir().mkdir(parents=True, exist_ok=True)
    init_db()
    bootstrap_reviewer()

    if settings.seed_on_start and settings.app_env != "test":
        from scripts.seed import seed_if_empty

        if seed_if_empty():
            logger.info("Seeded the demo data into an empty database")

    logger.info("Maatram Verify %s ready", __version__)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    config = rules()

    app = FastAPI(
        title=config["app"]["name"],
        description="Deterministic admission document validation. No generative AI.",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(applications.router)
    app.include_router(documents.router)
    app.include_router(meta.router)
    app.include_router(admin.router)

    return app


app = create_app()


@app.get("/health", tags=["meta"])
@app.get("/api/health", tags=["meta"])
def health() -> dict:
    from app.ocr.engine import engine_name
    from app.ocr.runtime import tesseract_status

    return {
        "service": "ok",
        "version": __version__,
        "engine": "deterministic",
        "generative_ai": False,
        "ocr": {
            "engine": engine_name(),
            "tesseract": tesseract_status(),
        },
    }
