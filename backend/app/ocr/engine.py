from __future__ import annotations

from app.core.config import get_settings, rules
from app.ocr.types import OcrEngine, OcrUnavailable


def engine_name() -> str:
    settings = get_settings()
    return (settings.ocr_engine or rules()["ocr"]["engine"]).strip().lower()


def get_engine(name: str | None = None) -> OcrEngine:
    chosen = (name or engine_name()).strip().lower()
    if chosen == "paddle":
        from app.ocr.paddle_engine import PaddleEngine

        return PaddleEngine()
    if chosen != "tesseract":
        raise OcrUnavailable(
            f"OCR engine {chosen!r} is not supported. Choose tesseract or paddle."
        )
    from app.ocr.tesseract_engine import TesseractEngine

    return TesseractEngine()
