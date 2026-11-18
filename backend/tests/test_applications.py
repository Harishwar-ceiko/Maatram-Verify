from __future__ import annotations

from datetime import datetime, timezone

from app.models.validation import ValidationRun
from tests.payloads import application_payload

PAYLOAD = application_payload()


def test_student_creates_application(client, student_headers):
    response = client.post("/api/applications", json=PAYLOAD, headers=student_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["reference"].startswith("MH26-")
    assert body["applicant_name"] == "Test Student"
    assert body["date_of_birth"] == "2008-04-18"
    assert body["father_name"] == "Ravi Student"
    assert body["mother_name"] == "Lakshmi Student"
    assert body["is_orphan"] is False
    assert body["is_first_graduate"] is True
    assert body["status"] == "submitted"
    assert "program" not in body
    assert [record["class_level"] for record in body["education"]] == [10, 11, 12]
    class_12 = next(record for record in body["education"] if record["class_level"] == 12)
    assert class_12["register_number"] == "REG2026A014"
    assert len(class_12["marks"]) == 4
    assert [record["class_level"] for record in body["classes"]] == [10, 11, 12]


def test_class_11_is_optional_and_serialises_as_not_provided(client, student_headers):
    payload = application_payload()
    payload.pop("class_11")
    response = client.post("/api/applications", json=payload, headers=student_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert [record["class_level"] for record in body["education"]] == [10, 12]
    assert [record["class_level"] for record in body["classes"]] == [10, 12]

    null_payload = application_payload(class_11=None)
    null_response = client.post("/api/applications", json=null_payload, headers=student_headers)
    assert null_response.status_code == 201, null_response.text
    assert [
        record["class_level"] for record in null_response.json()["education"]
    ] == [10, 12]


def test_class_10_and_class_12_are_required(client, student_headers):
    missing_ten = application_payload()
    missing_ten.pop("class_10")
    assert (
        client.post("/api/applications", json=missing_ten, headers=student_headers).status_code
        == 422
    )

    missing_twelve = application_payload()
    missing_twelve.pop("class_12")
    assert (
        client.post(
            "/api/applications", json=missing_twelve, headers=student_headers
        ).status_code
        == 422
    )


def test_invalid_marks_are_rejected(client, student_headers):
    bad = application_payload()
    bad["class_12"]["marks"] = [{"subject": "Maths", "marks_obtained": -3}]
    response = client.post("/api/applications", json=bad, headers=student_headers)
    assert response.status_code == 422


def test_duplicate_subjects_are_rejected_within_a_class(client, student_headers):
    bad = application_payload()
    bad["class_10"]["marks"] = [
        {"subject": "Maths", "marks_obtained": 80},
        {"subject": "maths", "marks_obtained": 81},
    ]
    response = client.post("/api/applications", json=bad, headers=student_headers)
    assert response.status_code == 422


def test_future_date_of_birth_is_rejected(client, student_headers):
    bad = application_payload(date_of_birth="2099-01-01")
    response = client.post("/api/applications", json=bad, headers=student_headers)
    assert response.status_code == 422


def test_students_only_see_their_own(client, student_headers, other_headers):
    created = client.post("/api/applications", json=PAYLOAD, headers=student_headers).json()
    response = client.get(f"/api/applications/{created['id']}", headers=other_headers)
    assert response.status_code == 403
    listing = client.get("/api/applications", headers=other_headers).json()
    assert listing["total"] == 0


def test_admin_sees_all(client, student_headers, admin_headers):
    client.post("/api/applications", json=PAYLOAD, headers=student_headers)
    response = client.get("/api/applications", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_finds_a_class_register_number(client, student_headers):
    client.post("/api/applications", json=PAYLOAD, headers=student_headers)
    response = client.get(
        "/api/applications", params={"q": "REG2024A014"}, headers=student_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    missed = client.get(
        "/api/applications", params={"q": "B.Sc. Computer Science"}, headers=student_headers
    )
    assert missed.json()["total"] == 0


def test_student_cannot_open_admin_area(client, student_headers):
    response = client.get("/api/admin/overview", headers=student_headers)
    assert response.status_code == 403


def test_admin_overview(client, student_headers, admin_headers):
    client.post("/api/applications", json=PAYLOAD, headers=student_headers)
    response = client.get("/api/admin/overview", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_applications"] == 1
    assert body["by_status"]["submitted"] == 1


def test_admin_overview_streams_recent_validation_activity(
    client, student_headers, admin_headers, db
):
    created = client.post("/api/applications", json=PAYLOAD, headers=student_headers).json()
    caption = "Every check passed. 2 subjects match the mark sheet."
    db.add(
        ValidationRun(
            application_id=created["id"],
            status="completed",
            overall="pass",
            summary={
                "verdict": caption,
                "matched": 2,
                "mismatched": 0,
                "critical": 0,
                "warnings": 0,
                "engine": "tesseract",
                "ocr_confidence": 91.4,
            },
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    body = client.get("/api/admin/overview", headers=admin_headers).json()
    assert body["generated_at"]
    assert len(body["activity"]) == 1
    entry = body["activity"][0]
    assert entry["application_id"] == created["id"]
    assert entry["reference"] == created["reference"]
    assert entry["overall"] == "pass"
    assert entry["matched"] == 2
    assert entry["ocr_confidence"] == 91.4
    assert entry["verdict"] == caption
    assert entry["class_12_year"] == 2026
    assert "program" not in entry


def test_meta_config_exposes_one_rule_source(client, student_headers):
    response = client.get("/api/meta/config", headers=student_headers)
    assert response.status_code == 200
    body = response.json()
    assert "Mathematics" in body["subjects"]["required"]
    assert body["subjects"]["by_class"]["10"] == [
        "Mathematics",
        "Science",
        "Social Science",
        "English",
        "Tamil",
    ]
    assert body["photo"]["min_width"] == 300
