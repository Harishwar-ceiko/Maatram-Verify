from __future__ import annotations

import time

from app.ocr.classify import classify_pages
from app.ocr.document_fields import (
    extract_aadhaar,
    extract_community,
    extract_first_graduate,
    extract_income,
)
from app.ocr.engine import get_engine
from app.ocr.fields import extract_fields
from app.ocr.render import render_document
from app.ocr.types import Extraction, OcrUnavailable
from app.validators.aadhaar import decode_qr, redact_text


def _mark_sheet(pages, classification) -> Extraction:
    result = extract_fields(pages)
    result.kind = "marksheet_12"
    result.classification = classification
    return result


def _dispatch(kind: str, pages, images, classification) -> Extraction:
    raw_text = "\n\n".join(page.text for page in pages).strip()
    if kind.startswith("marksheet"):
        return _mark_sheet(pages, classification)
    if kind == "aadhaar":
        payloads: list[str] = []
        try:
            payloads = decode_qr(images)
        except Exception:  # noqa: BLE001 - a camera photo may defeat the decoder
            payloads = []
        result = extract_aadhaar(pages, raw_text, payloads)
        result.classification = classification
        return result
    if kind == "income_certificate":
        result = extract_income(pages, raw_text)
        result.classification = classification
        return result
    if kind == "community_certificate":
        result = extract_community(pages, raw_text)
        result.classification = classification
        return result
    if kind == "first_graduate_certificate":
        result = extract_first_graduate(pages, raw_text)
        result.classification = classification
        return result
    result = Extraction(
        pages=list(pages),
        raw_text=raw_text,
        kind=kind,
        classification=classification,
        warnings=["This document type has no field extractor."],
    )
    return result


def extract_document(
    data: bytes,
    mime_type: str,
    kind: str | None = None,
) -> Extraction:
    started = time.perf_counter()
    images = render_document(data, mime_type)

    # A photo is validated by the image rules, not OCR. Callers normally skip
    # the extractor for photos; this keeps direct calls harmless.
    if kind == "photo":
        return Extraction(
            raw_text="",
            engine="tesseract",
            duration_ms=int((time.perf_counter() - started) * 1000),
            kind="photo",
        )

    engine = get_engine()
    pages = engine.extract(images)
    classification = None
    resolved = kind
    if not resolved or resolved == "auto":
        classification = classify_pages(pages, images)
        resolved = (classification or {}).get("kind") or "other"
    elif resolved == "marksheet":
        resolved = "marksheet_12"

    extraction = _dispatch(str(resolved), pages, images, classification)
    extraction.kind = str(resolved)
    extraction.engine = engine.name
    extraction.duration_ms = int((time.perf_counter() - started) * 1000)
    # The raw text is kept for audit/debugging but can never carry a full
    # Aadhaar number.
    extraction.raw_text = redact_text(extraction.raw_text)
    extraction.warnings = [redact_text(warning) for warning in extraction.warnings]
    if resolved == "other":
        extraction.warnings.append(
            "The document type could not be determined; choose it explicitly."
        )
    return extraction


__all__ = ["extract_document", "OcrUnavailable"]
