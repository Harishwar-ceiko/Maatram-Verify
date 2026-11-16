"""Dev fixtures: a clean sample mark sheet and a clearly synthetic portrait.

These are stand-ins for testing the upload and preview screens. The Phase 5
generator builds the noisy evaluation set; nothing here pretends to be a real
student record.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "samples"
OUT.mkdir(exist_ok=True)

INK = (28, 27, 22)
MUTED = (110, 105, 92)
LINE = (196, 190, 174)
PAPER = (250, 248, 240)
ACCENT = (166, 58, 27)

SERIF = "C:/Windows/Fonts/georgia.ttf"
SERIF_BOLD = "C:/Windows/Fonts/georgiab.ttf"
SANS = "C:/Windows/Fonts/arial.ttf"
SANS_BOLD = "C:/Windows/Fonts/arialbd.ttf"
MONO = "C:/Windows/Fonts/consola.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def marksheet() -> None:
    width, height = 1240, 1754
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    margin = 110

    # A hairline frame and a rule, like a printed statement.
    draw.rectangle([margin - 40, margin - 40, width - margin + 40, height - margin + 40], outline=LINE, width=2)
    draw.text((margin, margin), "STATE BOARD OF EXAMINATIONS", font=font(SANS_BOLD, 26), fill=MUTED)
    draw.text((margin, margin + 56), "Statement of Marks", font=font(SERIF, 64), fill=INK)
    draw.line([margin, margin + 150, width - margin, margin + 150], fill=INK, width=2)
    draw.text(
        (margin, margin + 176),
        "Higher Secondary Certificate Examination · March 2026",
        font=font(SANS, 24),
        fill=MUTED,
    )

    fields = [
        ("Candidate", "ANANYA SUBRAMANIAN"),
        ("Register No.", "REG2026A014"),
        ("Examination", "March 2026"),
        ("Board", "State Board of Examinations"),
    ]
    top = margin + 250
    for index, (label, value) in enumerate(fields):
        column = index % 2
        row = index // 2
        x = margin + column * 520
        y = top + row * 74
        draw.text((x, y), label.upper(), font=font(SANS, 17), fill=MUTED)
        draw.text((x, y + 26), value, font=font(SANS_BOLD, 27), fill=INK)

    table_top = top + 190
    columns = [margin, margin + 520, margin + 720, margin + 880, width - margin]
    headers = ["Subject", "Maximum", "Obtained", "Grade"]
    draw.rectangle([margin, table_top, width - margin, table_top + 58], fill=(236, 231, 218))
    for column, header in zip(columns, headers):
        draw.text((column + (0 if header == "Subject" else 8), table_top + 18), header, font=font(SANS_BOLD, 20), fill=INK)
    draw.line([margin, table_top, width - margin, table_top], fill=INK, width=2)
    draw.line([margin, table_top + 58, width - margin, table_top + 58], fill=INK, width=1)

    rows = [
        ("Mathematics", "100", "88", "A"),
        ("English", "100", "92", "A+"),
        ("Physics", "100", "81", "A"),
        ("Chemistry", "100", "79", "B+"),
    ]
    row_height = 74
    for index, row in enumerate(rows):
        y = table_top + 58 + index * row_height
        draw.line([margin, y + row_height, width - margin, y + row_height], fill=LINE, width=1)
        for column, value in zip(columns, row):
            draw.text((column + (0 if column == margin else 8), y + 22), value, font=font(MONO if column != margin else SANS, 26), fill=INK)

    total_y = table_top + 58 + len(rows) * row_height + 20
    draw.text((columns[0], total_y), "Grand total", font=font(SANS_BOLD, 24), fill=INK)
    draw.text((columns[1] + 8, total_y), "400", font=font(MONO, 26), fill=INK)
    draw.text((columns[2] + 8, total_y), "340", font=font(MONO, 26), fill=INK)
    draw.text((columns[3] + 8, total_y), "85.0%", font=font(MONO, 24), fill=ACCENT)

    draw.line([margin, height - 300, width - margin, height - 300], fill=LINE, width=1)
    draw.text((margin, height - 270), "Result: PASS", font=font(SANS_BOLD, 28), fill=INK)
    draw.text(
        (margin, height - 220),
        "This is a synthetic sample generated for the Maatram Verify prototype.",
        font=font(SANS, 19),
        fill=MUTED,
    )
    draw.text((width - margin - 300, height - 150), "Controller of Examinations", font=font(SERIF, 24, ), fill=MUTED)
    draw.line([width - margin - 300, height - 110, width - margin, height - 110], fill=LINE, width=1)

    image.save(OUT / "marksheet-reg2026a014.png", optimize=True)
    print(f"wrote {OUT / 'marksheet-reg2026a014.png'}")


def portrait() -> None:
    width, height = 600, 800
    image = Image.new("RGB", (width, height), (228, 222, 208))
    draw = ImageDraw.Draw(image)

    # Warm studio backdrop, deliberately flat and graphic so nobody mistakes
    # it for a photograph of a real person.
    draw.rectangle([0, 0, width, height], fill=(231, 225, 211))
    draw.ellipse([90, 40, 510, 460], fill=(214, 207, 190))
    draw.rectangle([0, 560, width, height], fill=(166, 58, 27))

    # Head and shoulders in ink.
    draw.ellipse([205, 150, 395, 380], fill=(53, 47, 38))
    draw.pieslice([40, 430, 560, 980], start=180, end=360, fill=(53, 47, 38))
    draw.ellipse([245, 330, 355, 390], fill=(231, 225, 211))

    # Collar and a quiet registration mark.
    draw.polygon([(250, 380), (300, 450), (350, 380)], fill=(247, 244, 235))
    draw.rectangle([40, 40, 88, 46], fill=(166, 58, 27))
    draw.rectangle([40, 40, 46, 88], fill=(166, 58, 27))

    image.save(OUT / "photo-ananya.png", optimize=True)
    print(f"wrote {OUT / 'photo-ananya.png'}")


if __name__ == "__main__":
    marksheet()
    portrait()
