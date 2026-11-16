from __future__ import annotations

from datetime import datetime, timezone

import fitz
from sqlalchemy import select

from app.models.review import AuditLog
from app.models.validation import Finding, ValidationRun

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


def _run(db, application_id: int, status: str = "completed") -> ValidationRun:
    now = datetime.now(timezone.utc)
    run = ValidationRun(
        application_id=application_id,
        status=status,
        overall="fail" if status == "completed" else None,
        summary={
            "verdict": "1 mark differs from the mark sheet. Sent to the review queue.",
            "matched": 1,
            "mismatched": 1,
            "critical": 1,
            "warnings": 0,
            "engine": "tesseract",
            "ocr_confidence": 91.4,
        },
        started_at=now,
        finished_at=now if status == "completed" else None,
    )
    db.add(run)
    db.flush()
    db.add(
        Finding(
            run_id=run.id,
            application_id=application_id,
            category="mark",
            field="Mathematics",
            subject_norm="Mathematics",
            result="mismatch",
            entered_value="92",
            uploaded_value="90",
            measured_value="90",
            required_value="92",
            difference=2.0,
            detail="Entered 92 but the sheet reads 90 (difference +2).",
            severity="critical",
            confidence=91.2,
            sort_order=0,
        )
    )
    db.commit()
    db.refresh(run)
    return run


def test_report_needs_a_completed_run(client, student_headers, db):
    created = client.post("/api/applications", json=PAYLOAD, headers=student_headers).json()

    missing = client.get(f"/api/applications/{created['id']}/report.pdf", headers=student_headers)
    assert missing.status_code == 409
    assert "Run the checks" in missing.json()["detail"]

    _run(db, created["id"], status="running")
    running = client.get(f"/api/applications/{created['id']}/report.pdf", headers=student_headers)
    assert running.status_code == 409


def test_report_belongs_to_the_student(client, student_headers, other_headers):
    created = client.post("/api/applications", json=PAYLOAD, headers=student_headers).json()

    response = client.get(
        f"/api/applications/{created['id']}/report.pdf", headers=other_headers
    )
    assert response.status_code == 403


def test_report_pdf_carries_stored_results_and_audit(client, student_headers, db):
    created = client.post("/api/applications", json=PAYLOAD, headers=student_headers).json()
    run = _run(db, created["id"])

    response = client.get(f"/api/applications/{created['id']}/report.pdf", headers=student_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert (
        f'attachment; filename="{created["reference"]}-validation.pdf"'
        in response.headers["content-disposition"]
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content.startswith(b"%PDF-")

    document = fitz.open(stream=response.content, filetype="pdf")
    assert document.page_count >= 1
    text = "\n".join(page.get_text() for page in document)
    document.close()
    flat = " ".join(text.split())
    assert created["reference"] in text
    assert "Test Student" in text
    assert "Mathematics" in text
    assert "Entered 92 but the sheet reads 90 (difference +2)." in text
    assert f"Run #{run.id}" in text
    assert "No generative model is used at any stage." in flat

    audit = db.scalars(
        select(AuditLog).where(AuditLog.action == "report.downloaded")
    ).all()
    assert len(audit) == 1
    assert audit[0].application_id == created["id"]
    assert audit[0].detail["run_id"] == run.id
    assert audit[0].detail["bytes"] == len(response.content)


def test_admin_can_download_any_report(client, student_headers, admin_headers, db):
    created = client.post("/api/applications", json=PAYLOAD, headers=student_headers).json()
    _run(db, created["id"])

    response = client.get(f"/api/applications/{created['id']}/report.pdf", headers=admin_headers)
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
