from __future__ import annotations

import time

from app.ocr.engine import get_engine
from app.ocr.fields import extract_fields
from app.ocr.render import render_document
from app.ocr.types import Extraction


def extract_document(data: bytes, mime_type: str) -> Extraction:
    started = time.perf_counter()
    images = render_document(data, mime_type)
    engine = get_engine()
    pages = engine.extract(images)
    extraction = extract_fields(pages)
    extraction.engine = engine.name
    extraction.duration_ms = int((time.perf_counter() - started) * 1000)
    return extraction
