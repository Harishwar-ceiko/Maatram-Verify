from __future__ import annotations

from dataclasses import dataclass

import pytesseract
from PIL import Image

from app.core.config import rules
from app.ocr.preprocess import PreparedPage, prepare_page
from app.ocr.runtime import ensure_available
from app.ocr.types import OcrPage, OcrUnavailable, Word


@dataclass(slots=True)
class _Attempt:
    page: OcrPage
    score: float


def _parse_data(data: dict, number: int, psm: int) -> OcrPage:
    words: list[Word] = []
    text = data.get("text", [])
    for index, raw in enumerate(text):
        token = str(raw or "").strip()
        if not token:
            continue
        try:
            confidence = float(data["conf"][index])
        except (KeyError, TypeError, ValueError):
            continue
        if confidence < 0:
            continue
        try:
            words.append(
                Word(
                    text=token,
                    confidence=round(confidence, 2),
                    left=int(data["left"][index]),
                    top=int(data["top"][index]),
                    width=int(data["width"][index]),
                    height=int(data["height"][index]),
                    block=int(data["block_num"][index]),
                    paragraph=int(data["par_num"][index]),
                    line=int(data["line_num"][index]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    lines: dict[tuple[int, int, int], list[Word]] = {}
    for word in words:
        lines.setdefault((word.block, word.paragraph, word.line), []).append(word)
    ordered = sorted(lines.items(), key=lambda item: min(word.top for word in item[1]))
    text_lines = [" ".join(word.text for word in line_words) for _, line_words in ordered]

    width = max((word.right for word in words), default=0)
    height = max((word.bottom for word in words), default=0)

    return OcrPage(
        number=number,
        width=width,
        height=height,
        words=words,
        text="\n".join(text_lines),
        psm=psm,
    )


KEYWORDS = {
    "subject",
    "subjects",
    "obtained",
    "maximum",
    "max",
    "marks",
    "mark",
    "grade",
    "total",
    "register",
    "candidate",
    "name",
    "result",
    "examination",
}


def _score(page: OcrPage, minimum: float) -> float:
    usable = [word for word in page.words if word.confidence >= minimum]
    if not usable:
        return -1.0
    mean = sum(word.confidence for word in usable) / len(usable)
    tokens = {word.text.strip(".,:;()[]").lower() for word in usable}
    keywords = len(tokens & KEYWORDS)
    numeric = sum(1 for word in usable if any(character.isdigit() for character in word.text))
    coverage = min(len(usable), 160) * 0.04
    return mean + keywords * 2.5 + min(numeric, 40) * 0.3 + coverage


class TesseractEngine:
    name = "tesseract"

    def __init__(self, language: str | None = None) -> None:
        config = rules()["ocr"]
        self.language = language or str(config["language"])
        self.modes = [int(mode) for mode in config["page_segmentation_modes"]]
        self.minimum_confidence = float(config["min_word_confidence"])
        ensure_available()

    def _read(self, page: PreparedPage, image: Image.Image, number: int, psm: int) -> OcrPage:
        payload = pytesseract.image_to_data(
            image,
            lang=self.language,
            config=f"--oem 3 --psm {psm} -c preserve_interword_spaces=1",
            output_type=pytesseract.Output.DICT,
        )
        parsed = _parse_data(payload, number=number, psm=psm)
        # Words carry the right coordinates, but the page bounds must come from
        # the raster, not from the rightmost word on the page.
        parsed.width, parsed.height = page.width, page.height
        return parsed

    def extract(self, images: list[Image.Image]) -> list[OcrPage]:
        pages: list[OcrPage] = []
        for number, image in enumerate(images, start=1):
            prepared = prepare_page(image)
            attempts: list[_Attempt] = []

            for mode in self.modes:
                try:
                    page = self._read(prepared, prepared.gray, number, mode)
                except pytesseract.TesseractError as exc:  # pragma: no cover - install/runtime fault
                    raise OcrUnavailable(f"Tesseract could not read page {number}: {exc}") from exc
                score = _score(page, self.minimum_confidence)
                attempts.append(_Attempt(page=page, score=score))
                # A confident read with the keywords a mark sheet needs is
                # enough; trying every mode would only cost time.
                if score >= 88 and len(
                    {word.text.strip(".,:;").lower() for word in page.words} & KEYWORDS
                ) >= 3:
                    break

            best = max(attempts, key=lambda attempt: attempt.score)
            if best.score < 72:
                candidate = self._read(prepared, prepared.binary, number, self.modes[0])
                candidate_score = _score(candidate, self.minimum_confidence)
                if candidate_score > best.score:
                    best = _Attempt(page=candidate, score=candidate_score)

            page = best.page
            page.number = number
            if not page.width:
                page.width, page.height = prepared.width, prepared.height
            pages.append(page)
        return pages
