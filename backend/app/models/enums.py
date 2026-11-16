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
    marksheet = "marksheet"
    photo = "photo"
    other = "other"


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
