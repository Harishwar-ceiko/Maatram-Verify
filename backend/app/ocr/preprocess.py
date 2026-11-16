from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from app.core.config import rules


@dataclass(slots=True)
class PreparedPage:
    """A page cleaned for OCR. Coordinates in words refer to this image."""

    gray: Image.Image
    binary: Image.Image
    width: int
    height: int
    scale: float
    skew_degrees: float
    dpi: int | None


def _to_array(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("L"))


def _to_image(array: np.ndarray) -> Image.Image:
    return Image.fromarray(array)


def _effective_dpi(image: Image.Image) -> int | None:
    dpi = image.info.get("dpi")
    if isinstance(dpi, tuple) and dpi and dpi[0]:
        try:
            return int(round(float(dpi[0])))
        except (TypeError, ValueError):
            return None
    return None


def _estimate_skew(gray: np.ndarray, max_degrees: float) -> float:
    """Text rows are long and horizontal, so a min-area rectangle around the
    ink gives the page angle without a Hough transform's vote noise."""

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, ink = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    points = cv2.findNonZero(ink)
    if points is None or len(points) < 200:
        return 0.0

    (_, _), (width, height), angle = cv2.minAreaRect(points)
    if width < 1 or height < 1:
        return 0.0
    if width < height:
        angle += 90
    if angle > 45:
        angle -= 90
    if abs(angle) > max_degrees:
        return 0.0
    return round(float(angle), 2)


def _deskew(gray: np.ndarray, degrees: float) -> np.ndarray:
    if abs(degrees) < 0.15:
        return gray
    height, width = gray.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    return cv2.warpAffine(
        gray,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def prepare_page(image: Image.Image) -> PreparedPage:
    config = rules()["ocr"]
    original = image.convert("RGB")
    dpi = _effective_dpi(original)
    scale = 1.0

    # Small scans lose thin strokes when binarised. Upscale only when the
    # measured or implied resolution is genuinely low.
    threshold = int(config["upscale_below_dpi"])
    if dpi is not None and dpi < threshold:
        scale = max(scale, int(config["upscale_factor"]))
    elif dpi is None and min(original.size) < 900:
        scale = max(scale, int(config["upscale_factor"]))

    if scale != 1.0:
        original = original.resize(
            (int(original.width * scale), int(original.height * scale)),
            Image.Resampling.LANCZOS,
        )

    gray = _to_array(original)
    gray = cv2.fastNlMeansDenoising(gray, None, int(config["denoise_strength"]), 7, 21)

    skew = _estimate_skew(gray, float(config["deskew_max_degrees"]))
    gray = _deskew(gray, skew)

    # CLAHE lifts faint carbon-copy strokes in the shadows without blowing out
    # the paper, which keeps the later adaptive threshold stable.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    binary = cv2.adaptiveThreshold(
        enhanced,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        int(config["adaptive_block"]) | 1,
        int(config["adaptive_c"]),
    )
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))

    height, width = enhanced.shape[:2]
    return PreparedPage(
        gray=_to_image(enhanced),
        binary=_to_image(binary),
        width=width,
        height=height,
        scale=scale,
        skew_degrees=skew,
        dpi=dpi,
    )
