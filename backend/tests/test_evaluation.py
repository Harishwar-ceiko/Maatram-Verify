from __future__ import annotations

import io

import numpy as np
from PIL import Image

from app.ocr.types import Extraction, Field, SubjectRow
from app.services import evaluation


def _subject(value: str, marks: float, max_marks: float = 100) -> SubjectRow:
    return SubjectRow(
        subject_raw=value,
        marks_obtained=marks,
        max_marks=max_marks,
        grade="A",
        confidence=95.0,
        page=1,
    )


def _case(case_id: str, variant: str, subjects, entered, expected_mismatches):
    return {
        "id": case_id,
        "variant": variant,
        "sheet": f"{case_id}.png",
        "mime": "image/png",
        "applicant_name": "Asha Rao" if case_id == "a" else "Bala Kumar",
        "register_number": "REG2026Z001" if case_id == "a" else "REG2026Z002",
        "exam_year": 2026,
        "board": "State Board",
        "subjects": subjects,
        "entered": entered,
        "expected": {
            "mismatches": expected_mismatches,
            "missing_upload": [],
            "extra_on_sheet": [],
        },
    }


def _noise_png(width: int, height: int, seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(90, 211, size=(height, width, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def test_evaluation_scores_extraction_and_mismatch_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "SYNTHETIC_DIR", tmp_path)
    (tmp_path / "a.png").write_bytes(b"a" * 10)
    (tmp_path / "b.png").write_bytes(b"b" * 20)
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "good.png").write_bytes(_noise_png(480, 600, 11))
    (tmp_path / "photos" / "small.png").write_bytes(_noise_png(220, 275, 12))

    subjects = [
        {"subject": "Mathematics", "marks": 70, "max_marks": 100, "grade": "B+"},
        {"subject": "English", "marks": 60, "max_marks": 100, "grade": "B"},
    ]
    dataset = {
        "dataset": "test-v1",
        "cases": [
            _case(
                "a",
                "clean",
                [
                    {"subject": "Mathematics", "marks": 88, "max_marks": 100, "grade": "A"},
                    {"subject": "English", "marks": 92, "max_marks": 100, "grade": "A+"},
                ],
                [
                    {"subject": "Mathematics", "marks": 88, "max_marks": 100},
                    {"subject": "English", "marks": 92, "max_marks": 100},
                ],
                [],
            ),
            _case(
                "b",
                "noise",
                subjects,
                [
                    {"subject": "Mathematics", "marks": 70, "max_marks": 100},
                    {"subject": "English", "marks": 68, "max_marks": 100},
                ],
                [{"subject": "English", "entered": 68, "sheet": 60}],
            ),
        ],
        "photos": [
            {
                "id": "photo-good",
                "file": "photos/good.png",
                "mime": "image/png",
                "expected": {"Resolution": "pass"},
                "expected_critical": [],
                "note": "good",
            },
            {
                "id": "photo-small",
                "file": "photos/small.png",
                "mime": "image/png",
                "expected": {"Resolution": "fail"},
                "expected_critical": ["Resolution"],
                "note": "small",
            },
        ],
    }

    exact_a = Extraction(
        name=Field(value="Asha Rao", confidence=95.0),
        register_number=Field(value="REG2026Z001", confidence=95.0),
        exam_year=Field(value=2026, confidence=90.0),
        subjects=[_subject("Mathematics", 88), _subject("English", 92)],
    )
    exact_b = Extraction(
        name=Field(value="Bala Kumar", confidence=95.0),
        register_number=Field(value="REG2026Z002", confidence=95.0),
        exam_year=Field(value=2026, confidence=90.0),
        subjects=[_subject("Mathematics", 70), _subject("English", 60)],
    )

    def fake_extract(data: bytes, mime: str, kind: str | None = None) -> Extraction:
        return exact_a if len(data) == 10 else exact_b

    monkeypatch.setattr(evaluation, "extract_document", fake_extract)
    summary, markdown = evaluation.evaluate_dataset(dataset)

    assert summary["cases"] == 2
    assert summary["mark_sheets"] == {
        "total": 2,
        "class_10": 0,
        "class_11": 0,
        "class_12": 2,
    }
    assert summary["field_accuracy"] == 1.0
    assert summary["subjects"]["found_rate"] == 1.0
    assert summary["subjects"]["mark_accuracy"] == 1.0
    assert summary["mismatch"] == {
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "tp": 1,
        "fp": 0,
        "fn": 0,
        "matrix": {"tp": 1, "fp": 0, "fn": 0, "tn": 1, "accuracy": 1.0},
    }
    assert summary["comparison_engine"]["f1"] == 1.0
    assert summary["photos"]["rule_accuracy"] == 1.0
    assert summary["photos"]["critical_correct"] == 2
    assert summary["targets"]["field_accuracy"]["met"] is True
    assert "Accuracy evaluation" in markdown
    assert "photo-small" not in markdown


def test_evaluation_reports_ocr_errors_without_aborting(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "SYNTHETIC_DIR", tmp_path)
    (tmp_path / "broken.png").write_bytes(b"broken")
    dataset = {
        "dataset": "test-v1",
        "cases": [
            _case(
                "broken",
                "clean",
                [{"subject": "Mathematics", "marks": 88, "max_marks": 100, "grade": "A"}],
                [{"subject": "Mathematics", "marks": 88, "max_marks": 100}],
                [],
            )
        ],
        "photos": [],
    }

    def explode(data: bytes, mime: str, kind: str | None = None):
        raise RuntimeError("tesseract unavailable")

    monkeypatch.setattr(evaluation, "extract_document", explode)
    summary, _ = evaluation.evaluate_dataset(dataset)

    assert summary["field_accuracy"] == 0.0
    assert summary["errors"][0]["case"] == "broken"
    assert "tesseract unavailable" in summary["errors"][0]["error"]
    assert summary["status"] == "completed"


def test_evaluation_scores_supporting_documents_and_classification(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "SYNTHETIC_DIR", tmp_path)
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "aadhaar-ok.png").write_bytes(b"aadhaar-ok")
    (tmp_path / "documents" / "aadhaar-bad.png").write_bytes(b"aadhaar-bad")
    (tmp_path / "documents" / "income.png").write_bytes(b"income")
    dataset = {
        "dataset": "test-v1",
        "cases": [],
        "documents": [
            {
                "id": "aadhaar-ok",
                "kind": "aadhaar",
                "file": "documents/aadhaar-ok.png",
                "mime": "image/png",
                "variant": "clean",
                "expected": {
                    "name": "Asha Rao",
                    "birth_detail": "2008-04-18",
                    "aadhaar_last4": "1234",
                    "checksum_valid": True,
                },
                "note": "valid",
            },
            {
                "id": "aadhaar-bad",
                "kind": "aadhaar",
                "file": "documents/aadhaar-bad.png",
                "mime": "image/png",
                "variant": "clean",
                "expected": {
                    "name": "Bala Kumar",
                    "birth_detail": "2007",
                    "aadhaar_last4": "5678",
                    "checksum_valid": False,
                },
                "note": "invalid checksum",
            },
            {
                "id": "income",
                "kind": "income_certificate",
                "file": "documents/income.png",
                "mime": "image/png",
                "variant": "clean",
                "expected": {
                    "name": "Asha Rao",
                    "certificate_number": "INC/2026/0042",
                    "issue_date": "2026-04-12",
                    "annual_income": 180000,
                },
                "note": "income",
            },
        ],
        "photos": [],
    }

    extractions = {
        b"aadhaar-ok": Extraction(
            name=Field(value="Asha Rao", confidence=95.0),
            raw_text="Aadhaar\nUnique Identification Authority of India\nName: Asha Rao",
            kind="aadhaar",
            attributes={
                "name": "Asha Rao",
                "aadhaar_number": "XXXX XXXX 1234",
                "birth_detail": "2008-04-18",
                "checksum_valid": True,
            },
        ),
        b"aadhaar-bad": Extraction(
            name=Field(value="Bala Kumar", confidence=95.0),
            raw_text="Aadhaar\nUnique Identification Authority of India\nName: Bala Kumar",
            kind="aadhaar",
            attributes={
                "name": "Bala Kumar",
                "aadhaar_number": "XXXX XXXX 5678",
                "birth_detail": "2007",
                "checksum_valid": False,
            },
        ),
        b"income": Extraction(
            name=Field(value="Asha Rao", confidence=95.0),
            raw_text="Income Certificate\nAnnual Income: INR 1,80,000\nRevenue Department",
            kind="income_certificate",
            attributes={
                "name": "Asha Rao",
                "certificate_number": "INC/2026/0042",
                "issue_date": "2026-04-12",
                "annual_income": 180000,
            },
        ),
    }

    def fake_document(data: bytes, mime: str, kind: str | None = None) -> Extraction:
        return extractions[data]

    monkeypatch.setattr(evaluation, "extract_document", fake_document)
    summary, markdown = evaluation.evaluate_dataset(dataset)

    documents = summary["documents"]
    assert documents["fixtures"] == 3
    assert documents["fields_total"] == 12
    assert documents["fields_correct"] == 12
    assert documents["field_accuracy"] == 1.0
    assert documents["checksum"] == {"tested": 2, "correct": 2, "accuracy": 1.0}
    assert documents["classification_accuracy"] == 1.0
    assert summary["classification"]["accuracy"] == 1.0
    assert summary["classification"]["total"] == 3
    assert summary["targets"]["document_field_accuracy"]["met"] is True
    assert "## Supporting documents" in markdown
    assert "Aadhaar checksum: **2/2**" in markdown
    assert "## Document type confusion" in markdown
