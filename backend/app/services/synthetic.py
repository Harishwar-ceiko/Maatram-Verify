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

PAPER = (250, 248, 240)
INK = (28, 27, 22)
MUTED = (110, 105, 92)
LINE = (196, 190, 174)
HEADER_FILL = (236, 231, 218)
ACCENT = (166, 58, 27)
WARM = (231, 225, 211)

SHEET_SIZE = (1240, 1754)
VARIANTS = ("clean", "noise", "blur", "rotate", "shadow", "jpeg")

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
) -> Image.Image:
    width, height = SHEET_SIZE
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    margin = 110

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
        f"Higher Secondary Certificate Examination · March {exam_year}",
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


def generate_dataset(force: bool = True) -> dict[str, Any]:
    """Write the synthetic corpus and return its ground truth."""

    config = rules()["evaluation"]
    count = int(config["cases"])
    seed = int(config["seed"])
    if count > len(NAMES):
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

    dataset = {
        "dataset": config["dataset"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "cases": cases,
        "photos": _photo_fixtures(SYNTHETIC_DIR),
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
