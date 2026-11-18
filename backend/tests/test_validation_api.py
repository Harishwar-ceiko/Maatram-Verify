from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from app.models.enums import ReviewStatus
from app.models.review import ReviewItem
from app.ocr.types import Extraction, Field, OcrPage, SubjectRow
from app.services import validation as validation_service
from app.validators.photo import PhotoAnalysis, PhotoCheckResult
from tests.conftest import TestingSession
from tests.payloads import application_payload

PAYLOAD = application_payload()


def make_png(
    size: tuple[int, int], colour=(246, 243, 235), pattern: str = "lines"
) -> bytes:
    image = Image.new("RGB", size, colour)
    draw = ImageDraw.Draw(image)
    if pattern == "lines":
        step = max(12, size[1] // 14)
        for y in range(0, size[1], step):
            draw.rectangle([0, y, size[0], y + step // 2], fill=(36, 34, 28))
    else:
        step = max(12, size[0] // 12)
        for x in range(0, size[0], step):
            draw.rectangle([x, 0, x + step // 2, size[1]], fill=(120, 96, 74))
        draw.ellipse(
            [size[0] // 4, size[1] // 5, size[0] * 3 // 4, size[1] * 4 // 5],
            fill=(206, 182, 156),
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def create_application(client, headers, payload=PAYLOAD) -> int:
    response = client.post("/api/applications", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def attach_documents(client, headers, application_id: int) -> None:
    marksheet = client.post(
        f"/api/applications/{application_id}/documents",
        headers=headers,
        data={"kind": "marksheet"},
        files={"file": ("sheet.png", make_png((1240, 1754)), "image/png")},
    )
    assert marksheet.status_code == 201, marksheet.text
    photo = client.post(
        f"/api/applications/{application_id}/documents",
        headers=headers,
        data={"kind": "photo"},
        files={"file": ("portrait.png", make_png((360, 480), (190, 170, 150), "portrait"), "image/png")},
    )
    assert photo.status_code == 201, photo.text


def passing_photo() -> PhotoAnalysis:
    return PhotoAnalysis(
        checks=[
            PhotoCheckResult(
                "Resolution",
                True,
                "info",
                "600 × 800 px",
                "300–6000 × 400–8000 px",
                "Within the accepted pixel range.",
            ),
            PhotoCheckResult(
                "Face",
                True,
                "info",
                "1 face · 30% of the short side",
                "at least 8% of the short side",
                "One clear frontal face was detected.",
            ),
        ],
        metrics={"width": 600, "height": 800, "faces": 1, "brightness": 151.0},
    )


def failing_photo() -> PhotoAnalysis:
    return PhotoAnalysis(
        checks=[
            PhotoCheckResult(
                "Brightness",
                False,
                "critical",
                "18 / 255",
                "55–215",
                "The photograph is too dark to verify.",
            ),
            PhotoCheckResult(
                "Face",
                False,
                "warning",
                "0 faces",
                "one frontal face",
                "No frontal face was detected.",
            ),
            PhotoCheckResult(
                "Resolution",
                True,
                "info",
                "600 × 800 px",
                "300–6000 × 400–8000 px",
                "Within the accepted pixel range.",
            ),
        ],
        metrics={"width": 600, "height": 800, "faces": 0, "brightness": 18.0},
    )


@pytest.fixture(autouse=True)
def _default_photo(monkeypatch):
    monkeypatch.setattr(
        validation_service,
        "analyze_photo",
        lambda data, mime_type=None: passing_photo(),
    )


def fake_extraction(*, math=88, include_physics=True) -> Extraction:
    subjects = [
        SubjectRow("Mathematics", math, 100, "A", 95.0, 1),
        SubjectRow("English", 92, 100, "A+", 94.0, 1),
        SubjectRow("Chemistry", 79, 100, "B+", 93.0, 1),
    ]
    if include_physics:
        subjects.insert(2, SubjectRow("Physics", 81, 100, "A", 94.0, 1))
    extraction = Extraction(
        pages=[OcrPage(number=1, width=1240, height=1754, words=[], text="")],
        name=Field(value="Test Student", confidence=95.0, page=1),
        register_number=Field(value="REG2026A014", confidence=94.0, page=1),
        exam_year=Field(value=2026, confidence=90.0, page=1),
        subjects=subjects,
        raw_text="synthetic test page",
        engine="tesseract",
        duration_ms=12,
    )
    return extraction


def test_validate_requires_both_documents(client, student_headers):
    application_id = create_application(client, student_headers)
    response = client.post(f"/api/applications/{application_id}/validate", headers=student_headers)
    assert response.status_code == 422
    assert "mark sheet" in response.json()["detail"]


def test_validate_requires_photo(client, student_headers):
    application_id = create_application(client, student_headers)
    marksheet = client.post(
        f"/api/applications/{application_id}/documents",
        headers=student_headers,
        data={"kind": "marksheet"},
        files={"file": ("sheet.png", make_png((1240, 1754)), "image/png")},
    )
    assert marksheet.status_code == 201
    response = client.post(f"/api/applications/{application_id}/validate", headers=student_headers)
    assert response.status_code == 422
    assert "photograph" in response.json()["detail"]


def test_validation_records_mismatch_missing_subject_and_review(
    client, student_headers, monkeypatch
):
    application_id = create_application(client, student_headers)
    attach_documents(client, student_headers, application_id)
    monkeypatch.setattr(
        validation_service,
        "extract_document",
        lambda data, mime, kind=None: fake_extraction(math=88, include_physics=False),
    )

    response = client.post(f"/api/applications/{application_id}/validate", headers=student_headers)
    assert response.status_code == 202, response.text

    detail = client.get(f"/api/applications/{application_id}", headers=student_headers).json()
    assert detail["status"] == "needs_review"
    run = detail["latest_run"]
    assert run["status"] == "completed"
    assert run["overall"] == "fail"
    assert run["summary"]["mismatched"] == 1
    assert run["summary"]["missing"] == 1
    assert run["summary"]["documents_read"] == 1
    assert run["summary"]["verdict"] == (
        "1 mark differs from the mark sheet and Physics is missing from the mark sheet. "
        "Sent to the review queue."
    )

    marks = [finding for finding in run["findings"] if finding["category"] == "mark"]
    mathematics = next(finding for finding in marks if finding["field"] == "Mathematics")
    assert mathematics["result"] == "mismatch"
    assert mathematics["entered_value"] == "85"
    assert mathematics["uploaded_value"] == "88"
    assert mathematics["difference"] == 3
    physics = [finding for finding in marks if finding["field"] == "Physics"]
    assert physics and physics[0]["result"] == "missing_upload"
    missing = [
        finding
        for finding in run["findings"]
        if finding["result"] == "missing_upload"
        and finding["category"] in ("mark", "completeness")
    ]
    assert len(missing) == 1

    identity = [finding for finding in run["findings"] if finding["category"] == "identity"]
    assert all(finding["result"] == "match" for finding in identity)

    assert len(detail["extracted_marks"]) == 3
    assert {mark["subject_norm"] for mark in detail["extracted_marks"]} == {
        "Mathematics",
        "English",
        "Chemistry",
    }

    session = TestingSession()
    review = session.query(ReviewItem).filter_by(application_id=application_id).one()
    assert review.status == ReviewStatus.open.value
    assert review.priority == 20
    assert any("Mathematics" in reason for reason in review.reasons)
    session.close()


def test_passing_run_verifies_application(client, student_headers, monkeypatch):
    application_id = create_application(client, student_headers)
    attach_documents(client, student_headers, application_id)
    monkeypatch.setattr(
        validation_service,
        "extract_document",
        lambda data, mime, kind=None: fake_extraction(math=85),
    )

    response = client.post(f"/api/applications/{application_id}/validate", headers=student_headers)
    assert response.status_code == 202, response.text
    detail = client.get(f"/api/applications/{application_id}", headers=student_headers).json()
    assert detail["status"] == "verified"
    assert detail["latest_run"]["overall"] == "pass"
    assert detail["latest_run"]["summary"]["critical"] == 0
    assert detail["latest_run"]["summary"]["verdict"] == (
        "All checks passed. 4 subjects match the mark sheet and identity details are consistent."
    )
    assert len(detail["latest_run"]["findings"]) == 12
    consistency = [
        finding
        for finding in detail["latest_run"]["findings"]
        if finding["category"] == "consistency"
    ]
    assert {finding["field"] for finding in consistency} == {
        "Class 10 to Class 11 years",
        "Class 11 to Class 12 years",
        "Class 11 and 12 subject group",
    }
    assert {finding["result"] for finding in consistency} == {"pass"}
    assert detail["latest_run"]["summary"]["identity_matrix"]["mismatched"] == 0
    photo = [
        finding for finding in detail["latest_run"]["findings"] if finding["category"] == "photo"
    ]
    assert {finding["result"] for finding in photo} == {"pass"}
    assert detail["latest_run"]["summary"]["photo_failures"] == 0
    assert detail["latest_run"]["summary"]["photo_metrics"][0]["faces"] == 1

    session = TestingSession()
    assert (
        session.query(ReviewItem).filter_by(application_id=application_id).count() == 0
    )
    session.close()


def test_photo_failures_reach_the_report(client, student_headers, monkeypatch):
    application_id = create_application(client, student_headers)
    attach_documents(client, student_headers, application_id)
    monkeypatch.setattr(
        validation_service,
        "extract_document",
        lambda data, mime, kind=None: fake_extraction(math=85),
    )
    monkeypatch.setattr(
        validation_service,
        "analyze_photo",
        lambda data, mime_type=None: failing_photo(),
    )

    response = client.post(f"/api/applications/{application_id}/validate", headers=student_headers)
    assert response.status_code == 202, response.text
    detail = client.get(f"/api/applications/{application_id}", headers=student_headers).json()
    run = detail["latest_run"]
    assert detail["status"] == "needs_review"
    assert run["overall"] == "fail"
    assert run["summary"]["critical"] == 1
    assert run["summary"]["warnings"] == 1
    assert run["summary"]["verdict"] == (
        "The photograph failed the brightness check. Sent to the review queue. "
        "1 warning also noted."
    )
    assert run["summary"]["photo_failures"] == 1
    assert run["summary"]["photo_warnings"] == 1
    assert run["summary"]["photo_metrics"][0]["brightness"] == 18.0

    photo = [finding for finding in run["findings"] if finding["category"] == "photo"]
    brightness = next(finding for finding in photo if finding["field"] == "Brightness")
    assert brightness["result"] == "fail"
    assert brightness["measured_value"] == "18 / 255"
    assert brightness["required_value"] == "55–215"
    face = next(finding for finding in photo if finding["field"] == "Face")
    assert face["result"] == "fail"


def test_consistency_flags_reach_the_review_reasons_and_queue(
    client, student_headers, admin_headers, monkeypatch
):
    payload = application_payload()
    payload["class_11"]["exam_year"] = 2027
    payload["class_11"]["marks"] = [
        {"subject": "History", "marks_obtained": 88, "max_marks": 100},
        {"subject": "Geography", "marks_obtained": 86, "max_marks": 100},
        {"subject": "Economics", "marks_obtained": 84, "max_marks": 100},
    ]
    application_id = create_application(client, student_headers, payload)
    attach_documents(client, student_headers, application_id)
    monkeypatch.setattr(
        validation_service,
        "extract_document",
        lambda data, mime, kind=None: fake_extraction(math=85),
    )

    response = client.post(
        f"/api/applications/{application_id}/validate", headers=student_headers
    )
    assert response.status_code == 202, response.text
    detail = client.get(
        f"/api/applications/{application_id}", headers=admin_headers
    ).json()
    assert detail["status"] == "needs_review"
    consistency = [
        finding
        for finding in detail["latest_run"]["findings"]
        if finding["category"] == "consistency"
    ]
    assert any(
        finding["field"] == "Class 11 to Class 12 years"
        and finding["result"] == "mismatch"
        for finding in consistency
    )
    assert any(
        finding["field"] == "Class 11 and 12 subject group"
        and finding["result"] == "pending"
        for finding in consistency
    )
    reasons = detail["review"]["reasons"]
    assert any("Class 11 to Class 12 years" in reason for reason in reasons)
    assert any("Class 11 and 12 subject group" in reason for reason in reasons)

    queue = client.get("/api/admin/reviews", headers=admin_headers).json()
    item = next(
        entry for entry in queue["items"] if entry["application_id"] == application_id
    )
    assert any("Class 11 to Class 12 years" in reason for reason in item["reasons"])
    assert any("Class 11 and 12 subject group" in reason for reason in item["reasons"])


def test_second_run_is_rejected_while_one_is_active(client, student_headers):
    application_id = create_application(client, student_headers)
    attach_documents(client, student_headers, application_id)

    session = TestingSession()
    from app.models.validation import ValidationRun

    session.add(ValidationRun(application_id=application_id, status="running"))
    session.commit()
    session.close()

    response = client.post(f"/api/applications/{application_id}/validate", headers=student_headers)
    assert response.status_code == 409
    assert "already running" in response.json()["detail"]
