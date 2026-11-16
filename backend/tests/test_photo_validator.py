from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from app.validators.photo import PhotoUnreadable, analyze_photo


def noisy_photo(width: int = 600, height: int = 800, seed: int = 7) -> bytes:
    """Deterministic mid-tone texture: bright, sharp and well over the 10 KB floor."""

    rng = np.random.default_rng(seed)
    pixels = rng.integers(90, 211, size=(height, width, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def flat_photo(
    width: int = 600, height: int = 800, level: int = 128, image_format: str = "PNG"
) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (level, level, level)).save(
        buffer, format=image_format
    )
    return buffer.getvalue()


def one_face(image: Image.Image, config: dict) -> list[tuple[int, int, int, int]]:
    return [(190, 150, 220, 220)]


def no_face(image: Image.Image, config: dict) -> list[tuple[int, int, int, int]]:
    return []


def two_faces(image: Image.Image, config: dict) -> list[tuple[int, int, int, int]]:
    return [(100, 150, 180, 180), (330, 150, 180, 180)]


def tiny_face(image: Image.Image, config: dict) -> list[tuple[int, int, int, int]]:
    return [(280, 340, 40, 40)]


def missing_detector(image: Image.Image, config: dict) -> None:
    return None


def by_field(analysis, field_name: str):
    return next(check for check in analysis.checks if check.field == field_name)


def test_good_photo_passes_every_rule():
    analysis = analyze_photo(noisy_photo(), "image/png", face_detector=one_face)

    assert analysis.passed, [check for check in analysis.checks if not check.passed]
    assert [check.field for check in analysis.checks] == [
        "Resolution",
        "Aspect ratio",
        "Orientation",
        "File size",
        "Format",
        "Brightness",
        "Sharpness",
        "Exposure",
        "Face",
    ]
    assert analysis.metrics["width"] == 600
    assert analysis.metrics["height"] == 800
    assert analysis.metrics["faces"] == 1
    assert analysis.metrics["face_ratio"] is not None


def test_dark_photo_fails_brightness():
    analysis = analyze_photo(flat_photo(level=20), "image/png", face_detector=one_face)

    brightness = by_field(analysis, "Brightness")
    assert brightness.passed is False
    assert brightness.severity == "critical"
    assert brightness.measured == "20 / 255"
    assert "too dark" in brightness.detail
    assert not analysis.passed


def test_uniform_gray_photo_fails_sharpness():
    analysis = analyze_photo(flat_photo(level=128), "image/png", face_detector=one_face)

    sharpness = by_field(analysis, "Sharpness")
    assert sharpness.passed is False
    assert sharpness.severity == "critical"
    assert "blurry" in sharpness.detail


def test_blank_scan_fails_exposure():
    analysis = analyze_photo(flat_photo(level=250), "image/png", face_detector=one_face)

    exposure = by_field(analysis, "Exposure")
    assert exposure.passed is False
    assert exposure.severity == "critical"
    assert exposure.measured.startswith("100% blank")
    assert "most of the frame is blank" in exposure.detail.lower()


def test_landscape_photo_warns_about_orientation_and_aspect():
    analysis = analyze_photo(noisy_photo(800, 600), "image/png", face_detector=one_face)

    orientation = by_field(analysis, "Orientation")
    aspect = by_field(analysis, "Aspect ratio")
    assert orientation.passed is False
    assert orientation.severity == "warning"
    assert orientation.measured == "Landscape"
    assert aspect.passed is False
    assert aspect.severity == "warning"
    assert by_field(analysis, "Resolution").passed is True


def test_small_resolution_is_critical():
    analysis = analyze_photo(
        noisy_photo(200, 300), "image/png", face_detector=one_face
    )

    resolution = by_field(analysis, "Resolution")
    assert resolution.passed is False
    assert resolution.severity == "critical"
    assert resolution.measured == "200 × 300 px"
    assert "at least 300 × 400 px" in resolution.detail
    assert [check.field for check in analysis.failures()] == ["Resolution"]


def test_missing_face_is_a_warning_not_a_failure_to_reject():
    analysis = analyze_photo(noisy_photo(), "image/png", face_detector=no_face)

    face = by_field(analysis, "Face")
    assert face.passed is False
    assert face.severity == "warning"
    assert face.measured == "0 faces"
    assert "reviewer should confirm" in face.detail
    assert analysis.metrics["faces"] == 0


def test_multiple_faces_warn():
    analysis = analyze_photo(noisy_photo(), "image/png", face_detector=two_faces)

    face = by_field(analysis, "Face")
    assert face.passed is False
    assert face.severity == "warning"
    assert face.measured == "2 faces"
    assert analysis.metrics["faces"] == 2


def test_tiny_face_warns():
    analysis = analyze_photo(noisy_photo(), "image/png", face_detector=tiny_face)

    face = by_field(analysis, "Face")
    assert face.passed is False
    assert face.severity == "warning"
    assert face.measured.startswith("1 face · 7%")
    assert "too small" in face.detail


def test_unavailable_detector_does_not_accuse_the_photo():
    analysis = analyze_photo(
        noisy_photo(), "image/png", face_detector=missing_detector
    )

    face = by_field(analysis, "Face")
    assert face.passed is False
    assert face.severity == "warning"
    assert face.measured == "Not run"
    assert "detector is unavailable" in face.detail
    assert analysis.metrics["faces"] is None


def test_disallowed_format_fails():
    data = flat_photo(image_format="BMP")
    analysis = analyze_photo(data, "image/bmp", face_detector=one_face)

    image_format = by_field(analysis, "Format")
    assert image_format.passed is False
    assert image_format.severity == "critical"
    assert image_format.measured == "BMP"
    assert image_format.required == "JPEG or PNG"


def test_unreadable_bytes_raise():
    with pytest.raises(PhotoUnreadable):
        analyze_photo(b"this is not an image", "image/png")
