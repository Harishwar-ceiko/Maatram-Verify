from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image, ImageOps

from app.core.config import rules
from app.ocr.types import OcrUnavailable


def _render_pdf(data: bytes, dpi: int) -> list[Image.Image]:
    images: list[Image.Image] = []
    pdf = fitz.open(stream=data, filetype="pdf")
    try:
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        for page in pdf:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            images.append(image)
    finally:
        pdf.close()
    return images


def _open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise OcrUnavailable("The uploaded image could not be decoded.") from exc
    return ImageOps.exif_transpose(image).convert("RGB")


def render_document(data: bytes, mime_type: str, *, dpi: int | None = None) -> list[Image.Image]:
    """Turn an uploaded mark sheet into OCR-ready raster pages.

    A PDF is rasterised at the configured DPI (300 by default). A plain image is
    used as-is apart from EXIF orientation, so nothing is invented.
    """

    target_dpi = dpi or int(rules()["ocr"]["render_dpi"])
    if mime_type == "application/pdf" or data.startswith(b"%PDF-"):
        images = _render_pdf(data, target_dpi)
    else:
        images = [_open_image(data)]
    if not images:
        raise OcrUnavailable("The document has no pages to read.")
    return images


def image_size(path: str | Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size
