from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.review import AuditLog, ReviewItem
from app.models.validation import ValidationRun
from app.services import validation as validation_service
from tests.conftest import TestingSession
from tests.test_validation_api import (
    attach_documents,
    create_application,
    fake_extraction,
    passing_photo,
)


@pytest.fixture(autouse=True)
def _default_photo(monkeypatch):
    monkeypatch.setattr(
        validation_service,
        "analyze_photo",
        lambda data, mime_type=None: passing_photo(),
    )


def _validated_application(client, headers, monkeypatch) -> tuple[int, dict, dict]:
    application_id = create_application(client, headers)
    attach_documents(client, headers, application_id)
    monkeypatch.setattr(
        validation_service,
        "extract_document",
        lambda data, mime, kind=None: fake_extraction(math=88),
    )
    response = client.post(
        f"/api/applications/{application_id}/validate", headers=headers
    )
    assert response.status_code == 202, response.text
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    mark = next(
        mark for mark in detail["extracted_marks"] if mark["subject_raw"] == "Mathematics"
    )
    assert detail["latest_run"]["overall"] == "fail"
    return application_id, detail, mark


def test_correction_is_admin_only_and_needs_a_matching_row(
    client, student_headers, admin_headers, monkeypatch
):
    application_id, _, mark = _validated_application(
        client, student_headers, monkeypatch
    )
    url = f"/api/admin/documents/{mark['document_id']}/marks/{mark['id']}"

    denied = client.patch(
        url,
        json={"marks_obtained": 85, "subject": "Mathematics"},
        headers=student_headers,
    )
    assert denied.status_code == 403

    wrong_document = client.patch(
        f"/api/admin/documents/{mark['document_id'] + 999}/marks/{mark['id']}",
        json={"marks_obtained": 85, "subject": "Mathematics"},
        headers=admin_headers,
    )
    assert wrong_document.status_code == 404
    assert "Document not found" in wrong_document.json()["detail"]

    wrong_mark = client.patch(
        f"/api/admin/documents/{mark['document_id']}/marks/{mark['id'] + 999}",
        json={"marks_obtained": 85, "subject": "Mathematics"},
        headers=admin_headers,
    )
    assert wrong_mark.status_code == 404
    assert "Extracted mark not found" in wrong_mark.json()["detail"]

    detail = client.get(
        f"/api/applications/{application_id}", headers=admin_headers
    ).json()
    assert detail["latest_run"]["overall"] == "fail"
    assert detail["extracted_marks"][0]["corrected_marks"] is None


def test_correction_is_audited_and_the_new_run_clears_the_mismatch(
    client, student_headers, admin_headers, admin, monkeypatch
):
    application_id, _, mark = _validated_application(
        client, student_headers, monkeypatch
    )
    response = client.patch(
        f"/api/admin/documents/{mark['document_id']}/marks/{mark['id']}",
        json={"marks_obtained": 85, "subject": "Mathematics"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mark"]["corrected_marks"] == 85
    assert body["mark"]["corrected_subject"] == "Mathematics"
    assert body["run"]["status"] == "pending"

    detail = client.get(
        f"/api/applications/{application_id}", headers=admin_headers
    ).json()
    assert detail["latest_run"]["overall"] == "pass"
    assert detail["latest_run"]["summary"]["mismatched"] == 0
    assert all(
        finding["result"] != "mismatch"
        for finding in detail["latest_run"]["findings"]
        if finding["category"] == "mark"
    )
    corrected = next(
        row for row in detail["extracted_marks"] if row["subject_raw"] == "Mathematics"
    )
    assert corrected["corrected_marks"] == 85
    assert corrected["corrected_subject"] == "Mathematics"
    assert detail["review"]["status"] == "approved"

    session = TestingSession()
    audit = session.scalars(
        select(AuditLog).where(AuditLog.action == "mark.corrected")
    ).all()
    assert len(audit) == 1
    entry = audit[0]
    assert entry.actor_id == admin["id"]
    assert entry.actor_email == admin["email"]
    assert entry.application_id == application_id
    assert entry.entity_id == mark["id"]
    assert entry.detail["document_id"] == mark["document_id"]
    assert entry.detail["before"]["marks_obtained"] == 88
    assert entry.detail["after"]["marks_obtained"] == 85
    assert entry.detail["after"]["subject"] == "Mathematics"
    review = session.query(ReviewItem).filter_by(application_id=application_id).one()
    assert review.status == "approved"
    session.close()


def test_correction_survives_a_later_validation_run(
    client, student_headers, admin_headers, monkeypatch
):
    application_id, _, mark = _validated_application(
        client, student_headers, monkeypatch
    )
    first = client.patch(
        f"/api/admin/documents/{mark['document_id']}/marks/{mark['id']}",
        json={"marks_obtained": 85, "subject": "Mathematics"},
        headers=admin_headers,
    )
    assert first.status_code == 200, first.text

    rerun = client.post(
        f"/api/applications/{application_id}/validate", headers=student_headers
    )
    assert rerun.status_code == 202, rerun.text

    detail = client.get(f"/api/applications/{application_id}", headers=student_headers).json()
    assert detail["latest_run"]["overall"] == "pass"
    corrected = next(
        row for row in detail["extracted_marks"] if row["subject_raw"] == "Mathematics"
    )
    assert corrected["corrected_marks"] == 85
    assert corrected["corrected_subject"] == "Mathematics"
    assert corrected["marks_obtained"] == 88


def test_correction_is_blocked_while_a_run_is_active(
    client, student_headers, admin_headers, monkeypatch
):
    application_id, _, mark = _validated_application(
        client, student_headers, monkeypatch
    )
    session = TestingSession()
    session.add(ValidationRun(application_id=application_id, status="running"))
    session.commit()
    session.close()

    response = client.patch(
        f"/api/admin/documents/{mark['document_id']}/marks/{mark['id']}",
        json={"marks_obtained": 85, "subject": "Mathematics"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "already running" in response.json()["detail"]

    detail = client.get(f"/api/applications/{application_id}", headers=admin_headers).json()
    corrected = next(
        row for row in detail["extracted_marks"] if row["subject_raw"] == "Mathematics"
    )
    assert corrected["corrected_marks"] is None
