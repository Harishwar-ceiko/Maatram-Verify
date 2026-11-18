from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from PIL import Image


@dataclass(slots=True)
class Word:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    block: int = 0
    paragraph: int = 0
    line: int = 0

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2

    @property
    def numeric(self) -> bool:
        cleaned = self.text.replace(",", "").replace(".", "").strip()
        return cleaned.isdigit()


@dataclass(slots=True)
class OcrPage:
    number: int
    width: int
    height: int
    words: list[Word]
    text: str
    psm: int = 0


@dataclass(slots=True)
class Field:
    value: Any = None
    confidence: float = 0.0
    page: int | None = None


@dataclass(slots=True)
class SubjectRow:
    subject_raw: str
    marks_obtained: float | None
    max_marks: float | None
    grade: str | None
    confidence: float
    page: int
    bbox: dict[str, int] | None = None


@dataclass(slots=True)
class Extraction:
    pages: list[OcrPage] = field(default_factory=list)
    name: Field = field(default_factory=Field)
    register_number: Field = field(default_factory=Field)
    exam_year: Field = field(default_factory=Field)
    subjects: list[SubjectRow] = field(default_factory=list)
    raw_text: str = ""
    engine: str = ""
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)
    kind: str | None = None
    classification: dict[str, Any] | None = None
    # Non-mark-sheet values in display-safe form (Aadhaar is already masked).
    attributes: dict[str, Any] = field(default_factory=dict)
    # Values that must never be persisted or logged. The Aadhaar extractor puts
    # the full number and checksum state here for the write path only.
    sensitive: dict[str, Any] = field(default_factory=dict)
    qr_payloads: list[str] = field(default_factory=list)


class OcrEngine(Protocol):
    """Every engine returns positioned words so table grouping is shared.

    Tesseract gives word boxes directly. An engine without word boxes (Paddle)
    can distribute a line's words across its polygon.
    """

    name: str

    def extract(self, images: Sequence[Image.Image]) -> list[OcrPage]: ...


class OcrUnavailable(RuntimeError):
    """The configured engine or its training data is not installed."""
