"""Deterministic synthetic corpus for accuracy evaluation and demos.

Every mark sheet is generated from a fixed seed, carries a fictional identity,
and is paired with the exact values printed on it. Variants add the kind of
degradation a real phone photograph brings: grain, blur, a slight tilt, uneven
light and JPEG compression. Photos use a public-domain stand-in portrait and
controlled perturbations, so each photo fixture has a known rule outcome.
"""

from __future__ import annotations

import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.core.config import ASSETS_DIR, SYNTHETIC_DIR, rules
from app.validators.aadhaar import verhoeff_checksum_digit, verhoeff_valid

PAPER = (250, 248, 240)
INK = (28, 27, 22)
MUTED = (110, 105, 92)
LINE = (196, 190, 174)
HEADER_FILL = (236, 231, 218)
ACCENT = (166, 58, 27)
WARM = (231, 225, 211)

SHEET_SIZE = (1240, 1754)
CARD_SIZE = (1240, 780)
VARIANTS = ("clean", "noise", "blur", "rotate", "shadow", "jpeg")
CLASS11_CASES = 6

NAMES = (
    "AARAV NATARAJAN",
    "DIYA MENON",
    "KARTHIK RANGANATHAN",
    "MEERA BALAKRISHNAN",
    "NITHIN VARGHESE",
    "PRIYANKA SELVAM",
    "RAHUL CHANDRASEKHAR",
    "SAHANA IYER",
    "TARUN MOHAN",
    "VAISHNAVI RAJENDRAN",
    "ADITYA NARAYANAN",
    "BHAVANA SURESH",
    "DINESH KUMARAVEL",
    "ESHA PRABHAKARAN",
    "GANESH SUNDARAM",
    "HARINI VENKATESAN",
    "IRFAN AHAMED",
    "JANANI MURUGAN",
    "KAVIN ALAGAPPAN",
    "LAKSHMI DEVI",
    "MANOJ PERUMAL",
    "NANDINI KRISHNAN",
    "OM PRAKASH",
    "PAVITHRA SHANMUGAM",
    "RITHIKA ARUNACHALAM",
    "SURIYA BHARATHI",
    "TRISHA GOPINATH",
    "UDHAYA KUMAR",
    "VARSHINI MOHANRAJ",
    "YASHWANTH RAMESH",
)

BASE_SUBJECTS = ("Mathematics", "English", "Physics", "Chemistry")
OPTIONAL_SUBJECTS = ("Computer Science", "Biology", "Accountancy", "Economics")

FONT_PATHS = {
    "serif": ("C:/Windows/Fonts/georgia.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    "serif_bold": (
        "C:/Windows/Fonts/georgiab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ),
    "sans": ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    "sans_bold": (
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "mono": ("C:/Windows/Fonts/cour.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
}


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - old Pillow
        return ImageFont.load_default()


def _grade(marks: int) -> str:
    if marks >= 90:
        return "A+"
    if marks >= 80:
        return "A"
    if marks >= 70:
        return "B+"
    return "B"


def _render_sheet(
    name: str,
    register: str,
    exam_year: int,
    board: str,
    subjects: list[dict[str, Any]],
    *,
    class_level: int = 12,
) -> Image.Image:
    width, height = SHEET_SIZE
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    margin = 110
    roman = "XII" if class_level == 12 else "XI"
    subtitle = (
        f"Class {roman} · Higher Secondary Certificate Examination · March {exam_year}"
        if class_level == 12
        else f"Class {roman} · Higher Secondary First Year Examination · March {exam_year}"
    )

    draw.rectangle(
        [margin - 40, margin - 40, width - margin + 40, height - margin + 40],
        outline=LINE,
        width=2,
    )
    draw.text((margin, margin), "STATE BOARD OF EXAMINATIONS", font=_font("sans_bold", 26), fill=MUTED)
    draw.text((margin, margin + 56), "Statement of Marks", font=_font("serif", 64), fill=INK)
    draw.line([margin, margin + 150, width - margin, margin + 150], fill=INK, width=2)
    draw.text(
        (margin, margin + 176),
        subtitle,
        font=_font("sans", 24),
        fill=MUTED,
    )

    fields = [
        ("Candidate", name),
        ("Register No.", register),
        ("Examination", f"March {exam_year}"),
        ("Board", board),
    ]
    top = margin + 250
    for index, (label, value) in enumerate(fields):
        column = index % 2
        row = index // 2
        x = margin + column * 520
        y = top + row * 74
        draw.text((x, y), label.upper(), font=_font("sans", 17), fill=MUTED)
        draw.text((x, y + 26), value, font=_font("sans_bold", 27), fill=INK)

    table_top = top + 190
    columns = [margin, margin + 520, margin + 720, margin + 880, width - margin]
    headers = ["Subject", "Maximum", "Obtained", "Grade"]
    draw.rectangle([margin, table_top, width - margin, table_top + 58], fill=HEADER_FILL)
    for column, header in zip(columns, headers):
        offset = 0 if header == "Subject" else 8
        draw.text(
            (column + offset, table_top + 18),
            header,
            font=_font("sans_bold", 20),
            fill=INK,
        )
    draw.line([margin, table_top, width - margin, table_top], fill=INK, width=2)
    draw.line([margin, table_top + 58, width - margin, table_top + 58], fill=LINE, width=1)

    row_height = 74
    for index, subject in enumerate(subjects):
        y = table_top + 58 + index * row_height
        draw.line([margin, y + row_height, width - margin, y + row_height], fill=LINE, width=1)
        values = [
            str(subject["subject"]),
            str(subject["max_marks"]),
            str(subject["marks"]),
            str(subject["grade"]),
        ]
        for column, value in zip(columns, values):
            offset = 0 if column == margin else 8
            face = "sans" if column == margin else "mono"
            draw.text(
                (column + offset, y + 22),
                value,
                font=_font(face, 26 if column == margin else 26),
                fill=INK,
            )

    footer = height - 300
    draw.line([margin, footer, width - margin, footer], fill=LINE, width=1)
    draw.text((margin, footer + 30), "Result: PASS", font=_font("sans_bold", 28), fill=INK)
    draw.text(
        (margin, footer + 80),
        "Synthetic evaluation document · not a real student record.",
        font=_font("sans", 19),
        fill=MUTED,
    )
    draw.text((width - margin - 300, footer + 150), "Controller of Examinations", font=_font("serif", 24), fill=MUTED)
    draw.line([width - margin - 300, footer + 190, width - margin, footer + 190], fill=LINE, width=1)
    return image


def synthetic_aadhaar(seed: int, *, valid: bool = True) -> str:
    """Return a 12-digit synthetic Aadhaar-shaped number.

    It starts with 0 or 1, is not issued to anybody, and only exists so the
    Verhoeff and masking paths can be measured. ``valid=False`` changes the
    check digit, which is enough to make the checksum fail.
    """

    rng = random.Random(seed)
    base = rng.choice("01") + "".join(str(rng.randrange(10)) for _ in range(10))
    number = base + verhoeff_checksum_digit(base)
    if valid:
        return number
    return number[:-1] + str((int(number[-1]) + 1) % 10)


def _render_aadhaar(
    name: str,
    number: str,
    *,
    gender: str,
    address: str,
    date_of_birth: str | None = None,
    year_of_birth: int | None = None,
) -> Image.Image:
    width, height = CARD_SIZE
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    margin = 80

    draw.rectangle([0, 0, width, 18], fill=(244, 146, 54))
    draw.rectangle([0, 18, width, 30], fill=(255, 255, 255))
    draw.rectangle([0, 30, width, 48], fill=(19, 136, 8))
    draw.rectangle(
        [margin - 24, 70, width - margin + 24, height - 54],
        outline=LINE,
        width=2,
    )
    draw.text(
        (margin, 92),
        "GOVERNMENT OF INDIA",
        font=_font("sans_bold", 24),
        fill=MUTED,
    )
    draw.text(
        (margin, 128),
        "Unique Identification Authority of India",
        font=_font("sans", 22),
        fill=MUTED,
    )
    draw.text((margin, 168), "Aadhaar", font=_font("serif_bold", 58), fill=INK)
    draw.line([margin, 246, width - margin, 246], fill=LINE, width=1)

    draw.text((margin, 278), f"Name: {name}", font=_font("sans_bold", 31), fill=INK)
    line_y = 336
    if date_of_birth is not None:
        draw.text(
            (margin, line_y),
            f"Date of Birth: {date_of_birth}",
            font=_font("sans", 29),
            fill=INK,
        )
        line_y += 54
    elif year_of_birth is not None:
        draw.text(
            (margin, line_y),
            f"Year of Birth: {year_of_birth}",
            font=_font("sans", 29),
            fill=INK,
        )
        line_y += 54
    draw.text((margin, line_y), f"Gender: {gender}", font=_font("sans", 29), fill=INK)
    draw.text((margin, line_y + 54), f"Address: {address}", font=_font("sans", 27), fill=INK)

    draw.rectangle([margin, 548, width - margin, 650], fill=WARM)
    number_text = f"{number[:4]} {number[4:8]} {number[8:]}"
    draw.text(
        (margin + 38, 568),
        number_text,
        font=_font("mono", 58),
        fill=INK,
    )
    draw.text(
        (margin, height - 40),
        "Synthetic evaluation card · not a real Aadhaar.",
        font=_font("sans", 18),
        fill=MUTED,
    )
    return image


def _render_certificate(
    title: str,
    *,
    certificate_number: str,
    name: str,
    father_name: str,
    address: str,
    issue_date: str,
    rows: list[tuple[str, str]],
) -> Image.Image:
    width, height = SHEET_SIZE
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    margin = 120

    draw.rectangle(
        [margin - 42, margin - 42, width - margin + 42, height - margin + 42],
        outline=LINE,
        width=2,
    )
    draw.text(
        (margin, margin - 6),
        "GOVERNMENT OF TAMIL NADU",
        font=_font("sans_bold", 25),
        fill=MUTED,
    )
    draw.text(
        (margin, margin + 32),
        "Revenue Department · Taluk Office",
        font=_font("sans", 21),
        fill=MUTED,
    )
    draw.text((margin, margin + 104), title, font=_font("serif_bold", 62), fill=INK)
    draw.line([margin, margin + 208, width - margin, margin + 208], fill=INK, width=2)
    draw.text(
        (margin, margin + 238),
        f"Certificate No: {certificate_number}",
        font=_font("sans_bold", 28),
        fill=INK,
    )

    fields = [
        ("Name", name),
        ("Father's Name", father_name),
        ("Address", address),
    ]
    top = margin + 310
    for label, value in fields:
        draw.text((margin, top), f"{label}: {value}", font=_font("sans", 29), fill=INK)
        top += 66

    top += 18
    for label, value in rows:
        draw.text((margin, top), f"{label}: {value}", font=_font("sans_bold", 30), fill=INK)
        top += 68

    top += 22
    draw.text((margin, top), f"Date of Issue: {issue_date}", font=_font("sans", 29), fill=INK)

    footer = height - 330
    draw.line([margin, footer, width - margin, footer], fill=LINE, width=1)
    draw.text(
        (margin, footer + 34),
        "This certificate is issued for educational assistance purposes.",
        font=_font("sans", 21),
        fill=MUTED,
    )
    draw.text(
        (margin, footer + 92),
        "Synthetic evaluation document · not a real certificate.",
        font=_font("sans", 20),
        fill=MUTED,
    )
    draw.text(
        (width - margin - 300, footer + 170),
        "Tahsildar",
        font=_font("serif", 26),
        fill=MUTED,
    )
    draw.line([width - margin - 300, footer + 210, width - margin, footer + 210], fill=LINE, width=1)
    return image


def _apply_variant(image: Image.Image, variant: str, seed: int) -> tuple[Image.Image, str]:
    if variant == "clean":
        return image, "image/png"
    if variant == "noise":
        rng = np.random.default_rng(seed)
        pixels = np.asarray(image).astype(np.int16)
        noise = rng.normal(0, 9, size=pixels.shape).astype(np.int16)
        return Image.fromarray(np.clip(pixels + noise, 0, 255).astype(np.uint8), "RGB"), "image/png"
    if variant == "blur":
        return image.filter(ImageFilter.GaussianBlur(1.3)), "image/png"
    if variant == "rotate":
        angle = 0.9 + (seed % 3) * 0.25
        return (
            image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=PAPER),
            "image/png",
        )
    if variant == "shadow":
        width, height = image.size
        gradient = np.linspace(0.78, 1.0, width, dtype=np.float32)[None, :, None]
        pixels = np.asarray(image).astype(np.float32) * gradient
        return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB"), "image/png"
    if variant == "jpeg":
        return image, "image/jpeg"
    raise ValueError(f"Unknown sheet variant: {variant}")


def _entered_marks(
    subjects: list[dict[str, Any]], design: int, rng: random.Random
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entered = [
        {
            "subject": row["subject"],
            "marks": row["marks"],
            "max_marks": row["max_marks"],
        }
        for row in subjects
    ]
    expected: dict[str, Any] = {
        "mismatches": [],
        "missing_upload": [],
        "extra_on_sheet": [],
    }

    if design in (1, 2):
        chosen = rng.sample(range(len(subjects)), design)
        for index in chosen:
            sheet_marks = subjects[index]["marks"]
            delta = rng.choice((-5, -3, 3, 4))
            entered_marks = sheet_marks + delta
            if not 0 <= entered_marks <= 100 or entered_marks == sheet_marks:
                entered_marks = sheet_marks - 2 if sheet_marks >= 2 else sheet_marks + 2
            entered[index]["marks"] = entered_marks
            expected["mismatches"].append(
                {
                    "subject": subjects[index]["subject"],
                    "entered": entered_marks,
                    "sheet": sheet_marks,
                }
            )
    elif design == 3:
        entered.append({"subject": "Biology", "marks": 71, "max_marks": 100})
        expected["missing_upload"].append("Biology")
    elif design == 4:
        dropped = entered.pop()
        expected["extra_on_sheet"].append(dropped["subject"])

    return entered, expected


def _noise_image(width: int, height: int, low: int, high: int, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(low, high + 1, size=(height, width, 3), dtype=np.uint8)
    return Image.fromarray(pixels, "RGB")


def _base_portrait() -> Image.Image:
    path = ASSETS_DIR / "portrait-standin.jpg"
    with Image.open(path) as source:
        image = source.convert("RGB")
    # The original is 512 x 600; crop to 480 x 600 so the frame is inside the
    # portrait aspect rules while keeping the whole face.
    left = (image.width - 480) // 2
    return image.crop((left, 0, left + 480, image.height))


def _photo_fixtures(root: Path) -> list[dict[str, Any]]:
    photos = root / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    base = _base_portrait()
    width, height = base.size
    fixtures: list[dict[str, Any]] = []

    def save(name: str, image: Image.Image, image_format: str = "PNG") -> str:
        suffix = ".jpg" if image_format == "JPEG" else f".{image_format.lower()}"
        path = photos / f"{name}{suffix}"
        if image_format == "JPEG":
            image.save(path, format="JPEG", quality=88)
            return f"photos/{path.name}"
        image.save(path, format=image_format)
        return f"photos/{path.name}"

    def add(
        slug: str,
        file: str,
        mime: str,
        expected: dict[str, str],
        expected_critical: list[str],
        note: str,
    ) -> None:
        fixtures.append(
            {
                "id": f"photo-{slug}",
                "file": file,
                "mime": mime,
                "expected": expected,
                "expected_critical": expected_critical,
                "note": note,
            }
        )

    good = save("photo-good", base)
    add(
        "good",
        good,
        "image/png",
        {
            "Resolution": "pass",
            "Aspect ratio": "pass",
            "Orientation": "pass",
            "File size": "pass",
            "Format": "pass",
            "Brightness": "pass",
            "Sharpness": "pass",
            "Exposure": "pass",
            "Face": "pass",
        },
        [],
        "Clean portrait, within every rule.",
    )

    dark = ImageEnhance.Brightness(base).enhance(0.32)
    add(
        "dark",
        save("photo-dark", dark),
        "image/png",
        {"Brightness": "fail"},
        ["Brightness"],
        "Underexposed portrait.",
    )

    washed = Image.blend(base, Image.new("RGB", (width, height), (255, 255, 255)), 0.82)
    add(
        "washed",
        save("photo-washed", washed),
        "image/png",
        {"Brightness": "fail"},
        ["Brightness", "Sharpness", "Exposure"],
        "Overexposed portrait; detail collapses along with the exposure.",
    )

    blurry = base.filter(ImageFilter.GaussianBlur(18))
    add(
        "blurry",
        save("photo-blurry", blurry),
        "image/png",
        {"Sharpness": "fail"},
        ["Sharpness"],
        "Heavily defocused portrait.",
    )

    blank = _noise_image(width, height, 170, 240, 4401)
    add(
        "blank",
        save("photo-blank", blank),
        "image/png",
        {"Exposure": "fail"},
        ["Exposure"],
        "Bright but no subject detail.",
    )

    small = base.resize((220, 275), Image.Resampling.LANCZOS)
    add(
        "lowres",
        save("photo-lowres", small),
        "image/png",
        {"Resolution": "fail"},
        ["Resolution"],
        "Thumbnail-sized portrait.",
    )

    landscape = base.rotate(90, expand=True)
    add(
        "landscape",
        save("photo-landscape", landscape),
        "image/png",
        {"Orientation": "fail", "Aspect ratio": "fail"},
        [],
        "Sideways portrait; warnings, not a rejection.",
    )

    no_face = _noise_image(width, height, 90, 210, 4402)
    add(
        "no-face",
        save("photo-no-face", no_face),
        "image/png",
        {"Face": "fail"},
        [],
        "No face in frame; reviewer warning.",
    )

    two = Image.new("RGB", (640, 800), (232, 226, 212))
    first = base.resize((300, 375), Image.Resampling.LANCZOS)
    second = first.copy()
    two.paste(first, (10, 220))
    two.paste(second, (330, 220))
    add(
        "two-faces",
        save("photo-two-faces", two),
        "image/png",
        {"Face": "fail"},
        [],
        "Two faces in the frame.",
    )

    tiny = _noise_image(width, height, 105, 195, 4403)
    tiny_face = base.resize((64, 80), Image.Resampling.LANCZOS)
    tiny.paste(tiny_face, (208, 260))
    add(
        "tiny-face",
        save("photo-tiny-face", tiny),
        "image/png",
        {"Face": "fail"},
        [],
        "Subject too small in the frame.",
    )

    bmp = save("photo-bmp", base, "BMP")
    add(
        "bmp",
        bmp,
        "image/bmp",
        {"Format": "fail"},
        ["Format"],
        "Unsupported container.",
    )

    return fixtures


def _document_fixtures(root: Path, seed: int) -> list[dict[str, Any]]:
    """Render supporting documents with their exact printed values.

    Aadhaar fixtures carry only the masked last four digits and the expected
    checksum state in ground truth. The full synthetic number is never written
    to ``dataset.json``.
    """

    folder = root / "documents"
    folder.mkdir(parents=True, exist_ok=True)
    fixtures: list[dict[str, Any]] = []

    def save(slug: str, image: Image.Image, variant: str) -> tuple[str, str]:
        rendered, mime = _apply_variant(image, variant, seed + len(fixtures) * 19)
        suffix = ".jpg" if mime == "image/jpeg" else ".png"
        path = folder / f"{slug}{suffix}"
        if mime == "image/jpeg":
            rendered.save(path, format="JPEG", quality=74)
        else:
            rendered.save(path, format="PNG", optimize=True)
        return f"documents/{path.name}", mime

    def add(
        slug: str,
        kind: str,
        image: Image.Image,
        variant: str,
        expected: dict[str, Any],
        note: str,
    ) -> None:
        file, mime = save(slug, image, variant)
        fixtures.append(
            {
                "id": slug,
                "kind": kind,
                "file": file,
                "mime": mime,
                "variant": variant,
                "expected": expected,
                "note": note,
            }
        )

    people = [
        (NAMES[0], "Ravi Natarajan", "12, Gandhi Street, Chennai 600028", "Male"),
        (NAMES[1], "Suresh Menon", "44, Lake View Road, Kochi 682016", "Female"),
        (NAMES[2], "Ranganathan Iyer", "8, Temple Street, Madurai 625001", "Male"),
        (NAMES[3], "Balakrishnan Nair", "17, Beach Road, Thiruvananthapuram 695001", "Female"),
        (NAMES[4], "Varghese Thomas", "5, Hill Colony, Coimbatore 641002", "Male"),
        (NAMES[5], "Selvam Murugan", "23, Market Street, Salem 636001", "Female"),
        (NAMES[6], "Chandrasekhar Rao", "61, Park Avenue, Trichy 620001", "Male"),
        (NAMES[7], "Iyer Subramanian", "9, River Bank, Thanjavur 613001", "Female"),
        (NAMES[8], "Mohan Raj", "31, School Street, Vellore 632001", "Male"),
        (NAMES[9], "Rajendran Pillai", "72, Garden Road, Kanchipuram 631501", "Female"),
        (NAMES[10], "Narayanan Kutty", "15, Fort Road, Tirunelveli 627001", "Male"),
        (NAMES[11], "Suresh Babu", "40, Bazaar Street, Erode 638001", "Female"),
    ]

    aadhaar_specs = [
        ("aadhaar-valid-dob", 0, "clean", True, "2008-04-18", None, "18/04/2008"),
        ("aadhaar-valid-year", 1, "rotate", True, "2007", 2007, None),
        ("aadhaar-valid-jpeg", 2, "jpeg", True, "2007-09-07", None, "07/09/2007"),
        ("aadhaar-invalid-checksum", 3, "clean", False, "2007-11-22", None, "22/11/2007"),
    ]
    for offset, (slug, person_index, variant, valid, birth_detail, year, date_text) in enumerate(
        aadhaar_specs
    ):
        name, _father, address, gender = people[person_index]
        number = synthetic_aadhaar(seed + 500 + offset, valid=valid)
        image = _render_aadhaar(
            name,
            number,
            gender=gender,
            address=address,
            date_of_birth=date_text,
            year_of_birth=year,
        )
        add(
            slug,
            "aadhaar",
            image,
            variant,
            {
                "name": name,
                "birth_detail": birth_detail,
                "aadhaar_last4": number[-4:],
                "checksum_valid": valid,
                "gender": gender,
            },
            (
                "Verhoeff-valid synthetic number with a printed date of birth."
                if valid and date_text
                else "Verhoeff-valid synthetic number with only a year of birth."
                if valid
                else "Synthetic number whose last digit fails the Verhoeff checksum."
            ),
        )

    certificate_specs = [
        (
            "income-valid",
            "income_certificate",
            4,
            "clean",
            "Income Certificate",
            "INC/2026/0042",
            "12/04/2026",
            "2026-04-12",
            [("Annual Income", "INR 1,80,000")],
            {"annual_income": 180000},
            "Annual income below the assistance threshold.",
        ),
        (
            "income-jpeg",
            "income_certificate",
            5,
            "jpeg",
            "Income Certificate",
            "INC/2026/0077",
            "19/04/2026",
            "2026-04-19",
            [("Annual Income", "INR 2,40,000")],
            {"annual_income": 240000},
            "Compressed certificate still below the threshold.",
        ),
        (
            "income-above-threshold",
            "income_certificate",
            6,
            "shadow",
            "Income Certificate",
            "INC/2026/0104",
            "02/05/2026",
            "2026-05-02",
            [("Annual Income", "INR 3,20,000")],
            {"annual_income": 320000},
            "Uneven light; income printed above the threshold.",
        ),
        (
            "community-clean",
            "community_certificate",
            7,
            "clean",
            "Community Certificate",
            "COM/2026/0031",
            "10/05/2026",
            "2026-05-10",
            [("Community", "BC"), ("Category", "Backward Class")],
            {"community": "BC"},
            "Community stated as BC.",
        ),
        (
            "community-jpeg",
            "community_certificate",
            8,
            "jpeg",
            "Community Certificate",
            "COM/2026/0058",
            "16/05/2026",
            "2026-05-16",
            [("Community", "MBC"), ("Category", "Most Backward Class")],
            {"community": "MBC"},
            "Compressed certificate stating MBC.",
        ),
        (
            "first-graduate-yes",
            "first_graduate_certificate",
            9,
            "clean",
            "First Graduate Certificate",
            "FG/2026/0018",
            "03/06/2026",
            "2026-06-03",
            [("First Graduate", "YES"), ("Status", "First Graduate")],
            {"first_graduate": "yes"},
            "First graduate in the family.",
        ),
        (
            "first-graduate-no",
            "first_graduate_certificate",
            10,
            "clean",
            "First Graduate Certificate",
            "FG/2026/0025",
            "09/06/2026",
            "2026-06-09",
            [("Status", "Not a first graduate")],
            {"first_graduate": "no"},
            "Certificate records that the applicant is not a first graduate.",
        ),
        (
            "first-graduate-jpeg",
            "first_graduate_certificate",
            11,
            "jpeg",
            "First Graduate Certificate",
            "FG/2026/0039",
            "21/06/2026",
            "2026-06-21",
            [("First Graduate", "YES"), ("Status", "First Graduate")],
            {"first_graduate": "yes"},
            "Compressed first-graduate certificate.",
        ),
    ]
    for (
        slug,
        kind,
        person_index,
        variant,
        title,
        number,
        date_text,
        issue_date,
        rows,
        extra,
        note,
    ) in certificate_specs:
        name, father, address, _gender = people[person_index]
        image = _render_certificate(
            title,
            certificate_number=number,
            name=name,
            father_name=father,
            address=address,
            issue_date=date_text,
            rows=rows,
        )
        expected = {
            "name": name,
            "certificate_number": number,
            "issue_date": issue_date,
            **extra,
        }
        add(slug, kind, image, variant, expected, note)

    return fixtures


def generate_dataset(force: bool = True) -> dict[str, Any]:
    """Write the synthetic corpus and return its ground truth."""

    config = rules()["evaluation"]
    count = int(config["cases"])
    class11_count = int(config.get("class_11_cases", CLASS11_CASES))
    seed = int(config["seed"])
    if count + class11_count > len(NAMES):
        raise ValueError("Not enough fictional names for the requested case count")

    if force and SYNTHETIC_DIR.exists():
        shutil.rmtree(SYNTHETIC_DIR)
    sheets = SYNTHETIC_DIR / "sheets"
    sheets.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, Any]] = []
    for index in range(count):
        rng = random.Random(seed + index * 37)
        variant = VARIANTS[index % len(VARIANTS)]
        name = NAMES[index]
        register = f"REG2026C{index + 1:03d}"
        exam_year = 2026 if index % 7 else 2025
        board = (
            "State Board of Examinations"
            if index % 2 == 0
            else "Central Board of Secondary Education"
        )

        subject_names = list(BASE_SUBJECTS)
        if index % 3 == 0:
            subject_names.append(OPTIONAL_SUBJECTS[index % len(OPTIONAL_SUBJECTS)])
        rng.shuffle(subject_names)

        subjects = []
        for subject in subject_names:
            marks = rng.randint(58, 98)
            subjects.append(
                {
                    "subject": subject,
                    "marks": marks,
                    "max_marks": 100,
                    "grade": _grade(marks),
                }
            )

        entered, expected = _entered_marks(subjects, index % 5, rng)
        image = _render_sheet(name, register, exam_year, board, subjects)
        rendered, mime = _apply_variant(image, variant, seed + index)
        suffix = ".jpg" if mime == "image/jpeg" else ".png"
        filename = f"case-{index + 1:02d}-{variant}{suffix}"
        if mime == "image/jpeg":
            rendered.save(sheets / filename, format="JPEG", quality=62)
        else:
            rendered.save(sheets / filename, format="PNG", optimize=True)

        cases.append(
            {
                "id": f"case-{index + 1:02d}",
                "kind": "marksheet_12",
                "class_level": 12,
                "variant": variant,
                "sheet": f"sheets/{filename}",
                "mime": mime,
                "applicant_name": name,
                "register_number": register,
                "exam_year": exam_year,
                "board": board,
                "subjects": subjects,
                "entered": entered,
                "expected": expected,
            }
        )

    for offset in range(class11_count):
        index = count + offset
        rng = random.Random(seed + 1000 + offset * 53)
        variant = VARIANTS[(offset + 1) % len(VARIANTS)]
        name = NAMES[index]
        register = f"REG2025F{offset + 1:03d}"
        exam_year = 2025
        board = (
            "State Board of Examinations"
            if offset % 2 == 0
            else "Central Board of Secondary Education"
        )
        subject_names = list(BASE_SUBJECTS)
        if offset % 3 == 0:
            subject_names.append(OPTIONAL_SUBJECTS[offset % len(OPTIONAL_SUBJECTS)])
        rng.shuffle(subject_names)

        subjects = []
        for subject in subject_names:
            marks = rng.randint(58, 98)
            subjects.append(
                {
                    "subject": subject,
                    "marks": marks,
                    "max_marks": 100,
                    "grade": _grade(marks),
                }
            )

        entered, expected = _entered_marks(subjects, offset % 5, rng)
        image = _render_sheet(
            name,
            register,
            exam_year,
            board,
            subjects,
            class_level=11,
        )
        rendered, mime = _apply_variant(image, variant, seed + 700 + offset)
        suffix = ".jpg" if mime == "image/jpeg" else ".png"
        filename = f"case-{index + 1:02d}-class11-{variant}{suffix}"
        if mime == "image/jpeg":
            rendered.save(sheets / filename, format="JPEG", quality=62)
        else:
            rendered.save(sheets / filename, format="PNG", optimize=True)

        cases.append(
            {
                "id": f"case-{index + 1:02d}",
                "kind": "marksheet_11",
                "class_level": 11,
                "variant": variant,
                "sheet": f"sheets/{filename}",
                "mime": mime,
                "applicant_name": name,
                "register_number": register,
                "exam_year": exam_year,
                "board": board,
                "subjects": subjects,
                "entered": entered,
                "expected": expected,
            }
        )

    documents = _document_fixtures(SYNTHETIC_DIR, seed)
    photos = _photo_fixtures(SYNTHETIC_DIR)
    dataset = {
        "dataset": config["dataset"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "cases": cases,
        "documents": documents,
        "photos": photos,
        "counts": {
            "class_12": count,
            "class_11": class11_count,
            "mark_sheets": len(cases),
            "documents": len(documents),
            "photos": len(photos),
        },
    }
    (SYNTHETIC_DIR / "dataset.json").write_text(
        json.dumps(dataset, indent=2), encoding="utf-8"
    )
    return dataset


def load_dataset() -> dict[str, Any] | None:
    path = SYNTHETIC_DIR / "dataset.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dataset() -> dict[str, Any]:
    dataset = load_dataset()
    if dataset is None:
        dataset = generate_dataset(force=True)
    return dataset
