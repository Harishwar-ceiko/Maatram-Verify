"""Deterministic Aadhaar checks: Verhoeff, masking, QR decoding and comparison.

No Aadhaar number is ever printed in a finding, stored in an OCR field, logged
or sent to the browser. The full number lives encrypted in ``AadhaarRecord``;
everything else works with the last four digits.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from datetime import date
from typing import Any, Iterable, Sequence

import cv2
import numpy as np
from PIL import Image

# Verhoeff tables.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)

# 12 digits, optionally grouped 4-4-4 with spaces or hyphens.
_AADHAAR_PATTERN = re.compile(r"(?<!\d)(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)")
_GROUPS = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")


def digits_only(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def verhoeff_valid(number: str) -> bool:
    cleaned = digits_only(number)
    if len(cleaned) != 12:
        return False
    checksum = 0
    for index, character in enumerate(reversed(cleaned)):
        checksum = _D[checksum][_P[index % 8][int(character)]]
    return checksum == 0


def verhoeff_checksum_digit(base: str) -> str:
    """Return the check digit that makes ``base + digit`` Verhoeff-valid."""

    cleaned = digits_only(base)
    checksum = 0
    for index, character in enumerate(reversed(cleaned)):
        checksum = _D[checksum][_P[(index + 1) % 8][int(character)]]
    return str(_INV[checksum])


def mask_number(value: str | None, *, prefix: str = "XXXX XXXX") -> str | None:
    cleaned = digits_only(value)
    if len(cleaned) < 4:
        return None
    return f"{prefix} {cleaned[-4:]}"


def mask_last4(last4: str | None, *, prefix: str = "XXXX XXXX") -> str | None:
    if not last4 or not re.fullmatch(r"\d{4}", last4):
        return None
    return f"{prefix} {last4}"


def redact_text(value: str, *, prefix: str = "XXXX XXXX") -> str:
    """Replace every Aadhaar-shaped 12-digit group in free text."""

    def replace(match: re.Match[str]) -> str:
        number = "".join(part for part in match.groups() if part)
        return mask_number(number, prefix=prefix) or "XXXX XXXX XXXX"

    return _AADHAAR_PATTERN.sub(replace, value or "")


def redact_filename(value: str, *, prefix: str = "XXXX XXXX") -> str:
    stem = value or "document"
    stem = _AADHAAR_PATTERN.sub(
        lambda match: (mask_number("".join(match.groups()), prefix=prefix) or "aadhaar")
        .replace(" ", "-")
        .replace("X", "x"),
        stem,
    )
    return re.sub(r"x{4}-?x{4}-(\d{4})", r"aadhaar-\1", stem, flags=re.IGNORECASE)


def candidates(text: str) -> list[str]:
    """Every 12-digit group in printed order, without duplicates."""

    found: list[str] = []
    for match in _GROUPS.finditer(text or ""):
        number = digits_only(match.group(0))
        if len(number) == 12 and number not in found:
            found.append(number)
    return found


def best_candidate(text: str) -> tuple[str | None, bool]:
    """Prefer a Verhoeff-valid number; fall back to the first readable one."""

    found = candidates(text)
    for number in found:
        if verhoeff_valid(number):
            return number, True
    return (found[0] if found else None), False


def _scale(image: Image.Image, maximum: int = 1600) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= maximum:
        return image
    ratio = maximum / longest
    return image.resize(
        (max(1, int(width * ratio)), max(1, int(height * ratio))),
        Image.Resampling.LANCZOS,
    )


def decode_qr(images: Sequence[Image.Image]) -> list[str]:
    """Decode visible QR payloads with OpenCV. Returns [] when none is found."""

    detector = cv2.QRCodeDetector()
    payloads: list[str] = []
    for source in images:
        image = _scale(source.convert("RGB"))
        gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
        attempts = [gray, cv2.bitwise_not(gray)]
        for frame in attempts:
            try:
                payload, _points, _straight = detector.detectAndDecode(frame)
            except cv2.error:
                payload = ""
            if not payload:
                try:
                    ok, decoded, _points, _straight = detector.detectAndDecodeMulti(frame)
                except (cv2.error, AttributeError):
                    ok, decoded = False, ()
                if ok:
                    payloads.extend(str(item) for item in decoded if item)
                continue
            if payload not in payloads:
                payloads.append(payload)
    return payloads


def _payload_text(payload: str) -> str:
    """Secure QR payloads are signed binary blobs; try text and XML attributes."""

    text = payload
    if payload.lstrip().startswith("<"):
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError:
            root = None
        if root is not None:
            text = " ".join([payload, *root.attrib.values()])
    # Aadhaar QR payloads are often URL-encoded or contain a uid= value.
    return text.replace("%20", " ")


def parse_qr_number(payloads: Iterable[str]) -> tuple[str | None, bool]:
    for payload in payloads:
        text = _payload_text(payload)
        number, valid = best_candidate(text)
        if number is not None:
            return number, valid
    return None, False


def compare_qr(payloads: Sequence[str], printed: str | None) -> dict[str, Any]:
    if not payloads:
        return {"status": "not_detected", "masked": None, "valid": False}
    qr_number, qr_valid = parse_qr_number(payloads)
    if qr_number is None:
        return {"status": "unreadable", "masked": None, "valid": False}
    status = "match" if printed and qr_number == printed else "mismatch"
    return {
        "status": status,
        "masked": mask_number(qr_number),
        "last4": qr_number[-4:],
        "valid": qr_valid,
    }


def dob_comparison(
    application_dob: date | None,
    extracted_dob: date | None,
    extracted_year: int | None,
) -> dict[str, Any] | None:
    """Return a stable comparison record, or None when Aadhaar has no birth data."""

    if extracted_dob is not None and application_dob is not None:
        matched = extracted_dob == application_dob
        return {
            "matched": matched,
            "entered": application_dob.isoformat(),
            "uploaded": extracted_dob.isoformat(),
            "measured": "exact date" if matched else "different date",
            "detail": (
                "The date of birth matches the application."
                if matched
                else "The date of birth on the Aadhaar does not match the application."
            ),
        }
    if extracted_year is not None and application_dob is not None:
        matched = extracted_year == application_dob.year
        return {
            "matched": matched,
            "entered": str(application_dob.year),
            "uploaded": str(extracted_year),
            "measured": "year of birth",
            "detail": (
                "The year of birth matches the application."
                if matched
                else "The year of birth on the Aadhaar does not match the application."
            ),
        }
    return None
