from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.core.config import rules

FaceBox = tuple[int, int, int, int]
FaceDetector = Callable[[Image.Image, dict[str, Any]], list[FaceBox] | None]


class PhotoUnreadable(ValueError):
    """The stored photo cannot be decoded, so no check can be trusted."""


@dataclass(slots=True)
class PhotoCheckResult:
    field: str
    passed: bool
    severity: str
    measured: str
    required: str
    detail: str


@dataclass(slots=True)
class PhotoAnalysis:
    """Every photo rule result, in report order."""

    checks: list[PhotoCheckResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def failures(self, severity: str | None = None) -> list[PhotoCheckResult]:
        failed = [check for check in self.checks if not check.passed]
        if severity is None:
            return failed
        return [check for check in failed if check.severity == severity]


@lru_cache(maxsize=1)
def _cascade() -> cv2.CascadeClassifier | None:
    path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(str(path))
    return None if cascade.empty() else cascade


def detect_faces(image: Image.Image, config: dict[str, Any]) -> list[FaceBox] | None:
    """Haar frontal-face detection, returning None when OpenCV has no cascade.

    None is deliberately distinct from an empty list: an unavailable detector
    must not accuse the applicant of having no face.
    """

    cascade = _cascade()
    if cascade is None:
        return None
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    boxes = cascade.detectMultiScale(
        gray,
        scaleFactor=float(config["face_scale_factor"]),
        minNeighbors=int(config["face_min_neighbors"]),
        # Detect small faces too; the ratio is judged below so the report can
        # say the face is present but too small rather than missing.
        minSize=(24, 24),
    )
    return [tuple(int(value) for value in box) for box in boxes]


def _check(
    field_name: str,
    passed: bool,
    *,
    measured: str,
    required: str,
    detail: str,
    severity: str = "critical",
) -> PhotoCheckResult:
    return PhotoCheckResult(
        field=field_name,
        passed=passed,
        severity="info" if passed else severity,
        measured=measured,
        required=required,
        detail=detail,
    )


def _resolution_check(width: int, height: int, config: dict[str, Any]) -> PhotoCheckResult:
    min_width = int(config["min_width"])
    min_height = int(config["min_height"])
    max_width = int(config["max_width"])
    max_height = int(config["max_height"])
    too_small = width < min_width or height < min_height
    too_large = width > max_width or height > max_height
    passed = not too_small and not too_large
    if too_small:
        detail = (
            f"The scan is {width} × {height} px. Use at least "
            f"{min_width} × {min_height} px so the face can be checked."
        )
    elif too_large:
        detail = (
            f"The scan is {width} × {height} px, above the {max_width} × {max_height} px "
            "limit. Downscale it to keep the file portable."
        )
    else:
        detail = "Within the accepted pixel range."
    return _check(
        "Resolution",
        passed,
        measured=f"{width} × {height} px",
        required=f"{min_width}–{max_width} × {min_height}–{max_height} px",
        detail=detail,
        severity="critical" if too_small else "warning",
    )


def _aspect_check(width: int, height: int, config: dict[str, Any]) -> PhotoCheckResult:
    minimum = float(config["min_aspect_ratio"])
    maximum = float(config["max_aspect_ratio"])
    ratio = width / height
    passed = minimum <= ratio <= maximum
    detail = (
        "The frame is within the portrait range."
        if passed
        else "The frame is too wide or too tall for a portrait photograph."
    )
    return _check(
        "Aspect ratio",
        passed,
        measured=f"{ratio:.2f}",
        required=f"{minimum:.2f}–{maximum:.2f} (portrait)",
        detail=detail,
        severity="warning",
    )


def _orientation_check(width: int, height: int) -> PhotoCheckResult:
    orientation = "Portrait" if height > width else ("Landscape" if width > height else "Square")
    passed = orientation == "Portrait"
    return _check(
        "Orientation",
        passed,
        measured=orientation,
        required="Portrait",
        detail=(
            "The photograph is upright."
            if passed
            else f"The photograph is {orientation.lower()}; rotate or re-crop it to portrait."
        ),
        severity="warning",
    )


def _size_check(size_bytes: int, config: dict[str, Any]) -> PhotoCheckResult:
    minimum = float(config["min_size_kb"])
    maximum = float(config["max_size_kb"])
    size_kb = size_bytes / 1024
    passed = minimum <= size_kb <= maximum
    if size_kb < minimum:
        detail = "The file is smaller than a usable photograph. Upload the original, not a thumbnail."
    elif size_kb > maximum:
        detail = "The file is larger than the photo limit. Compress it before uploading."
    else:
        detail = "The file size is within the accepted range."
    return _check(
        "File size",
        passed,
        measured=f"{size_kb:,.0f} KB",
        required=f"{minimum:,.0f}–{maximum:,.0f} KB",
        detail=detail,
        severity="warning",
    )


def _format_check(image_format: str, config: dict[str, Any]) -> PhotoCheckResult:
    allowed = [str(item).upper() for item in config["allowed_formats"]]
    passed = image_format in allowed
    return _check(
        "Format",
        passed,
        measured=image_format or "Unknown",
        required=" or ".join(allowed),
        detail=(
            "The image format is accepted."
            if passed
            else "Only JPEG and PNG photographs are accepted."
        ),
        severity="critical",
    )


def _brightness_check(gray: np.ndarray, config: dict[str, Any]) -> PhotoCheckResult:
    minimum = float(config["min_brightness"])
    maximum = float(config["max_brightness"])
    mean = float(gray.mean())
    passed = minimum <= mean <= maximum
    if mean < minimum:
        detail = "The photograph is too dark to verify. Retake it in even, natural light."
    elif mean > maximum:
        detail = "The photograph is overexposed. Retake it without a direct light source."
    else:
        detail = "Lighting is within the accepted range."
    return _check(
        "Brightness",
        passed,
        measured=f"{mean:.0f} / 255",
        required=f"{minimum:.0f}–{maximum:.0f}",
        detail=detail,
        severity="critical",
    )


def _sharpness_check(gray: np.ndarray, config: dict[str, Any]) -> PhotoCheckResult:
    minimum = float(config["min_sharpness"])
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    passed = variance >= minimum
    return _check(
        "Sharpness",
        passed,
        measured=f"{variance:,.0f}",
        required=f"at least {minimum:,.0f}",
        detail=(
            "Edges are crisp enough to check the face."
            if passed
            else "The photograph is blurry. Hold the camera steady or use a sharper original."
        ),
        severity="critical",
    )


def _blank_check(gray: np.ndarray, config: dict[str, Any]) -> PhotoCheckResult:
    blank_threshold = int(config["blank_pixel_threshold"])
    ink_threshold = int(config["ink_pixel_threshold"])
    max_blank = float(config["max_blank_ratio"])
    min_ink = float(config["min_ink_ratio"])

    blank_ratio = float((gray >= blank_threshold).mean())
    ink_ratio = float((gray <= ink_threshold).mean())
    passed = blank_ratio <= max_blank and ink_ratio >= min_ink
    if blank_ratio > max_blank:
        detail = "Most of the frame is blank. Use a photograph, not an empty scan."
    elif ink_ratio < min_ink:
        detail = "There is almost no subject in the frame."
    else:
        detail = "The frame contains a subject and is not washed out."
    return _check(
        "Exposure",
        passed,
        measured=f"{blank_ratio:.0%} blank · {ink_ratio * 100:.1f}% ink",
        required=f"≤ {max_blank:.0%} blank · ≥ {min_ink * 100:.1f}% ink",
        detail=detail,
        severity="critical",
    )


def _face_check(
    image: Image.Image,
    config: dict[str, Any],
    detector: FaceDetector,
) -> tuple[PhotoCheckResult, int | None, float | None]:
    if not config["face_check"]:
        return (
            _check(
                "Face",
                True,
                measured="Skipped",
                required="One clear frontal face",
                detail="Face detection is switched off in the rules.",
            ),
            None,
            None,
        )

    boxes = detector(image, config)
    minimum_ratio = float(config["face_min_size_ratio"])
    if boxes is None:
        return (
            _check(
                "Face",
                False,
                measured="Not run",
                required="One clear frontal face",
                detail=(
                    "The Haar detector is unavailable, so the face could not be checked. "
                    "A reviewer should confirm the photograph."
                ),
                severity="warning",
            ),
            None,
            None,
        )
    if not boxes:
        return (
            _check(
                "Face",
                False,
                measured="0 faces",
                required=f"one frontal face, at least {minimum_ratio:.0%} of the short side",
                detail=(
                    "No frontal face was detected. Haar can miss profiles, veils and low-contrast "
                    "photos; a reviewer should confirm this one."
                ),
                severity="warning",
            ),
            0,
            None,
        )

    x, y, width, height = max(boxes, key=lambda box: box[2] * box[3])
    shortest = max(1, min(image.width, image.height))
    face_ratio = width / shortest
    if len(boxes) > 1:
        return (
            _check(
                "Face",
                False,
                measured=f"{len(boxes)} faces",
                required=f"one frontal face, at least {minimum_ratio:.0%} of the short side",
                detail="More than one face was detected. Use a photograph of the applicant alone.",
                severity="warning",
            ),
            len(boxes),
            round(face_ratio, 3),
        )
    if face_ratio < minimum_ratio:
        return (
            _check(
                "Face",
                False,
                measured=f"1 face · {face_ratio:.0%} of the short side",
                required=f"at least {minimum_ratio:.0%} of the short side",
                detail="The face is present but too small in the frame. Crop closer.",
                severity="warning",
            ),
            1,
            round(face_ratio, 3),
        )
    return (
        _check(
            "Face",
            True,
            measured=f"1 face · {face_ratio:.0%} of the short side",
            required=f"at least {minimum_ratio:.0%} of the short side",
            detail="One clear frontal face was detected.",
        ),
        1,
        round(face_ratio, 3),
    )


def analyze_photo(
    data: bytes,
    mime_type: str | None = None,
    *,
    face_detector: FaceDetector | None = None,
) -> PhotoAnalysis:
    """Run every deterministic photo rule against an uploaded image.

    `face_detector` is injectable so tests can exercise the rule outcomes without
    depending on Haar's opinion of a synthetic fixture.
    """

    config = rules()["photo"]
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image_format = str(source.format or "").upper()
            image = ImageOps.exif_transpose(source).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - any decode failure is the same finding
        raise PhotoUnreadable(
            "The photograph could not be decoded. Upload a valid JPEG or PNG."
        ) from exc

    gray = np.asarray(image.convert("L"))
    detector = face_detector or detect_faces
    face_result, face_count, face_ratio = _face_check(image, config, detector)

    checks = [
        _resolution_check(image.width, image.height, config),
        _aspect_check(image.width, image.height, config),
        _orientation_check(image.width, image.height),
        _size_check(len(data), config),
        _format_check(image_format, config),
        _brightness_check(gray, config),
        _sharpness_check(gray, config),
        _blank_check(gray, config),
        face_result,
    ]
    metrics = {
        "format": image_format,
        "width": image.width,
        "height": image.height,
        "size_kb": round(len(data) / 1024, 1),
        "aspect_ratio": round(image.width / image.height, 3),
        "brightness": round(float(gray.mean()), 1),
        "sharpness": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1),
        "blank_ratio": round(float((gray >= int(config["blank_pixel_threshold"])).mean()), 3),
        "ink_ratio": round(float((gray <= int(config["ink_pixel_threshold"])).mean()), 4),
        "faces": face_count,
        "face_ratio": face_ratio,
        "mime_type": mime_type,
    }
    return PhotoAnalysis(checks=checks, metrics=metrics)
