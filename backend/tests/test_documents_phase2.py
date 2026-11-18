from __future__ import annotations

import io
import json
from datetime import date, timedelta

import fitz
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.api.routes import documents as documents_route
from app.core.security import decrypt_text
from app.models.document import AadhaarRecord, OcrResult
from app.models.review import AuditLog
from app.ocr import extract as extract_module
from app.ocr.classify import classify_pages, classify_text
from app.ocr.document_fields import (
    extract_aadhaar,
    extract_community,
    extract_first_graduate,
    extract_income,
)
from app.ocr.types import Extraction, Field, OcrPage, SubjectRow
from app.services import validation as validation_service
from app.validators.aadhaar import (
    best_candidate,
    compare_qr,
    dob_comparison,
    mask_number,
    redact_filename,
    redact_text,
    verhoeff_checksum_digit,
    verhoeff_valid,
)
from app.validators.photo import PhotoAnalysis, PhotoCheckResult
from tests.conftest import TestingSession
from tests.payloads import application_payload

PAYLOAD = application_payload()


_PNG_SEED = 0


def make_png(
    size: tuple[int, int] = (640, 480),
    colour=(246, 243, 235),
    pattern: str = "sheet",
) -> bytes:
    global _PNG_SEED
    _PNG_SEED += 1
    seed = _PNG_SEED
    width, height = size
    image = Image.new("RGB", size, colour)
    draw = ImageDraw.Draw(image)
    if pattern == "portrait":
        for x in range(0, width, max(18, width // (6 + seed % 6))):
            draw.rectangle(
                [x, 0, x + max(4, width // 22), height],
                fill=(70 + seed * 13 % 120, 80, 90),
            )
        draw.ellipse(
            [width // 4, height // 5, width * 3 // 4, height * 4 // 5],
            fill=(206, 182, 156),
        )
    elif pattern == "diagonal":
        step = max(16, width // (7 + seed % 5))
        for x in range(-height, width + step, step):
            draw.line([(x, 0), (x + height, height)], fill=(36, 34, 28), width=max(2, step // 8))
        for x in range(-height, width + step, step * 2):
            draw.line([(x, height), (x + height, 0)], fill=(150, 120, 90), width=max(1, step // 12))
    elif pattern == "blocks":
        step = max(20, width // (8 + seed % 4))
        for y in range((seed * 5) % step, height, step * 2):
            for x in range((seed * 3) % step, width, step * 2):
                draw.rectangle(
                    [x, y, x + step, y + step],
                    fill=(40 + seed % 80, 60, 90),
                )
    else:
        step = max(18, height // (8 + seed % 5))
        for y in range((seed * 7) % step, height, step):
            draw.rectangle([0, y, width, y + max(3, step // 3)], fill=(36, 34, 28))
        for x in range((seed * 11) % width, width, max(25, width // (5 + seed % 4))):
            draw.rectangle(
                [x, 0, x + max(2, width // 30), height],
                fill=(120, 96, 74),
            )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def synthetic_aadhaar(seed: str = "01234567890") -> str:
    assert len(seed) == 11 and seed[0] in "01"
    return seed + verhoeff_checksum_digit(seed)


def page(text: str = "") -> OcrPage:
    return OcrPage(number=1, width=1240, height=1754, words=[], text=text)


# ---------------------------------------------------------------------------
# Aadhaar rules
# ---------------------------------------------------------------------------


def test_verhoeff_accepts_a_generated_number_and_rejects_a_changed_digit():
    number = synthetic_aadhaar()
    assert verhoeff_valid(number)
    assert not verhoeff_valid(number[:-1] + str((int(number[-1]) + 1) % 10))
    assert not verhoeff_valid("0123")
    assert not verhoeff_valid("abcdefghijkl")


def test_best_candidate_prefers_a_valid_number():
    valid = synthetic_aadhaar("10234567890")
    invalid = valid[:-1] + str((int(valid[-1]) + 1) % 10)
    number, checksum = best_candidate(f"printed {invalid} then {valid}")
    assert number == valid
    assert checksum is True
    number, checksum = best_candidate(f"printed {invalid}")
    assert number == invalid
    assert checksum is False


def test_masking_and_redaction_never_keep_a_full_number():
    number = synthetic_aadhaar()
    masked = mask_number(number)
    assert masked == f"XXXX XXXX {number[-4:]}"
    assert number not in redact_text(f"Aadhaar {number} was scanned")
    assert number not in redact_text(f"Aadhaar {number[:4]} {number[4:8]} {number[8:]} was scanned")
    assert number not in redact_filename(f"aadhaar-{number}.png")
    assert number[-4:] in redact_filename(f"aadhaar-{number}.png")


def test_qr_comparison_reports_match_mismatch_and_missing():
    number = synthetic_aadhaar()
    other = synthetic_aadhaar("11234567890")
    matched = compare_qr([f"uid={number}"], number)
    assert matched["status"] == "match"
    assert matched["masked"] == mask_number(number)
    assert matched["last4"] == number[-4:]
    assert compare_qr([f"uid={other}"], number)["status"] == "mismatch"
    assert compare_qr([], number)["status"] == "not_detected"
    assert compare_qr(["not a number"], number)["status"] == "unreadable"


def test_dob_comparison_handles_exact_and_year_only_values():
    exact = dob_comparison(date(2008, 4, 18), date(2008, 4, 18), None)
    assert exact and exact["matched"] is True
    different = dob_comparison(date(2008, 4, 18), date(2008, 4, 19), None)
    assert different and different["matched"] is False
    year = dob_comparison(date(2008, 4, 18), None, 2008)
    assert year and year["matched"] is True
    assert dob_comparison(None, None, None) is None


# ---------------------------------------------------------------------------
# Deterministic classifier
# ---------------------------------------------------------------------------


def test_classifier_separates_the_three_mark_sheet_classes():
    class_10 = classify_text(
        "SECONDARY SCHOOL LEAVING CERTIFICATE\n"
        "Mathematics 94\nScience 91\nSocial Science 88\nEnglish 90\nTamil 86\nMarks"
    )
    class_11 = classify_text(
        "HIGHER SECONDARY FIRST YEAR\n"
        "Mathematics 88\nEnglish 90\nPhysics 85\nChemistry 84\nMarks"
    )
    class_12 = classify_text(
        "HIGHER SECONDARY CERTIFICATE\nSecond Year\n"
        "Mathematics 85\nEnglish 92\nPhysics 81\nChemistry 79\nMarks"
    )
    assert class_10 and class_10["kind"] == "marksheet_10"
    assert class_11 and class_11["kind"] == "marksheet_11"
    assert class_12 and class_12["kind"] == "marksheet_12"
    assert all(item["method"] == "keyword" for item in (class_10, class_11, class_12))


def test_classifier_defaults_an_ambiguous_sheet_to_class_12_with_a_note():
    result = classify_text("FIRST YEAR\nSECOND YEAR\nMathematics 80\nMarks")
    assert result is not None
    assert result["kind"] == "marksheet_12"
    assert result["ambiguous"] is True
    assert result["note"] and "Class 12" in result["note"]


def test_classifier_recognises_supporting_documents():
    aadhaar = classify_text(
        "GOVERNMENT OF INDIA\nUNIQUE IDENTIFICATION AUTHORITY OF INDIA\n"
        "Aadhaar\nName: Test Student\nYear of Birth: 2008\nGender: Male\nAddress: Chennai"
    )
    income = classify_text(
        "INCOME CERTIFICATE\nCertificate No: INC-1\n"
        "Annual Income: Rs. 2,00,000\nDate of Issue: 01/06/2026\nRevenue Department"
    )
    community = classify_text(
        "COMMUNITY CERTIFICATE\nCommunity: BC\nDate of Issue: 01/06/2026\nRevenue Department"
    )
    graduate = classify_text(
        "FIRST GRADUATE CERTIFICATE\nName: Test Student\nFather's Name: Ravi Student\n"
        "This certifies that the applicant is a first graduate."
    )
    assert aadhaar and aadhaar["kind"] == "aadhaar"
    assert income and income["kind"] == "income_certificate"
    assert community and community["kind"] == "community_certificate"
    assert graduate and graduate["kind"] == "first_graduate_certificate"


def test_classifier_returns_none_for_unrelated_text():
    assert classify_text("A short note about the weather in Chennai.") is None


def test_classifier_falls_back_to_a_portrait_face_heuristic(monkeypatch):
    monkeypatch.setattr("app.validators.photo.detect_faces", lambda image, config: [1])
    result = classify_pages([], [Image.new("RGB", (400, 500), (200, 180, 160))])
    assert result and result["kind"] == "photo"
    assert result["method"] == "image_heuristic"


# ---------------------------------------------------------------------------
# Supporting-document extractors
# ---------------------------------------------------------------------------


def test_aadhaar_extractor_masks_the_number_and_compares_the_qr():
    number = synthetic_aadhaar()
    text = (
        "GOVERNMENT OF INDIA\nAADHAAR\nName: Test Student\n"
        "Date of Birth: 18/04/2008\nGender: Male\n"
        "Address: 12, Gandhi Street, Chennai 600028\n"
        f"{number[:4]} {number[4:8]} {number[8:]}"
    )
    extraction = extract_aadhaar([page(text)], text, [f"uid={number}"])
    assert extraction.kind == "aadhaar"
    assert extraction.name.value == "Test Student"
    assert extraction.attributes["aadhaar_number"] == mask_number(number)
    assert extraction.attributes["date_of_birth"] == "2008-04-18"
    assert extraction.attributes["birth_detail"] == "2008-04-18"
    assert extraction.attributes["qr_status"] == "match"
    assert extraction.attributes["checksum_valid"] is True
    assert extraction.sensitive["aadhaar_number"] == number
    assert number not in json.dumps(extraction.attributes)
    assert not extraction.warnings


def test_aadhaar_extractor_flags_a_bad_checksum_without_printing_the_number():
    valid = synthetic_aadhaar()
    invalid = valid[:-1] + str((int(valid[-1]) + 1) % 10)
    text = f"AADHAAR\nName: Test Student\nDate of Birth: 18/04/2008\n{invalid}"
    extraction = extract_aadhaar([page(text)], text, [f"uid={invalid}"])
    assert extraction.attributes["checksum_valid"] is False
    assert any("Verhoeff" in warning for warning in extraction.warnings)
    warnings = " ".join(extraction.warnings)
    assert invalid not in warnings
    assert mask_number(invalid) in warnings


def test_aadhaar_extractor_flags_a_qr_mismatch():
    number = synthetic_aadhaar()
    other = synthetic_aadhaar("11234567890")
    text = f"AADHAAR\nName: Test Student\nDate of Birth: 18/04/2008\n{number}"
    extraction = extract_aadhaar([page(text)], text, [f"uid={other}"])
    assert extraction.attributes["qr_status"] == "mismatch"
    assert any("does not match" in warning for warning in extraction.warnings)
    assert number not in " ".join(extraction.warnings)


def test_income_extractor_reads_number_amount_date_and_father():
    text = (
        "INCOME CERTIFICATE\n"
        "Certificate No: INC-2026-001\n"
        "Name: Test Student\n"
        "Father's Name: Ravi Student\n"
        "Annual Income: Rs. 3,20,000\n"
        "Date of Issue: 01/06/2026\n"
        "Revenue Department"
    )
    extraction = extract_income([page(text)], text)
    assert extraction.name.value == "Test Student"
    assert extraction.attributes["certificate_number"] == "INC-2026-001"
    assert extraction.attributes["annual_income"] == 320000.0
    assert extraction.attributes["annual_income_display"] == "INR 320,000"
    assert extraction.attributes["issue_date"] == "2026-06-01"
    assert extraction.attributes["father_name"] == "Ravi Student"
    assert not extraction.warnings


def test_community_extractor_ignores_the_document_title():
    text = (
        "COMMUNITY CERTIFICATE\n"
        "Certificate No: COM-2026-001\n"
        "Name: Test Student\n"
        "Community: BC\n"
        "Date of Issue: 01/06/2026"
    )
    extraction = extract_community([page(text)], text)
    assert extraction.attributes["community"] == "BC"
    assert extraction.attributes["certificate_number"] == "COM-2026-001"
    assert extraction.attributes["issue_date"] == "2026-06-01"
    assert not extraction.warnings


def test_first_graduate_extractor_reads_status_and_rejects_the_negative():
    positive = (
        "FIRST GRADUATE CERTIFICATE\n"
        "Certificate No: FG-1\n"
        "Name: Test Student\n"
        "Date of Issue: 01/06/2026\n"
        "This certifies that the applicant is a first graduate."
    )
    negative = positive.replace("is a first graduate", "is not a first graduate")
    assert extract_first_graduate([page(positive)], positive).attributes["first_graduate"] == "yes"
    assert extract_first_graduate([page(negative)], negative).attributes["first_graduate"] == "no"


def test_extract_document_redacts_aadhaar_from_ocr_text_and_warnings(monkeypatch):
    number = synthetic_aadhaar()

    class FakeEngine:
        name = "fake"

        def extract(self, images):
            return [
                page(
                    "AADHAAR\nName: Test Student\nDate of Birth: 18/04/2008\n"
                    f"{number}"
                )
            ]

    monkeypatch.setattr(
        extract_module,
        "render_document",
        lambda data, mime_type, dpi=300: [Image.new("RGB", (200, 200))],
    )
    monkeypatch.setattr(extract_module, "get_engine", lambda: FakeEngine())
    monkeypatch.setattr(extract_module, "decode_qr", lambda images: [])

    extraction = extract_module.extract_document(b"not-used", "image/png", "aadhaar")
    assert extraction.kind == "aadhaar"
    assert extraction.engine == "fake"
    assert number not in extraction.raw_text
    assert number not in " ".join(extraction.warnings)
    assert extraction.attributes["aadhaar_number"] == mask_number(number)


# ---------------------------------------------------------------------------
# Upload classification, slots and masking
# ---------------------------------------------------------------------------


def create_application(client, headers) -> int:
    response = client.post("/api/applications", json=PAYLOAD, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(
    client,
    headers,
    application_id: int,
    kind: str,
    name: str = "document.png",
    data: bytes | None = None,
):
    return client.post(
        f"/api/applications/{application_id}/documents",
        headers=headers,
        data={"kind": kind},
        files={"file": (name, data or make_png(), "image/png")},
    )


def test_auto_upload_uses_the_classifier_and_records_its_evidence(
    client, student_headers, monkeypatch
):
    application_id = create_application(client, student_headers)
    monkeypatch.setattr(
        documents_route,
        "classify_document",
        lambda data, mime: {
            "kind": "marksheet_11",
            "method": "keyword",
            "score": 9,
            "scores": {"marksheet_11": 9, "marksheet_12": 4},
            "signals": ["higher secondary first year", "physics"],
            "confidence": 69.0,
            "ambiguous": False,
            "note": None,
        },
    )
    response = upload(client, student_headers, application_id, "auto", "sheet.png")
    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["kind"] == "marksheet_11"
    assert document["kind_label"] == "Class 11 mark sheet"
    assert document["classification"]["method"] == "keyword"
    assert document["classification"]["requested"] == "auto"

    session = TestingSession()
    audit = session.scalars(
        select(AuditLog).where(AuditLog.action == "document.uploaded")
    ).one()
    assert audit.detail["kind"] == "marksheet_11"
    assert audit.detail["requested_kind"] == "auto"
    assert audit.detail["classification"]["method"] == "keyword"
    session.close()


def test_auto_upload_rejects_unidentified_content(client, student_headers, monkeypatch):
    application_id = create_application(client, student_headers)
    monkeypatch.setattr(documents_route, "classify_document", lambda data, mime: None)
    response = upload(client, student_headers, application_id, "auto")
    assert response.status_code == 422
    assert "could not be identified" in response.json()["detail"]


def test_student_override_wins_over_the_classifier(client, student_headers, monkeypatch):
    application_id = create_application(client, student_headers)
    monkeypatch.setattr(
        documents_route,
        "classify_document",
        lambda data, mime: {"kind": "marksheet_12", "method": "keyword"},
    )
    response = upload(client, student_headers, application_id, "marksheet_10")
    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["kind"] == "marksheet_10"
    assert document["classification"]["method"] == "override"
    assert document["classification"]["requested"] == "marksheet_10"


def test_legacy_marksheet_kind_still_means_class_12(client, student_headers):
    application_id = create_application(client, student_headers)
    response = upload(client, student_headers, application_id, "marksheet", "sheet.png")
    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["kind"] == "marksheet_12"
    assert document["kind_label"] == "Class 12 mark sheet"
    assert document["classification"]["legacy_alias"] is True


def test_single_slot_replaces_a_supporting_document(client, student_headers):
    application_id = create_application(client, student_headers)
    first = upload(
        client,
        student_headers,
        application_id,
        "income_certificate",
        "first.png",
        make_png(colour=(240, 230, 210)),
    )
    second = upload(
        client,
        student_headers,
        application_id,
        "income_certificate",
        "second.png",
        make_png(colour=(210, 230, 240)),
    )
    assert first.status_code == 201 and second.status_code == 201
    detail = client.get(f"/api/applications/{application_id}", headers=student_headers).json()
    certificates = [
        document
        for document in detail["documents"]
        if document["kind"] == "income_certificate"
    ]
    assert len(certificates) == 1
    assert certificates[0]["original_filename"] == "second.png"


def test_aadhaar_filename_is_masked_before_storage(client, student_headers):
    application_id = create_application(client, student_headers)
    number = synthetic_aadhaar()
    response = upload(
        client,
        student_headers,
        application_id,
        "aadhaar",
        f"aadhaar-{number}.png",
    )
    assert response.status_code == 201, response.text
    filename = response.json()["document"]["original_filename"]
    assert number not in filename
    assert number[-4:] in filename


# ---------------------------------------------------------------------------
# Validation with Aadhaar and supporting documents
# ---------------------------------------------------------------------------


def fake_mark_sheet() -> Extraction:
    return Extraction(
        pages=[page("synthetic mark sheet")],
        name=Field(value="Test Student", confidence=95.0, page=1),
        register_number=Field(value="REG2026A014", confidence=94.0, page=1),
        exam_year=Field(value=2026, confidence=90.0, page=1),
        subjects=[
            SubjectRow("Mathematics", 85, 100, "A", 95.0, 1),
            SubjectRow("English", 92, 100, "A+", 94.0, 1),
            SubjectRow("Physics", 81, 100, "A", 94.0, 1),
            SubjectRow("Chemistry", 79, 100, "B+", 93.0, 1),
        ],
        raw_text="synthetic mark sheet",
        engine="tesseract",
        kind="marksheet_12",
    )


def fake_aadhaar(
    number: str,
    *,
    checksum_valid: bool = True,
    qr_status: str = "match",
    dob: str = "2008-04-18",
    address: str = "12, Gandhi Street, Chennai 600028",
) -> Extraction:
    year = int(dob[:4]) if dob else None
    extraction = Extraction(
        pages=[page("synthetic aadhaar")],
        name=Field(value="Test Student", confidence=95.0, page=1),
        raw_text="synthetic aadhaar",
        engine="tesseract",
        kind="aadhaar",
        attributes={
            "aadhaar_number": mask_number(number),
            "name": "Test Student",
            "birth_detail": dob or (str(year) if year else None),
            "date_of_birth": dob,
            "year_of_birth": year,
            "gender": "Male",
            "address": address,
            "qr_status": qr_status,
            "qr_last4": number[-4:] if qr_status == "match" else "9999",
            "checksum_valid": checksum_valid,
        },
    )
    extraction.sensitive = {
        "aadhaar_number": number,
        "checksum_valid": checksum_valid,
        "qr_status": qr_status,
        "qr_last4": number[-4:] if qr_status == "match" else "9999",
    }
    return extraction


def fake_certificate(kind: str, **attributes) -> Extraction:
    values = {
        "name": "Test Student",
        "certificate_number": "CERT-001",
        "issue_date": (date.today() - timedelta(days=20)).isoformat(),
    }
    values.update(attributes)
    return Extraction(
        pages=[page(f"synthetic {kind}")],
        name=Field(value=values["name"], confidence=95.0, page=1),
        raw_text=f"synthetic {kind}",
        engine="tesseract",
        kind=kind,
        attributes=values,
    )


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


def validate_with(
    client,
    headers,
    monkeypatch,
    supporting: dict[str, Extraction] | None = None,
    sheets: dict[str, Extraction] | None = None,
) -> tuple[int, dict]:
    """Create an application, attach the core documents and fake OCR by kind."""

    application_id = create_application(client, headers)
    assert (
        upload(
            client,
            headers,
            application_id,
            "marksheet",
            "sheet.png",
            make_png((1240, 1754), pattern="sheet"),
        ).status_code
        == 201
    )
    for kind in sheets or {}:
        assert (
            upload(
                client,
                headers,
                application_id,
                kind,
                f"{kind}.png",
                make_png(pattern="sheet"),
            ).status_code
            == 201
        )
    assert (
        upload(
            client,
            headers,
            application_id,
            "photo",
            "portrait.png",
            make_png((360, 480), pattern="portrait"),
        ).status_code
        == 201
    )
    for kind in supporting or {}:
        assert (
            upload(
                client,
                headers,
                application_id,
                kind,
                f"{kind}.png",
                make_png(pattern="diagonal"),
            ).status_code
            == 201
        )

    documents = supporting or {}
    sheet_documents = sheets or {}

    def dispatch(data, mime_type, kind=None):
        if kind in sheet_documents:
            return sheet_documents[kind]
        if kind in (None, "auto", "marksheet", "marksheet_10", "marksheet_11", "marksheet_12"):
            return fake_mark_sheet()
        return documents[kind]

    monkeypatch.setattr(validation_service, "extract_document", dispatch)
    monkeypatch.setattr(
        validation_service,
        "analyze_photo",
        lambda data, mime_type=None: passing_photo(),
    )
    response = client.post(
        f"/api/applications/{application_id}/validate", headers=headers
    )
    assert response.status_code == 202, response.text
    detail = client.get(f"/api/applications/{application_id}", headers=headers).json()
    return application_id, detail


def finding(run: dict, field: str) -> dict:
    return next(item for item in run["findings"] if item["field"] == field)


def test_aadhaar_validation_masks_stores_encrypted_and_never_leaks(
    client, student_headers, monkeypatch
):
    number = synthetic_aadhaar()
    application_id, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {"aadhaar": fake_aadhaar(number)},
    )
    run = detail["latest_run"]
    assert run["overall"] == "pass", [
        (item["field"], item["result"], item["severity"], item["detail"])
        for item in run["findings"]
        if item["severity"] != "info"
    ]

    aadhaar_document = next(
        document for document in detail["documents"] if document["kind"] == "aadhaar"
    )
    assert aadhaar_document["masked_aadhaar"] == mask_number(number)
    assert finding(run, "Aadhaar number")["uploaded_value"] == mask_number(number)
    assert finding(run, "QR code")["result"] == "pass"

    # The API payload never carries the full number.
    assert number not in client.get(
        f"/api/applications/{application_id}", headers=student_headers
    ).text

    session = TestingSession()
    record = session.query(AadhaarRecord).one()
    assert record.last4 == number[-4:]
    assert record.checksum_valid is True
    assert record.qr_status == "match"
    assert record.number_encrypted != number
    assert decrypt_text(record.number_encrypted) == number

    ocr = session.query(OcrResult).join(OcrResult.document).filter_by(kind="aadhaar").one()
    assert number not in json.dumps(ocr.fields)
    assert number not in ocr.raw_text

    audit_rows = session.scalars(select(AuditLog)).all()
    assert all(number not in json.dumps(row.detail) for row in audit_rows)
    session.close()

    report = client.get(
        f"/api/applications/{application_id}/report.pdf", headers=student_headers
    )
    assert report.status_code == 200
    pdf = fitz.open(stream=report.content, filetype="pdf")
    text = "\n".join(pdf_page.get_text() for pdf_page in pdf)
    pdf.close()
    assert number not in text
    flat = " ".join(text.split())
    assert mask_number(number) in flat


def test_aadhaar_qr_mismatch_fails_validation(client, student_headers, monkeypatch):
    number = synthetic_aadhaar()
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {"aadhaar": fake_aadhaar(number, qr_status="mismatch")},
    )
    run = detail["latest_run"]
    assert run["overall"] == "fail"
    assert finding(run, "QR code")["result"] == "fail"
    assert finding(run, "Aadhaar number")["result"] == "pass"


def test_aadhaar_checksum_failure_fails_validation(client, student_headers, monkeypatch):
    valid = synthetic_aadhaar()
    invalid = valid[:-1] + str((int(valid[-1]) + 1) % 10)
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {"aadhaar": fake_aadhaar(invalid, checksum_valid=False)},
    )
    run = detail["latest_run"]
    assert run["overall"] == "fail"
    assert finding(run, "Aadhaar number")["result"] == "fail"
    assert finding(run, "Aadhaar number")["uploaded_value"] == mask_number(invalid)


def test_income_above_the_threshold_fails_and_within_passes(
    client, student_headers, monkeypatch
):
    _, above = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "income_certificate": fake_certificate(
                "income_certificate", annual_income=320000.0
            )
        },
    )
    run = above["latest_run"]
    assert run["overall"] == "fail"
    income = finding(run, "Annual income")
    assert income["result"] == "fail"
    assert income["uploaded_value"] == "INR 320,000"
    assert "250,000" in income["required_value"]

    _, within = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "income_certificate": fake_certificate(
                "income_certificate", annual_income=200000.0
            )
        },
    )
    assert within["latest_run"]["overall"] == "pass"
    assert finding(within["latest_run"], "Annual income")["result"] == "pass"


def test_expired_income_certificate_fails(client, student_headers, monkeypatch):
    issued = (date.today() - timedelta(days=500)).isoformat()
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "income_certificate": fake_certificate(
                "income_certificate",
                annual_income=200000.0,
                issue_date=issued,
            )
        },
    )
    run = detail["latest_run"]
    assert run["overall"] == "fail"
    issue = finding(run, "Issue date")
    assert issue["result"] == "fail"
    assert "expired" in issue["detail"].casefold()


def test_missing_income_amount_is_a_missing_upload(client, student_headers, monkeypatch):
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "income_certificate": fake_certificate(
                "income_certificate", annual_income=None
            )
        },
    )
    run = detail["latest_run"]
    assert run["overall"] == "fail"
    income = finding(run, "Annual income")
    assert income["result"] == "missing_upload"
    assert "could not be read from the income certificate" in income["detail"]


def test_community_known_passes_and_unknown_goes_to_review(
    client, student_headers, monkeypatch
):
    _, known = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "community_certificate": fake_certificate(
                "community_certificate", community="BC"
            )
        },
    )
    assert known["latest_run"]["overall"] == "pass"

    _, unknown = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "community_certificate": fake_certificate(
                "community_certificate", community="XYZ"
            )
        },
    )
    run = unknown["latest_run"]
    assert run["overall"] == "review"
    assert finding(run, "Community")["result"] == "pending"


def test_first_graduate_certificate_must_agree_with_the_claim(
    client, student_headers, monkeypatch
):
    _, agreeing = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "first_graduate_certificate": fake_certificate(
                "first_graduate_certificate", first_graduate="yes"
            )
        },
    )
    assert agreeing["latest_run"]["overall"] == "pass"
    assert finding(agreeing["latest_run"], "First graduate status")["result"] == "pass"

    _, contradicting = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "first_graduate_certificate": fake_certificate(
                "first_graduate_certificate", first_graduate="no"
            )
        },
    )
    run = contradicting["latest_run"]
    assert run["overall"] == "fail"
    assert finding(run, "First graduate status")["result"] == "fail"


def test_supporting_document_name_mismatch_is_reported(
    client, student_headers, monkeypatch
):
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "community_certificate": fake_certificate(
                "community_certificate",
                name="Someone Else",
                community="BC",
            )
        },
    )
    run = detail["latest_run"]
    assert run["overall"] == "fail"
    name_findings = [
        item
        for item in run["findings"]
        if item["category"] == "identity" and item["field"] == "Applicant name"
    ]
    assert any(item["result"] == "mismatch" for item in name_findings)

def test_father_name_match_and_mismatch_on_certificates(
    client, student_headers, monkeypatch
):
    _, agreeing = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "community_certificate": fake_certificate(
                "community_certificate",
                community="BC",
                father_name="Ravi Student",
            )
        },
    )
    run = agreeing["latest_run"]
    assert run["overall"] == "pass"
    father = finding(run, "Father's name")
    assert father["category"] == "consistency"
    assert father["result"] == "match"

    _, differing = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "community_certificate": fake_certificate(
                "community_certificate",
                community="BC",
                father_name="Suresh Kumar",
            )
        },
    )
    run = differing["latest_run"]
    assert run["overall"] == "fail"
    father = finding(run, "Father's name")
    assert father["result"] == "mismatch"
    assert father["severity"] == "critical"
    assert father["uploaded_value"] == "Suresh Kumar"
    assert "does not match the application" in father["detail"]
    assert "father's name" in father["meta"]["clause"]


def test_aadhaar_address_mismatch_is_a_warning(client, student_headers, monkeypatch):
    number = synthetic_aadhaar()
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "aadhaar": fake_aadhaar(
                number, address="99, Some Other Road, Madurai 625001"
            )
        },
    )
    run = detail["latest_run"]
    assert run["overall"] == "review"
    address = finding(run, "Address")
    assert address["category"] == "consistency"
    assert address["result"] == "pending"
    assert address["severity"] == "warning"
    assert "differs from the application" in address["detail"]


def test_run_summary_carries_the_identity_matrix(client, student_headers, monkeypatch):
    number = synthetic_aadhaar()
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {"aadhaar": fake_aadhaar(number)},
    )
    summary = detail["latest_run"]["summary"]
    matrix = summary["identity_matrix"]
    fields = {row["field"]: row for row in matrix["fields"]}
    assert fields["name"]["status"] == "match"
    assert fields["date_of_birth"]["status"] == "match"
    assert fields["father_name"]["status"] == "not_available"
    assert fields["address"]["status"] == "match"
    assert matrix["checked"] == 3
    assert summary["identity_mismatches"] == 0
    assert any(
        value["source"] == "Aadhaar" for value in fields["name"]["values"]
    )


def fake_class_11_sheet(name: str = "Test Student") -> Extraction:
    return Extraction(
        pages=[page("synthetic class 11 mark sheet")],
        name=Field(value=name, confidence=95.0, page=1),
        register_number=Field(value="REG2025A014", confidence=94.0, page=1),
        exam_year=Field(value=2025, confidence=90.0, page=1),
        subjects=[
            SubjectRow("Mathematics", 88, 100, "A", 95.0, 1),
            SubjectRow("English", 90, 100, "A+", 94.0, 1),
            SubjectRow("Physics", 85, 100, "A", 94.0, 1),
            SubjectRow("Chemistry", 84, 100, "A", 93.0, 1),
            SubjectRow("Computer Science", 92, 100, "A+", 93.0, 1),
        ],
        raw_text="synthetic class 11 mark sheet",
        engine="tesseract",
        kind="marksheet_11",
    )


def test_class_11_name_conflict_against_class_12_is_in_the_matrix(
    client, student_headers, monkeypatch
):
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        sheets={"marksheet_11": fake_class_11_sheet("Someone Else")},
    )
    run = detail["latest_run"]
    assert run["overall"] == "fail"
    matrix = run["summary"]["identity_matrix"]
    name_row = next(row for row in matrix["fields"] if row["field"] == "name")
    values = {value["source"]: value for value in name_row["values"]}
    assert values["Class 12 mark sheet"]["status"] == "match"
    assert values["Class 11 mark sheet"]["status"] == "mismatch"
    assert name_row["status"] == "mismatch"
    assert matrix["mismatched"] >= 1


def test_community_name_conflict_against_the_mark_sheet_is_in_the_matrix(
    client, student_headers, monkeypatch
):
    _, detail = validate_with(
        client,
        student_headers,
        monkeypatch,
        {
            "community_certificate": fake_certificate(
                "community_certificate",
                name="Someone Else",
                community="BC",
            )
        },
    )
    run = detail["latest_run"]
    assert run["overall"] == "fail"
    matrix = run["summary"]["identity_matrix"]
    name_row = next(row for row in matrix["fields"] if row["field"] == "name")
    values = {value["source"]: value for value in name_row["values"]}
    assert values["Class 12 mark sheet"]["status"] == "match"
    assert values["Community certificate"]["status"] == "mismatch"
    assert name_row["status"] == "mismatch"
    assert matrix["mismatched"] == 1
