from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.services import synthetic
from app.validators.aadhaar import verhoeff_valid


def test_generated_dataset_is_complete_and_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(synthetic, "SYNTHETIC_DIR", tmp_path)
    first = synthetic.generate_dataset(force=True)
    second = synthetic.generate_dataset(force=True)

    assert first["dataset"] == "synthetic-v2"
    assert len(first["cases"]) == 30
    assert len(first["documents"]) == 12
    assert len(first["photos"]) == 11
    assert first["counts"] == {
        "class_12": 24,
        "class_11": 6,
        "mark_sheets": 30,
        "documents": 12,
        "photos": 11,
    }
    assert [case["id"] for case in first["cases"]] == [case["id"] for case in second["cases"]]
    assert [case["subjects"] for case in first["cases"]] == [
        case["subjects"] for case in second["cases"]
    ]
    assert [document["expected"] for document in first["documents"]] == [
        document["expected"] for document in second["documents"]
    ]

    class_11 = [case for case in first["cases"] if case["kind"] == "marksheet_11"]
    assert len(class_11) == 6
    assert all(case["class_level"] == 11 for case in class_11)
    assert all(case["exam_year"] == 2025 for case in class_11)

    for case in first["cases"]:
        sheet = tmp_path / case["sheet"]
        assert sheet.exists() and sheet.stat().st_size > 1024
        assert case["kind"] in {"marksheet_11", "marksheet_12"}
        truth = {row["subject"]: row["marks"] for row in case["subjects"]}
        mismatches = {
            item["subject"]: (item["entered"], item["sheet"])
            for item in case["expected"]["mismatches"]
        }
        for row in case["entered"]:
            if row["subject"] in mismatches:
                entered, sheet_mark = mismatches[row["subject"]]
                assert row["marks"] == entered
                assert truth[row["subject"]] == sheet_mark
                assert entered != sheet_mark
            elif row["subject"] in truth:
                assert row["marks"] == truth[row["subject"]]

    for document in first["documents"]:
        path = tmp_path / document["file"]
        assert path.exists() and path.stat().st_size > 1024
        assert document["kind"] in {
            "aadhaar",
            "income_certificate",
            "community_certificate",
            "first_graduate_certificate",
        }
        assert document["expected"]

    kinds = Counter(document["kind"] for document in first["documents"])
    assert kinds == {
        "aadhaar": 4,
        "income_certificate": 3,
        "community_certificate": 2,
        "first_graduate_certificate": 3,
    }
    aadhaar = [document for document in first["documents"] if document["kind"] == "aadhaar"]
    assert any(document["expected"]["checksum_valid"] is True for document in aadhaar)
    assert any(document["expected"]["checksum_valid"] is False for document in aadhaar)
    for document in aadhaar:
        assert len(document["expected"]["aadhaar_last4"]) == 4
        assert "aadhaar_number" not in document["expected"]

    for photo in first["photos"]:
        path = tmp_path / photo["file"]
        assert path.exists() and path.stat().st_size > 1024

    assert all(case["variant"] in synthetic.VARIANTS for case in first["cases"])


def test_synthetic_aadhaar_numbers_are_verhoeff_checked():
    valid = synthetic.synthetic_aadhaar(2601)
    assert len(valid) == 12
    assert valid[0] in "01"
    assert verhoeff_valid(valid)

    invalid = synthetic.synthetic_aadhaar(2601, valid=False)
    assert len(invalid) == 12
    assert invalid[0] in "01"
    assert invalid != valid
    assert not verhoeff_valid(invalid)


def test_expected_mismatches_are_derived_from_the_sheet_not_the_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(synthetic, "SYNTHETIC_DIR", tmp_path)
    data = synthetic.generate_dataset(force=True)

    mismatch_cases = [case for case in data["cases"] if case["expected"]["mismatches"]]
    assert mismatch_cases, "the corpus must contain injected mismatches"
    for case in mismatch_cases:
        truth = {row["subject"]: row["marks"] for row in case["subjects"]}
        for item in case["expected"]["mismatches"]:
            assert truth[item["subject"]] == item["sheet"]
            assert item["entered"] != item["sheet"]
