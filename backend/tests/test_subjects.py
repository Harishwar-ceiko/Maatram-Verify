from __future__ import annotations

from app.services.subjects import normalize_subject, same_subject


def test_alias_map_normalises_common_spellings():
    assert normalize_subject("Maths").canonical == "Mathematics"
    assert normalize_subject("MATHEMATICS").canonical == "Mathematics"
    assert normalize_subject("Eng").canonical == "English"
    assert normalize_subject("Computer Applications").canonical == "Computer Science"


def test_fuzzy_match_tolerates_ocr_character_noise():
    match = normalize_subject("Chemlstry")
    assert match.canonical == "Chemistry"
    assert match.known is True
    assert match.score >= 82


def test_unknown_subject_is_kept_not_guessed():
    match = normalize_subject("Astronomy")
    assert match.canonical == "Astronomy"
    assert match.known is False


def test_subjects_match_across_forms():
    assert same_subject("Math", "Mathematics")
    assert same_subject("PHYSICS I", "Physics")
    assert not same_subject("Physics", "Chemistry")
