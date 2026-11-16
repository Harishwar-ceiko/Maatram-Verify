from __future__ import annotations

import hashlib
import io
import re
import uuid
from pathlib import Path

import fitz
from PIL import Image, ImageOps

from app.core.config import get_settings, rules
from app.core.security import decrypt_bytes, encrypt_bytes
from app.models.document import Document

MAGIC = {
    "pdf": b"%PDF-",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
}

MIME = {
    "pdf": "application/pdf",
    "jpeg": "image/jpeg",
    "png": "image/png",
}

EXTENSIONS = {"pdf": ".pdf", "jpeg": ".jpg", "png": ".png"}


class UploadError(ValueError):
    pass


def detect_format(data: bytes) -> str | None:
    for name, signature in MAGIC.items():
        if data.startswith(signature):
            return name
    return None


def sanitize_filename(name: str) -> str:
    name = Path(name or "document").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    if not name:
        name = "document"
    stem, suffix = Path(name).stem[:100], Path(name).suffix[:10]
    return f"{stem}{suffix}"


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dhash(image: Image.Image, size: int = 8) -> str:
    gray = ImageOps.exif_transpose(image).convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = gray.tobytes()
    bits = 0
    for row in range(size):
        for column in range(size):
            left = pixels[row * (size + 1) + column]
            right = pixels[row * (size + 1) + column + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:0{size * size // 4}x}"


def phash_bytes(data: bytes, fmt: str) -> tuple[str | None, int | None, int | None]:
    """Perceptual hash plus pixel dimensions. A PDF is hashed from page one."""

    if fmt == "pdf":
        try:
            pdf = fitz.open(stream=data, filetype="pdf")
            page = pdf.load_page(0)
            pixmap = page.get_pixmap(dpi=72)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            digest = dhash(image)
            pdf.close()
            return digest, None, None
        except Exception:  # noqa: BLE001 - a hash is an optimization, never a blocker
            return None, None, None

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        width, height = image.size
        return dhash(image), width, height
    except Exception:  # noqa: BLE001
        return None, None, None


def pdf_page_count(data: bytes) -> int:
    try:
        pdf = fitz.open(stream=data, filetype="pdf")
        count = pdf.page_count
        pdf.close()
        return count
    except Exception:  # noqa: BLE001
        return 1


def hamming_hex(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 999


def storage_root() -> Path:
    root = get_settings().resolved_upload_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_bytes(application_id: int, data: bytes) -> tuple[str, Path]:
    name = f"{uuid.uuid4().hex}.bin"
    folder = storage_root() / str(application_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(encrypt_bytes(data))
    return name, path


def read_document_bytes(document: Document) -> bytes:
    path = document_path(document)
    if not path.exists():
        raise FileNotFoundError(path)
    return decrypt_bytes(path.read_bytes())


def document_path(document: Document) -> Path:
    return storage_root() / str(document.application_id) / document.stored_name


def delete_document_file(document: Document) -> None:
    path = document_path(document)
    if path.exists():
        path.unlink()


def validate_upload(data: bytes, kind: str) -> tuple[str, int, int]:
    settings = get_settings()
    config = rules()
    max_bytes = min(settings.max_upload_mb, config["uploads"]["max_mb"]) * 1024 * 1024
    if not data:
        raise UploadError("The file is empty.")
    if len(data) > max_bytes:
        raise UploadError(f"File is larger than {max_bytes // (1024 * 1024)} MB.")
    if len(data) < config["uploads"]["min_bytes"]:
        raise UploadError("This file is too small to be a document.")

    fmt = detect_format(data)
    if fmt is None:
        raise UploadError("The content is not a PDF, JPEG or PNG, whatever the extension says.")
    if kind == "photo" and fmt == "pdf":
        raise UploadError("A profile photo must be a JPEG or PNG, not a PDF.")

    pages = pdf_page_count(data) if fmt == "pdf" else 1
    if pages > config["uploads"]["max_pages"]:
        raise UploadError(f"The PDF has {pages} pages; the limit is {config['uploads']['max_pages']}.")
    return fmt, pages, len(data)
