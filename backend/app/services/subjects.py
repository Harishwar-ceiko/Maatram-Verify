from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz, process

from app.core.config import rules


@dataclass(frozen=True, slots=True)
class SubjectMatch:
    canonical: str
    known: bool
    score: float
    matched_on: str | None = None


def clean(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("&", " and ")
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return " ".join(text.casefold().split())


def display(value: str) -> str:
    return " ".join((value or "").split()).strip(" .:-")


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    config = rules()["subjects"]
    lookup: dict[str, str] = {}
    for canonical, alternatives in config["aliases"].items():
        lookup[clean(canonical)] = canonical
        for alternative in alternatives:
            lookup[clean(alternative)] = canonical
    for canonical in config["required"]:
        lookup.setdefault(clean(canonical), canonical)
    return lookup


def normalize_subject(raw: str) -> SubjectMatch:
    """Map a printed or typed subject to its canonical name.

    Exact aliases win. Anything else goes through rapidfuzz WRatio, which
    tolerates OCR truncation like "Chemlstry" without accepting a different
    subject. Below the threshold the cleaned original is kept, never guessed.
    """

    config = rules()["subjects"]
    cleaned = clean(raw)
    if not cleaned:
        return SubjectMatch(canonical=display(raw), known=False, score=0.0)

    lookup = _aliases()
    if cleaned in lookup:
        return SubjectMatch(canonical=lookup[cleaned], known=True, score=100.0, matched_on=cleaned)

    threshold = float(config["fuzzy_threshold"])
    result = process.extractOne(cleaned, list(lookup.keys()), scorer=fuzz.WRatio)
    if result is not None:
        matched, score, _ = result
        if score >= threshold:
            return SubjectMatch(
                canonical=lookup[matched],
                known=True,
                score=round(float(score), 1),
                matched_on=matched,
            )

    title = display(raw)
    if title.isupper():
        title = title.title()
    return SubjectMatch(
        canonical=title,
        known=False,
        score=round(float(result[1]), 1) if result else 0.0,
        matched_on=result[0] if result else None,
    )


def same_subject(left: str, right: str) -> bool:
    a = normalize_subject(left)
    b = normalize_subject(right)
    if clean(a.canonical) == clean(b.canonical):
        return True
    threshold = float(rules()["subjects"]["fuzzy_threshold"])
    return fuzz.WRatio(clean(left), clean(right)) >= threshold


def canonical_required() -> list[str]:
    return list(rules()["subjects"]["required"])
