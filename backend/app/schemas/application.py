from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnteredMarkIn(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    marks_obtained: float = Field(ge=0, le=1000)
    max_marks: float | None = Field(default=None, gt=0, le=1000)
    grade: str | None = Field(default=None, max_length=12)

    @field_validator("subject")
    @classmethod
    def tidy_subject(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("subject is required")
        return cleaned

    @field_validator("marks_obtained")
    @classmethod
    def finite_marks(cls, value: float) -> float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("marks must be a finite number")
        return value


class ApplicationCreate(BaseModel):
    program: str = Field(min_length=2, max_length=160)
    applicant_name: str = Field(min_length=2, max_length=160)
    register_number: str = Field(min_length=2, max_length=64)
    exam_year: int = Field(ge=1990, le=2100)
    board: str = Field(default="", max_length=160)
    marks: list[EnteredMarkIn] = Field(min_length=1, max_length=30)

    @field_validator("program", "applicant_name", "register_number")
    @classmethod
    def tidy(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("this field is required")
        return cleaned

    @field_validator("register_number")
    @classmethod
    def upper_register(cls, value: str) -> str:
        return value.upper()

    @field_validator("marks")
    @classmethod
    def unique_subjects(cls, value: list[EnteredMarkIn]) -> list[EnteredMarkIn]:
        seen = {mark.subject.strip().lower() for mark in value}
        if len(seen) != len(value):
            raise ValueError("a subject is entered twice")
        return value


class MarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    marks_obtained: float
    max_marks: float | None
    grade: str | None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    original_filename: str
    mime_type: str
    size_bytes: int
    page_count: int
    width: int | None
    height: int | None
    duplicate_of_id: int | None
    created_at: datetime


class UploadResult(BaseModel):
    document: DocumentOut
    warnings: list[str] = []


class ExtractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    subject_raw: str
    subject_norm: str | None
    marks_obtained: float | None
    max_marks: float | None
    grade: str | None
    confidence: float
    page: int
    corrected_subject: str | None
    corrected_marks: float | None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    field: str
    subject_norm: str | None
    result: str
    entered_value: str | None
    uploaded_value: str | None
    measured_value: str | None
    required_value: str | None
    difference: float | None
    detail: str | None
    severity: str
    confidence: float | None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    overall: str | None
    summary: dict
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    findings: list[FindingOut] = []


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    program: str
    applicant_name: str
    register_number: str
    exam_year: int
    board: str
    status: str
    created_at: datetime
    submitted_at: datetime | None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    priority: int
    reasons: list[str] = []
    run_id: int | None = None
    assigned_to_email: str | None = None
    decision_comment: str | None = None
    decided_by_email: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ApplicationDetail(ApplicationOut):
    marks: list[MarkOut] = []
    documents: list[DocumentOut] = []
    latest_run: RunOut | None = None
    extracted_marks: list[ExtractOut] = []
    review: ReviewOut | None = None


class ApplicationList(BaseModel):
    items: list[ApplicationOut]
    total: int


class ReviewDecision(BaseModel):
    comment: str = Field(min_length=3, max_length=2000)

    @field_validator("comment")
    @classmethod
    def tidy_comment(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 3:
            raise ValueError("a comment is required for every decision")
        return cleaned


class MarkCorrection(BaseModel):
    marks_obtained: float = Field(ge=0, le=1000)
    subject: str | None = Field(default=None, max_length=160)
