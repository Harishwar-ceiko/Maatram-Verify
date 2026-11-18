from __future__ import annotations

import re

from PIL import Image

from scripts import seed


SCENARIOS = {
    "all_valid",
    "mark_mismatch",
    "bad_photo",
    "missing_subject",
    "duplicate_upload",
    "income_above_threshold",
    "income_expired",
    "aadhaar_checksum",
    "community_name_mismatch",
    "class_11_name_mismatch",
}


def test_seed_covers_every_demo_scenario_once():
    scenarios = [spec["scenario"] for spec in seed.APPLICATIONS]
    assert len(scenarios) == 10
    assert len(set(scenarios)) == 10
    assert set(scenarios) == SCENARIOS


def test_only_the_all_valid_record_is_left_for_the_live_run():
    pending = [
        spec["scenario"] for spec in seed.APPLICATIONS if not spec.get("validate")
    ]
    assert pending == ["all_valid"]
    assert seed.APPLICATIONS[0]["scenario"] == "all_valid"


def test_seed_attaches_the_document_that_each_scenario_needs():
    by_scenario = {spec["scenario"]: spec for spec in seed.APPLICATIONS}

    assert by_scenario["income_above_threshold"]["supporting"] == [
        {"kind": "income_certificate", "profile": "above_threshold"}
    ]
    assert by_scenario["income_expired"]["supporting"] == [
        {"kind": "income_certificate", "profile": "expired"}
    ]
    assert by_scenario["aadhaar_checksum"]["supporting"] == [
        {"kind": "aadhaar", "profile": "invalid_checksum", "seed": 2601}
    ]
    assert by_scenario["community_name_mismatch"]["supporting"][0]["kind"] == (
        "community_certificate"
    )
    assert by_scenario["community_name_mismatch"]["supporting"][0]["printed_name"] != (
        seed.STUDENTS[1]["full_name"]
    )
    class_11 = by_scenario["class_11_name_mismatch"]["extra_sheets"][0]
    assert class_11["class_level"] == 11
    assert class_11["name"] != seed.STUDENTS[0]["full_name"]


def test_supporting_document_renderer_returns_png_for_each_seed_profile():
    profiles = [
        item
        for spec in seed.APPLICATIONS
        for item in spec.get("supporting", [])
    ]
    assert len(profiles) == 4
    for item in profiles:
        kind, data, filename = seed._supporting_document(item, seed.STUDENTS[0])
        assert kind == item["kind"]
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        assert filename.endswith(".png")
        if item["kind"] == "aadhaar":
            assert re.fullmatch(r"aadhaar-\d{4}\.png", filename)


def test_class_11_sheet_uses_the_conflicting_name_and_class_register(monkeypatch):
    calls: list[tuple[str, str, int, int]] = []

    def fake_render(name, register, exam_year, board, subjects, *, class_level=12):
        calls.append((name, register, exam_year, class_level))
        return Image.new("RGB", (20, 20))

    monkeypatch.setattr(seed, "_render_sheet", fake_render)
    spec = next(
        item for item in seed.APPLICATIONS if item["scenario"] == "class_11_name_mismatch"
    )
    data = seed._sheet_bytes(
        spec,
        seed.STUDENTS[0]["full_name"],
        class_level=11,
        name=spec["extra_sheets"][0]["name"],
    )
    assert data.startswith(b"\x89PNG")
    assert calls == [
        (
            "Ananya Ramanathan",
            spec["class_11"]["register_number"],
            spec["class_11"]["exam_year"],
            11,
        )
    ]
