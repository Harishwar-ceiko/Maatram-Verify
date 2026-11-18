"""Extractors for the supporting document kinds.

Every extractor reads printed text and positioned words only. The output keeps
display-safe values in ``attributes``; anything secret goes in ``sensitive`` and
is never serialised. Missing values stay missing: nothing is guessed.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Sequence

from app.ocr.types import Extraction, Field, OcrPage
from app.validators.aadhaar import (
    best_candidate,
    compare_qr,
    mask_number,
    verhoeff_valid,
)

MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

DATE_FORMATS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d-%b-%Y",
    "%d %B, %Y",
    "%d %b, %Y",
)

COMPANY_LABELS = ("father", "mother", "guardian", "spouse")
CERTIFICATE_TITLES = (
    "income certificate",
    "annual income certificate",
    "income and asset certificate",
    "community certificate",
    "caste certificate",
    "first graduate certificate",
    "certificate of income",
)
CERTIFICATE_NUMBER_LABELS = (
    "certificate no",
    "certificate number",
    "serial no",
    "sl no",
    "reference no",
    "reg no",
)
FATHER_LABELS = ("father's name", "father name", "father")
ADDRESS_LABELS = ("residential address", "permanent address", "address")


def _clean(value: str | None) -> str:
    return " ".join((value or "").replace("\u00a0", " ").split()).strip(" .,:;-/|")


def _lines(raw_text: str) -> list[str]:
    return [line.strip() for line in (raw_text or "").splitlines() if line.strip()]


def _label_value(
    raw_text: str,
    labels: Sequence[str],
    *,
    skip: Sequence[str] = (),
    max_next: int = 2,
) -> tuple[str | None, float]:
    """Find a label and return its inline value or the next line.

    This is deliberately line-oriented: certificates print labels and values in
    predictable rows, and reading a neighbouring line is safer than inventing a
    relationship from a bag of words.
    """

    lines = _lines(raw_text)
    lowered_skip = [item.casefold() for item in skip]
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if any(token in lowered for token in lowered_skip):
            continue
        for label in labels:
            escaped = re.escape(label.casefold())
            match = re.search(
                rf"(?:^|[^a-z0-9]){escaped}\b\s*[:\-]?\s*(.*)$",
                lowered,
                flags=re.IGNORECASE,
            )
            if match is None:
                continue
            # Use the original line for the returned value so casing survives.
            original = re.search(
                rf"(?:^|[^A-Za-z0-9]){re.escape(label)}\b\s*[:\-]?\s*(.*)$",
                line,
                flags=re.IGNORECASE,
            )
            rest = _clean(original.group(1) if original else "")
            rest = re.split(
                r"\b(?:date|dob|gender|address|aadhaar|vid|certificate|community|category|income|father|mother)\b",
                rest,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            rest = _clean(rest)
            if rest:
                return rest, 1.0
            for offset in range(1, max_next + 1):
                if index + offset >= len(lines):
                    break
                following = _clean(lines[index + offset])
                if following and not following.endswith(":"):
                    return following, 0.75
    return None, 0.0


def parse_date_text(value: str | None) -> date | None:
    if not value:
        return None
    text = _clean(value)
    numeric = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", text)
    if numeric:
        day, month, year = (int(part) for part in numeric.groups())
        try:
            return date(year, month, day)
        except ValueError:
            pass
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.search(
        rf"\b(\d{{1,2}})\s+({'|'.join(MONTHS)}|{'|'.join(month[:3] for month in MONTHS)})\.?,?\s+(\d{{4}})\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(
                    f"{match.group(1)} {match.group(2)} {match.group(3)}", fmt
                ).date()
            except ValueError:
                continue
    return None


def _date_matches(text: str) -> list[date]:
    found: list[date] = []
    for pattern in (
        r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b",
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
        r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}\b",
    ):
        for match in re.finditer(pattern, text or ""):
            parsed = parse_date_text(match.group(0))
            if parsed and parsed not in found:
                found.append(parsed)
    return found


def parse_amount(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace(",", "")
    match = re.search(r"(?<![\d.])(\d+(?:\.\d{1,2})?)(?![\d])", text)
    if not match:
        return None
    amount = float(match.group(1))
    lower = text.casefold()
    if "crore" in lower:
        amount *= 10000000
    elif "lakh" in lower or "lac" in lower:
        amount *= 100000
    if amount < 0 or amount > 100000000:
        return None
    return amount


def _display_amount(value: float | None) -> str | None:
    if value is None:
        return None
    return f"INR {value:,.0f}"


def _extraction(
    pages: Sequence[OcrPage],
    *,
    kind: str,
    raw_text: str,
    name: Field,
    attributes: dict[str, Any],
    warnings: list[str],
    engine: str = "",
) -> Extraction:
    return Extraction(
        pages=list(pages),
        name=name,
        raw_text=raw_text,
        kind=kind,
        attributes=attributes,
        warnings=warnings,
        engine=engine,
    )


def extract_aadhaar(
    pages: Sequence[OcrPage],
    raw_text: str,
    qr_payloads: Sequence[str] = (),
) -> Extraction:
    flattened = re.sub(r"\s+", " ", raw_text or "")
    number, checksum_valid = best_candidate(flattened)
    name_value, name_confidence = _label_value(
        raw_text,
        ("name",),
        skip=COMPANY_LABELS,
    )
    name = Field(value=name_value, confidence=round(name_confidence * 80, 1), page=1)

    dob_text, dob_confidence = _label_value(
        raw_text, ("date of birth", "dob", "d.o.b")
    )
    year_text, year_confidence = _label_value(
        raw_text, ("year of birth", "yob", "birth year")
    )
    gender_text, gender_confidence = _label_value(
        raw_text, ("gender", "sex")
    )
    address_text, _ = _label_value(raw_text, ("address",), max_next=3)

    extracted_dob = parse_date_text(dob_text)
    extracted_year = None
    if year_text:
        year_match = re.search(r"\b(19|20)\d{2}\b", year_text)
        if year_match:
            extracted_year = int(year_match.group(0))
            year_text = str(extracted_year)
    if extracted_dob is not None:
        dob_text = extracted_dob.isoformat()
    if extracted_dob is None:
        extracted_dob = None

    warnings: list[str] = []
    if number is None:
        warnings.append("The Aadhaar number could not be read.")
    else:
        masked = mask_number(number) or "XXXX XXXX XXXX"
        if not checksum_valid:
            warnings.append(
                f"The printed Aadhaar number {masked} failed the Verhoeff checksum."
            )
    if not name_value:
        warnings.append("The name could not be located on the Aadhaar.")
    if extracted_dob is None and extracted_year is None:
        warnings.append("Neither a date of birth nor a year of birth could be read.")

    qr = compare_qr(list(qr_payloads), number)
    if qr["status"] == "not_detected":
        warnings.append("No readable QR code was found on the Aadhaar.")
    elif qr["status"] == "unreadable":
        warnings.append("A QR code was found but its payload could not be read.")
    elif qr["status"] == "mismatch":
        warnings.append(
            f"The QR code ({qr.get('masked') or 'unreadable'}) does not match the "
            f"printed number ({mask_number(number) or 'unreadable'})."
        )

    attributes: dict[str, Any] = {
        "aadhaar_number": mask_number(number),
        "name": name_value,
        "birth_detail": (
            extracted_dob.isoformat()
            if extracted_dob is not None
            else (str(extracted_year) if extracted_year is not None else None)
        ),
        "date_of_birth": extracted_dob.isoformat() if extracted_dob is not None else None,
        "year_of_birth": extracted_year,
        "gender": _clean(gender_text).title() if gender_text else None,
        "address": _clean(address_text) if address_text else None,
        "qr_status": qr["status"],
        "qr_last4": qr.get("last4"),
        "checksum_valid": checksum_valid,
    }
    extraction = _extraction(
        pages,
        kind="aadhaar",
        raw_text=raw_text,
        name=name,
        attributes=attributes,
        warnings=warnings,
    )
    extraction.sensitive = {
        "aadhaar_number": number,
        "checksum_valid": checksum_valid,
        "qr_status": qr["status"],
        "qr_last4": qr.get("last4"),
    }
    extraction.qr_payloads = list(qr_payloads)
    return extraction


def _certificate_base(
    pages: Sequence[OcrPage],
    raw_text: str,
    kind: str,
    *,
    date_labels: Sequence[str],
) -> tuple[Field, dict[str, Any], list[str]]:
    name_value, name_confidence = _label_value(
        raw_text, ("name",), skip=COMPANY_LABELS
    )
    name = Field(value=name_value, confidence=round(name_confidence * 80, 1), page=1)
    number_value, number_confidence = _label_value(
        raw_text,
        CERTIFICATE_NUMBER_LABELS,
        skip=CERTIFICATE_TITLES,
    )
    if not number_value:
        # Some certificates print only "Certificate: ABC-123". Require the
        # colon so the heading "INCOME CERTIFICATE" is never read as a value.
        fallback = re.search(
            r"(?im)^\s*certificate\s*(?:no\.?|number)?\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9/\-]*)",
            raw_text or "",
        )
        if fallback:
            number_value = _clean(fallback.group(1))
            number_confidence = 0.65
    issue_value, issue_confidence = _label_value(raw_text, date_labels)
    issue_date = parse_date_text(issue_value)
    if issue_date is None:
        for line in _lines(raw_text):
            if re.search(r"\b(?:issue|issued)\b", line, flags=re.IGNORECASE):
                dates = _date_matches(line)
                if dates:
                    issue_date = dates[0]
                    break
    father_value, father_confidence = _label_value(raw_text, FATHER_LABELS)
    address_value, address_confidence = _label_value(
        raw_text, ADDRESS_LABELS, max_next=3
    )
    attributes: dict[str, Any] = {
        "name": name_value,
        "certificate_number": number_value,
        "certificate_number_confidence": round(number_confidence * 80, 1),
        "issue_date": issue_date.isoformat() if issue_date else None,
        "issue_date_confidence": round(issue_confidence * 80, 1),
        "father_name": _clean(father_value) or None,
        "father_name_confidence": round(father_confidence * 80, 1),
        "address": _clean(address_value) or None,
        "address_confidence": round(address_confidence * 80, 1),
    }
    warnings: list[str] = []
    if not name_value:
        warnings.append(f"The name could not be located on the {kind.replace('_', ' ')}.")
    if not number_value:
        warnings.append("The certificate number could not be located.")
    if issue_date is None:
        warnings.append("The issue date could not be read.")
    return name, attributes, warnings


def extract_income(pages: Sequence[OcrPage], raw_text: str) -> Extraction:
    name, attributes, warnings = _certificate_base(
        pages,
        raw_text,
        "income_certificate",
        date_labels=("date of issue", "issue date", "issued on", "issued"),
    )
    amount_text, amount_confidence = _label_value(
        raw_text,
        (
            "annual income",
            "family annual income",
            "total annual income",
            "family income",
            "income",
        ),
        skip=CERTIFICATE_TITLES,
    )
    amount = parse_amount(amount_text)
    if amount is None:
        # The amount is often printed on the next row without repeating the
        # label. Search the whole text only when it carries a currency marker.
        for line in _lines(raw_text):
            if re.search(r"(?:rs\.?|inr|₹)", line, flags=re.IGNORECASE):
                amount = parse_amount(line)
                if amount is not None:
                    amount_confidence = 0.5
                    break
    attributes["annual_income"] = amount
    attributes["annual_income_display"] = _display_amount(amount)
    attributes["annual_income_confidence"] = round(amount_confidence * 80, 1)
    if amount is None:
        warnings.append("The annual income amount could not be read.")
    return _extraction(
        pages,
        kind="income_certificate",
        raw_text=raw_text,
        name=name,
        attributes=attributes,
        warnings=warnings,
    )


def extract_community(pages: Sequence[OcrPage], raw_text: str) -> Extraction:
    name, attributes, warnings = _certificate_base(
        pages,
        raw_text,
        "community_certificate",
        date_labels=("date of issue", "issue date", "issued on", "issued"),
    )
    community_value, community_confidence = _label_value(
        raw_text,
        ("community", "caste", "category"),
        skip=CERTIFICATE_TITLES,
    )
    attributes["community"] = _clean(community_value).upper() if community_value else None
    attributes["community_confidence"] = round(community_confidence * 80, 1)
    if not community_value:
        warnings.append("The community could not be read.")
    return _extraction(
        pages,
        kind="community_certificate",
        raw_text=raw_text,
        name=name,
        attributes=attributes,
        warnings=warnings,
    )


def extract_first_graduate(pages: Sequence[OcrPage], raw_text: str) -> Extraction:
    name, attributes, warnings = _certificate_base(
        pages,
        raw_text,
        "first_graduate_certificate",
        date_labels=("date of issue", "issue date", "issued on", "issued"),
    )
    lowered = (raw_text or "").casefold()
    if re.search(r"\bnot\s+(?:a\s+)?first\s+graduate\b", lowered):
        status = "no"
    elif re.search(r"\bfirst\s+graduate\b", lowered):
        status = "yes"
    else:
        status = None
    attributes["first_graduate"] = status
    if status is None:
        warnings.append("The certificate does not state that the applicant is a first graduate.")
    return _extraction(
        pages,
        kind="first_graduate_certificate",
        raw_text=raw_text,
        name=name,
        attributes=attributes,
        warnings=warnings,
    )
