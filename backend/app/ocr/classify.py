"""Deterministic document classification.

The classifier is a keyword score over the OCR text. It never guesses from a
filename, a model score or a language model. Each configured phrase is worth
three points when it appears in the title region and one point otherwise; the
winner must clear ``min_score`` or the upload is rejected and the applicant is
asked to choose the type explicitly.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from PIL import Image

from app.core.config import rules
from app.ocr.engine import get_engine
from app.ocr.render import render_document
from app.ocr.types import OcrPage

_SPACE = re.compile(r"[^a-z0-9+]+")


def normalise(text: str) -> str:
    lowered = (text or "").casefold().replace("&", " and ")
    lowered = _SPACE.sub(" ", lowered)
    return " ".join(lowered.split())


def _present(haystack: str, phrase: str) -> bool:
    needle = normalise(phrase)
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "


def _mark_sheet_kind(kind: str | None) -> bool:
    return bool(kind and kind.startswith("marksheet"))


def classify_text(text: str) -> dict[str, Any] | None:
    config = rules()["documents"]["classifier"]
    haystack = normalise(text)
    if not haystack:
        return None

    scores: dict[str, int] = {}
    signals: dict[str, list[str]] = {}
    for kind, groups in config["keywords"].items():
        total = 0
        matched: list[str] = []
        for phrase in groups.get("title", []):
            if _present(haystack, phrase):
                total += 3
                matched.append(phrase)
        for phrase in groups.get("body", []):
            if _present(haystack, phrase):
                total += 1
                matched.append(phrase)
        if total:
            scores[kind] = total
            signals[kind] = matched

    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_kind, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    minimum = int(config["min_score"])
    if top_score < minimum:
        return None

    margin = int(config["ambiguous_margin"])
    ambiguous = bool(second_score and top_score - second_score < margin)
    chosen = top_kind
    note = None
    if ambiguous and _mark_sheet_kind(top_kind):
        # Class 11 and Class 12 sheets share most of their text. Without a
        # class-specific title, keep the core Class 12 flow and let the
        # applicant override the type if the sheet is for another year.
        mark_sheets = [item for item in ranked if _mark_sheet_kind(item[0])]
        if len(mark_sheets) > 1:
            chosen = "marksheet_12"
            note = (
                "The mark sheet did not state its class clearly; it was treated as "
                "Class 12. Change the document type if that is wrong."
            )

    confidence = round(100 * top_score / (top_score + second_score), 0) if second_score else 100.0
    return {
        "kind": chosen,
        "method": "keyword",
        "score": top_score,
        "scores": {kind: score for kind, score in ranked},
        "signals": signals.get(chosen) or signals.get(top_kind) or [],
        "confidence": confidence,
        "ambiguous": ambiguous,
        "note": note,
    }


def _looks_like_photo(images: Sequence[Image.Image]) -> bool:
    if len(images) != 1:
        return False
    image = images[0]
    if image.height <= 0:
        return False
    ratio = image.width / image.height
    if not 0.45 <= ratio <= 0.95:
        return False
    try:
        from app.validators.photo import detect_faces

        faces = detect_faces(image, rules()["photo"])
    except Exception:  # noqa: BLE001 - a missing cascade is not a failed photo
        return False
    return bool(faces)


def classify_pages(
    pages: Sequence[OcrPage], images: Sequence[Image.Image] | None = None
) -> dict[str, Any] | None:
    text = "\n".join(page.text for page in pages)
    result = classify_text(text)
    if result is not None:
        return result
    if images and _looks_like_photo(images):
        return {
            "kind": "photo",
            "method": "image_heuristic",
            "score": 0,
            "scores": {},
            "signals": ["frontal face", "portrait frame"],
            "confidence": 80.0,
            "ambiguous": False,
            "note": None,
        }
    return None


def classify_document(data: bytes, mime_type: str) -> dict[str, Any] | None:
    """Cheap read used at upload time, before the applicant confirms the type."""

    config = rules()["documents"]["classifier"]
    images = render_document(data, mime_type, dpi=int(config["auto_dpi"]))
    engine = get_engine()
    pages = engine.extract(images)
    return classify_pages(pages, images)
