from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    student = "student"
    admin = "admin"


class ApplicationStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    processing = "processing"
    needs_review = "needs_review"
    verified = "verified"
    approved = "approved"
    rejected = "rejected"


class DocumentKind(str, Enum):
    # Specific kinds introduced with multi-document verification.
    marksheet_10 = "marksheet_10"
    marksheet_11 = "marksheet_11"
    marksheet_12 = "marksheet_12"
    aadhaar = "aadhaar"
    income_certificate = "income_certificate"
    community_certificate = "community_certificate"
    first_graduate_certificate = "first_graduate_certificate"
    photo = "photo"
    # Legacy aliases kept so pre-Phase-2 records and clients still resolve.
    marksheet = "marksheet"
    other = "other"

    @classmethod
    def supported(cls) -> set[str]:
        return {
            "marksheet_10",
            "marksheet_11",
            "marksheet_12",
            "aadhaar",
            "income_certificate",
            "community_certificate",
            "first_graduate_certificate",
            "photo",
        }

    @classmethod
    def normalise(cls, value: str) -> str | None:
        """Map a client-supplied kind to a supported kind.

        The old generic ``marksheet`` always meant the Class 12 statement,
        because that was the only academic sheet the first release accepted.
        """

        cleaned = (value or "").strip().lower()
        if cleaned == cls.marksheet.value:
            return cls.marksheet_12.value
        return cleaned if cleaned in cls.supported() else None


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Result(str, Enum):
    match = "match"
    mismatch = "mismatch"
    pass_ = "pass"
    fail = "fail"
    pending = "pending"
    missing_upload = "missing_upload"
    missing_entry = "missing_entry"
    skipped = "skipped"


class FindingCategory(str, Enum):
    mark = "mark"
    completeness = "completeness"
    document = "document"
    photo = "photo"
    identity = "identity"
    duplicate = "duplicate"
    format = "format"
    ocr = "ocr"


class ReviewStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"
