from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.ocr.types import OcrUnavailable


@dataclass(frozen=True, slots=True)
class TesseractInfo:
    command: str
    version: str
    traineddata: bool


def _candidate_commands() -> list[Path]:
    """Path candidates, most explicit first. The per-user install is last so a
    system-wide install still wins when one exists."""

    settings = get_settings()
    candidates: list[Path] = []

    if settings.tesseract_cmd:
        candidates.append(Path(settings.tesseract_cmd))
    if os.environ.get("TESSERACT_CMD"):
        candidates.append(Path(os.environ["TESSERACT_CMD"]))

    on_path = shutil.which("tesseract")
    if on_path:
        candidates.append(Path(on_path))

    executable = "tesseract.exe" if os.name == "nt" else "tesseract"
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Programs" / "Tesseract-OCR" / executable)

    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(key)
        if base:
            candidates.append(Path(base) / "Tesseract-OCR" / executable)

    return candidates


def _resolve() -> TesseractInfo:
    import pytesseract

    errors: list[str] = []
    for candidate in _candidate_commands():
        if not candidate or not candidate.is_file():
            continue
        pytesseract.pytesseract.tesseract_cmd = str(candidate)
        try:
            version = pytesseract.get_tesseract_version()
        except Exception as exc:  # noqa: BLE001 - a broken install should fall through
            errors.append(f"{candidate}: {exc}")
            continue
        traineddata = (candidate.parent / "tessdata" / "eng.traineddata").is_file()
        return TesseractInfo(
            command=str(candidate),
            version=str(version.public) if hasattr(version, "public") else str(version),
            traineddata=traineddata,
        )

    detail = "; ".join(errors[:2])
    suffix = f" ({detail})" if detail else ""
    raise OcrUnavailable(
        "Tesseract is not available. Install it or set TESSERACT_CMD to the executable"
        f"{suffix}."
    )


@lru_cache(maxsize=1)
def tesseract_info() -> TesseractInfo:
    return _resolve()


def ensure_available() -> TesseractInfo:
    info = tesseract_info()
    if not info.traineddata:
        raise OcrUnavailable(
            f"Tesseract at {info.command} has no English training data. "
            "Install the eng language pack."
        )
    return info


def tesseract_status() -> dict:
    try:
        info = ensure_available()
    except OcrUnavailable as exc:
        return {"available": False, "error": str(exc)}
    return {
        "available": True,
        "command": info.command,
        "version": info.version,
        "traineddata": info.traineddata,
    }
