from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.application import Application
from app.models.review import AuditLog, ReviewItem
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


def _file(client, headers) -> dict:
    return client.post("/api/applications", json=PAYLOAD, headers=headers).json()


def _review(
    db,
    application_id: int,
    status: str = "open",
    priority: int = 20,
    reasons: list[str] | None = None,
) -> ReviewItem:
    run = ValidationRun(
        application_id=application_id,
        status="completed",
        overall="fail",
        summary={
            "verdict": "1 mark differs from the mark sheet.",
            "matched": 1,
            "mismatched": 1,
            "critical": 1,
            "warnings": 0,
            "engine": "tesseract",
            "ocr_confidence": 91.4,
        },
        finished_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()
    item = ReviewItem(
        application_id=application_id,
        run_id=run.id,
        status=status,
        priority=priority,
        reasons=reasons or ["Entered 92 but the sheet reads 90."],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_review_queue_is_admin_only(client, student_headers, db):
    created = _file(client, student_headers)
    _review(db, created["id"])

    assert client.get("/api/admin/reviews", headers=student_headers).status_code == 403
    assert (
        client.post(
            "/api/admin/reviews/1/approve",
            json={"comment": "Checked against the original."},
            headers=student_headers,
        ).status_code
        == 403
    )


def test_queue_lists_active_items_with_counts(client, student_headers, admin_headers, db):
    first = _file(client, student_headers)
    second = _file(client, student_headers)
    third = _file(client, student_headers)
    open_item = _review(db, first["id"], priority=20, reasons=["Mathematics 92 vs 90."])
    _review(db, second["id"], status="approved", priority=50)
    _review(db, third["id"], status="rejected", priority=50)

    body = client.get("/api/admin/reviews", headers=admin_headers).json()
    assert body["total"] == 1
    assert body["counts"]["open"] == 1
    assert body["counts"]["active"] == 1
    assert body["counts"]["approved"] == 1
    assert body["counts"]["rejected"] == 1
    assert body["counts"]["all"] == 3
    item = body["items"][0]
    assert item["id"] == open_item.id
    assert item["reference"] == first["reference"]
    assert item["priority"] == 20
    assert item["reasons"] == ["Mathematics 92 vs 90."]
    assert item["overall"] == "fail"
    assert item["matched"] == 1 and item["mismatched"] == 1
    assert item["application_status"] == "submitted"

    approved = client.get(
        "/api/admin/reviews?status=approved", headers=admin_headers
    ).json()
    assert approved["total"] == 1
    assert approved["items"][0]["status"] == "approved"
    assert approved["items"][0]["application_id"] == second["id"]


def test_approve_review_records_decision_and_audit(
    client, student_headers, admin_headers, admin, db
):
    created = _file(client, student_headers)
    item = _review(db, created["id"])

    response = client.post(
        f"/api/admin/reviews/{item.id}/approve",
        json={"comment": "Original sheet checked; the entered mark is correct."},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["application_status"] == "approved"
    assert body["decided_by_email"] == admin["email"]

    db.expire_all()
    stored = db.get(ReviewItem, item.id)
    assert stored.status == "approved"
    assert stored.decided_by == admin["id"]
    assert stored.assigned_to == admin["id"]
    assert stored.decided_at is not None
    assert stored.decision_comment == "Original sheet checked; the entered mark is correct."
    assert db.get(Application, created["id"]).status == "approved"

    audit = db.scalars(
        select(AuditLog).where(AuditLog.action == "review.approved")
    ).all()
    assert len(audit) == 1
    assert audit[0].actor_email == admin["email"]
    assert audit[0].application_id == created["id"]
    assert audit[0].detail["comment"] == "Original sheet checked; the entered mark is correct."

    admin_view = client.get(f"/api/applications/{created['id']}", headers=admin_headers).json()
    assert admin_view["review"]["status"] == "approved"
    assert admin_view["review"]["decided_by_email"] == admin["email"]
    student_view = client.get(f"/api/applications/{created['id']}", headers=student_headers).json()
    assert student_view["review"] is None

    audit_page = client.get(
        f"/api/admin/audit?application_id={created['id']}", headers=admin_headers
    ).json()
    assert any(entry["action"] == "review.approved" for entry in audit_page["items"])


def test_reject_review_sets_application_rejected(client, student_headers, admin_headers, db):
    created = _file(client, student_headers)
    item = _review(db, created["id"])

    response = client.post(
        f"/api/admin/reviews/{item.id}/reject",
        json={"comment": "The sheet does not match the entered subject."},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"

    db.expire_all()
    assert db.get(ReviewItem, item.id).status == "rejected"
    assert db.get(Application, created["id"]).status == "rejected"
    actions = [
        row.action
        for row in db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
    ]
    assert "review.rejected" in actions


def test_review_cannot_be_decided_twice(client, student_headers, admin_headers, db):
    created = _file(client, student_headers)
    item = _review(db, created["id"], status="approved")

    response = client.post(
        f"/api/admin/reviews/{item.id}/approve",
        json={"comment": "Second decision attempt."},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "already decided" in response.json()["detail"]


def test_review_decision_needs_a_real_comment(client, student_headers, admin_headers, db):
    created = _file(client, student_headers)
    item = _review(db, created["id"])

    response = client.post(
        f"/api/admin/reviews/{item.id}/approve",
        json={"comment": "  a  "},
        headers=admin_headers,
    )
    assert response.status_code == 422

    target = client.post(
        "/api/admin/reviews/9999/approve",
        json={"comment": "Reviewed against the original."},
        headers=admin_headers,
    )
    assert target.status_code == 404
