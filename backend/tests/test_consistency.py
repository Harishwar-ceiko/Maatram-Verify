from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.consistency import (
    SourceRecord,
    build_identity_matrix,
    class_year_checks,
    subject_group_checks,
)

APPLICATION = SimpleNamespace(
    applicant_name="Test Student",
    date_of_birth=date(2008, 4, 18),
    father_name="Ravi Student",
    address="12, Gandhi Street, Chennai 600028",
)


def record(level: int, year: int, subjects: tuple[str, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        class_level=level,
        exam_year=year,
        marks=[SimpleNamespace(subject=subject) for subject in subjects],
    )


def source(**overrides) -> SourceRecord:
    values = {
        "source": "Aadhaar",
        "kind": "aadhaar",
        "document_id": 1,
        "filename": "aadhaar.png",
        "name": "Test Student",
        "date_of_birth": "2008-04-18",
        "father_name": None,
        "address": "12, Gandhi Street, Chennai 600028",
    }
    values.update(overrides)
    return SourceRecord(**values)


def test_matrix_records_each_source_and_matches_the_application():
    matrix = build_identity_matrix(
        APPLICATION,
        [
            source(),
            source(
                source="Community certificate",
                kind="community_certificate",
                document_id=2,
                father_name="Ravi Student",
                address=None,
            ),
        ],
    )

    fields = {row["field"]: row for row in matrix["fields"]}
    assert set(fields) == {"name", "date_of_birth", "father_name", "address"}
    assert fields["name"]["status"] == "match"
    assert [value["source"] for value in fields["name"]["values"]] == [
        "Application",
        "Aadhaar",
        "Community certificate",
    ]
    assert fields["date_of_birth"]["status"] == "match"
    assert fields["father_name"]["status"] == "match"
    assert fields["address"]["status"] == "match"
    assert matrix["checked"] == 4
    assert matrix["mismatched"] == 0


def test_matrix_flags_a_mismatched_father_name_and_address():
    matrix = build_identity_matrix(
        APPLICATION,
        [
            source(
                source="Income certificate",
                kind="income_certificate",
                father_name="Suresh Kumar",
                address="99, Some Other Road, Madurai 625001",
            )
        ],
    )

    fields = {row["field"]: row for row in matrix["fields"]}
    assert fields["father_name"]["status"] == "mismatch"
    assert fields["address"]["status"] == "mismatch"
    assert matrix["mismatched"] == 2
    assert "differs from the application" in fields["father_name"]["detail"]


def test_matrix_accepts_a_year_of_birth_and_reports_missing_fields():
    matrix = build_identity_matrix(
        APPLICATION,
        [source(date_of_birth=None, year_of_birth=2008, address=None)],
    )

    fields = {row["field"]: row for row in matrix["fields"]}
    assert fields["date_of_birth"]["status"] == "match"
    assert fields["date_of_birth"]["values"][1]["value"] == "2008"
    assert fields["address"]["status"] == "not_available"
    assert matrix["checked"] == 2


def test_matrix_without_sources_reports_every_field_unavailable():
    matrix = build_identity_matrix(APPLICATION, [])
    assert matrix["checked"] == 0
    assert matrix["mismatched"] == 0
    assert {row["status"] for row in matrix["fields"]} == {"not_available"}


def test_class_years_pass_for_a_normal_progression():
    checks = class_year_checks(
        {10: record(10, 2024), 11: record(11, 2025), 12: record(12, 2026)}
    )
    assert len(checks) == 2
    assert {check.result for check in checks} == {"pass"}
    assert [check.field for check in checks] == [
        "Class 10 to Class 11 years",
        "Class 11 to Class 12 years",
    ]


def test_class_years_flag_out_of_order_records_as_critical():
    checks = class_year_checks({10: record(10, 2026), 12: record(12, 2024)})
    assert len(checks) == 1
    check = checks[0]
    assert check.result == "mismatch"
    assert check.severity == "critical"
    assert "out of order" in (check.detail or "")


def test_class_years_flag_an_impossible_gap_as_fail():
    checks = class_year_checks({10: record(10, 2015), 12: record(12, 2026)})
    assert len(checks) == 1
    assert checks[0].result == "fail"
    assert checks[0].severity == "critical"
    assert checks[0].difference == 8


def test_class_years_warn_when_the_gap_is_allowed_but_unexpected():
    checks = class_year_checks({10: record(10, 2023), 12: record(12, 2026)})
    assert len(checks) == 1
    assert checks[0].result == "pending"
    assert checks[0].severity == "warning"


def test_subject_groups_pass_with_a_single_extra_elective():
    checks = subject_group_checks(
        {
            11: record(
                11,
                2025,
                ("Mathematics", "English", "Physics", "Chemistry", "Computer Science"),
            ),
            12: record(
                12,
                2026,
                ("Mathematics", "English", "Physics", "Chemistry"),
            ),
        }
    )
    assert len(checks) == 1
    assert checks[0].result == "pass"
    assert checks[0].meta["overlap"] == 75.0


def test_subject_groups_warn_on_a_stream_change():
    checks = subject_group_checks(
        {
            11: record(11, 2025, ("History", "Geography", "Economics")),
            12: record(12, 2026, ("Mathematics", "Physics", "Chemistry")),
        }
    )
    assert len(checks) == 1
    assert checks[0].result == "pending"
    assert checks[0].severity == "warning"
    assert "stream change" in (checks[0].detail or "")


def test_subject_groups_ignore_shared_language_subjects():
    checks = subject_group_checks(
        {
            11: record(11, 2025, ("Mathematics", "Physics", "English", "Tamil")),
            12: record(12, 2026, ("Mathematics", "Physics", "English", "Tamil")),
        }
    )
    assert len(checks) == 1
    assert checks[0].result == "pass"


def test_subject_groups_are_skipped_without_both_classes():
    assert subject_group_checks({11: record(11, 2025, ("Mathematics",))}) == []
