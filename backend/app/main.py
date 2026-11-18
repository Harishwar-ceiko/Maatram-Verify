from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import admin, applications, auth, documents, meta
from app.core.config import get_settings, rules
from app.db.init_db import init_db

logger = logging.getLogger("maatram")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.resolved_storage_dir().mkdir(parents=True, exist_ok=True)
    init_db()
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
        "ocr": {"engine": engine_name(), "tesseract": tesseract_status()},
    }
