from __future__ import annotations

from PIL import Image

from app.ocr.types import OcrPage, OcrUnavailable, Word


class PaddleEngine:
    """Optional second opinion. PaddleOCR is not installed by default; the
    interface and adapters exist so it can be enabled without touching the
    validation pipeline.

    The conversion below maps a detected line box onto word boxes, which keeps
    the shared table grouping in `app.ocr.fields` usable for both engines.
    """

    name = "paddle"

    def __init__(self, language: str = "en") -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise OcrUnavailable(
                "PaddleOCR is not installed. Install `paddleocr` and `paddlepaddle`, "
                "or set OCR_ENGINE=tesseract."
            ) from exc
        self._reader = PaddleOCR(use_angle_cls=True, lang=language, show_log=False)

    def extract(self, images: list[Image.Image]) -> list[OcrPage]:
        import numpy as np

        pages: list[OcrPage] = []
        for number, image in enumerate(images, start=1):
            result = self._reader.ocr(np.array(image.convert("RGB")), cls=True)
            lines = (result or [[]])[0] or []
            words: list[Word] = []
            for line_index, line in enumerate(lines):
                box, (text, confidence) = line[0], line[1]
                left = min(point[0] for point in box)
                top = min(point[1] for point in box)
                right = max(point[0] for point in box)
                bottom = max(point[1] for point in box)
                pieces = str(text).split()
                if not pieces:
                    continue
                width = max(1.0, (right - left) / len(pieces))
                for column, piece in enumerate(pieces):
                    words.append(
                        Word(
                            text=piece,
                            confidence=round(float(confidence) * 100, 2),
                            left=int(left + column * width),
                            top=int(top),
                            width=int(width),
                            height=max(1, int(bottom - top)),
                            block=0,
                            paragraph=0,
                            line=line_index,
                        )
                    )
            pages.append(
                OcrPage(
                    number=number,
                    width=image.width,
                    height=image.height,
                    words=words,
                    text="\n".join(" ".join(word.text for word in words if word.line == line) for line in sorted({word.line for word in words})),
                )
            )
        return pages
