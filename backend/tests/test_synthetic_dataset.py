from __future__ import annotations

from pathlib import Path

from app.services import synthetic


def test_generated_dataset_is_complete_and_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(synthetic, "SYNTHETIC_DIR", tmp_path)
    first = synthetic.generate_dataset(force=True)
    second = synthetic.generate_dataset(force=True)

    assert first["dataset"] == "synthetic-v1"
    assert len(first["cases"]) == 24
    assert len(first["photos"]) == 11
    assert [case["id"] for case in first["cases"]] == [case["id"] for case in second["cases"]]
    assert [case["subjects"] for case in first["cases"]] == [
        case["subjects"] for case in second["cases"]
    ]

    for case in first["cases"]:
        sheet = tmp_path / case["sheet"]
        assert sheet.exists() and sheet.stat().st_size > 1024
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

    for photo in first["photos"]:
        path = tmp_path / photo["file"]
        assert path.exists() and path.stat().st_size > 1024

    assert all(case["variant"] in synthetic.VARIANTS for case in first["cases"])


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
