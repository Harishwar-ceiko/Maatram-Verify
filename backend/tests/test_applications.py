from __future__ import annotations

from datetime import datetime, timezone

from app.models.validation import ValidationRun

PAYLOAD = {
    "program": "B.Sc. Computer Science",
    "applicant_name": "Test Student",
    "register_number": "reg2026a014",
    "exam_year": 2026,
    "board": "State Board",
    "marks": [
        {"subject": "Mathematics", "marks_obtained": 92, "max_marks": 100},
        {"subject": "English", "marks_obtained": 88, "max_marks": 100},
    ],
}


def test_student_creates_application(client, student_headers):
    response = client.post("/api/applications", json=PAYLOAD, headers=student_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["reference"].startswith("MH26-")
    assert body["register_number"] == "REG2026A014"
    assert len(body["marks"]) == 2
    assert body["status"] == "submitted"


def test_invalid_marks_are_rejected(client, student_headers):
    bad = {**PAYLOAD, "marks": [{"subject": "Maths", "marks_obtained": -3}]}
    response = client.post("/api/applications", json=bad, headers=student_headers)
    assert response.status_code == 422


def test_duplicate_subjects_are_rejected(client, student_headers):
    bad = {
        **PAYLOAD,
        "marks": [
            {"subject": "Maths", "marks_obtained": 80},
            {"subject": "maths", "marks_obtained": 81},
        ],
    }
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


def test_meta_config_exposes_one_rule_source(client, student_headers):
    response = client.get("/api/meta/config", headers=student_headers)
    assert response.status_code == 200
    body = response.json()
    assert "Mathematics" in body["subjects"]["required"]
    assert body["photo"]["min_width"] == 300
