from __future__ import annotations

from datetime import datetime, timezone

import fitz
from sqlalchemy import select

from app.models.review import AuditLog
from app.models.validation import Finding, ValidationRun
from tests.payloads import application_payload
from tests.test_validation_api import make_png

PAYLOAD = application_payload()


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
    assert "Programme" not in text
    assert "Date of birth" in text
    assert "18 Apr 2008" in text
    assert "Father's name" in text
    assert "Ravi Student" in text
    assert "Class 10" in text
    assert "Class 11" in text
    assert "Class 12" in text
    assert "REG2024A014" in text
    assert "REG2026A014" in text

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


def test_report_carries_document_verdicts_type_sections_and_matrix(
    client, student_headers, db
):
    created = client.post("/api/applications", json=PAYLOAD, headers=student_headers).json()
    upload = client.post(
        f"/api/applications/{created['id']}/documents",
        headers=student_headers,
        data={"kind": "marksheet_12"},
        files={"file": ("sheet.png", make_png((1240, 1754)), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document"]["id"]

    run = _run(db, created["id"])
    run.summary = {
        **(run.summary or {}),
        "documents": [
            {
                "id": document_id,
                "kind": "marksheet_12",
                "label": "Class 12 mark sheet",
                "filename": "sheet.png",
                "status": "fail",
                "findings": 2,
                "critical": 1,
                "warnings": 0,
                "classification": {"method": "classifier"},
                "masked_aadhaar": None,
            }
        ],
        "identity_matrix": {
            "fields": [
                {
                    "field": "name",
                    "label": "Name",
                    "status": "mismatch",
                    "detail": "The application name differs from the mark sheet.",
                    "values": [
                        {
                            "source": "Application",
                            "kind": "application",
                            "document_id": None,
                            "filename": None,
                            "value": "Test Student",
                            "status": "application",
                            "similarity": None,
                        },
                        {
                            "source": "Class 12 mark sheet",
                            "kind": "marksheet_12",
                            "document_id": document_id,
                            "filename": "sheet.png",
                            "value": "Test Studant",
                            "status": "mismatch",
                            "similarity": 91.0,
                        },
                    ],
                }
            ],
            "checked": 1,
            "mismatched": 1,
        },
        "consistency_findings": 1,
    }
    db.add(
        Finding(
            run_id=run.id,
            application_id=created["id"],
            category="document",
            field="Aadhaar checksum",
            result="pass",
            severity="info",
            detail="The printed Aadhaar number passes the Verhoeff checksum.",
            sort_order=1,
            meta={
                "kind": "marksheet_12",
                "document_id": document_id,
                "label": "Class 12 mark sheet",
            },
        )
    )
    db.add(
        Finding(
            run_id=run.id,
            application_id=created["id"],
            category="consistency",
            field="Class 10 to Class 11 years",
            result="pass",
            severity="info",
            detail="Expected a gap of one year; the records show one year.",
            sort_order=2,
        )
    )
    db.commit()

    response = client.get(
        f"/api/applications/{created['id']}/report.pdf", headers=student_headers
    )
    assert response.status_code == 200, response.text
    document = fitz.open(stream=response.content, filetype="pdf")
    text = " ".join(" ".join(page.get_text().split()) for page in document)
    document.close()
    assert "Document verdicts" in text
    assert "Class 12 mark sheet" in text
    assert "Validation by document" in text
    assert "Aadhaar checksum" in text
    assert "Identity consistency matrix" in text
    assert "Test Studant" in text
    assert "Consistency checks" in text
    assert "Class 10 to Class 11 years" in text


def test_report_marks_class_11_as_not_provided(client, student_headers, db):
    payload = application_payload(class_11=None)
    created = client.post("/api/applications", json=payload, headers=student_headers).json()
    _run(db, created["id"])

    response = client.get(f"/api/applications/{created['id']}/report.pdf", headers=student_headers)
    assert response.status_code == 200, response.text
    document = fitz.open(stream=response.content, filetype="pdf")
    text = " ".join(
        " ".join(page.get_text().split()) for page in document
    )
    document.close()
    assert "Class 11 Not provided" in text
