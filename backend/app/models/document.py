from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin
from app.models.enums import DocumentKind, RunStatus


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(
        String(40), default=DocumentKind.marksheet_12.value, nullable=False
    )
    # Deterministic evidence from the upload-time classifier: matched phrases,
    # scores and whether the applicant overrode the detected type.
    classification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    phash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    encrypted: Mapped[bool] = mapped_column(default=True, nullable=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    application: Mapped["Application"] = relationship(back_populates="documents")  # noqa: F821
    ocr_result: Mapped["OcrResult | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    extracted_marks: Mapped[list["ExtractedMark"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="ExtractedMark.id"
    )
    aadhaar_record: Mapped["AadhaarRecord | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def masked_aadhaar(self) -> str | None:
        record = self.aadhaar_record
        if record is None:
            return None
        return f"XXXX XXXX {record.last4}"

    @property
    def kind_label(self) -> str:
        # Imported lazily to keep model import order simple.
        from app.core.config import rules

        kinds = rules().get("documents", {}).get("kinds", {})
        return str(kinds.get(self.kind, {}).get("label", self.kind.replace("_", " ").title()))


class OcrResult(Base, TimestampMixin):
    __tablename__ = "ocr_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    engine: Mapped[str] = mapped_column(String(40), default="tesseract", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.pending.value, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped[Document] = relationship(back_populates="ocr_result")


class ExtractedMark(Base):
    __tablename__ = "extracted_marks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    subject_raw: Mapped[str] = mapped_column(String(160), nullable=False)
    subject_norm: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    marks_obtained: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(12), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    corrected_subject: Mapped[str | None] = mapped_column(String(160), nullable=True)
    corrected_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    corrected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship(back_populates="extracted_marks")

    @property
    def effective_subject(self) -> str:
        return self.corrected_subject or self.subject_raw

    @property
    def effective_marks(self) -> float | None:
        return self.corrected_marks if self.corrected_marks is not None else self.marks_obtained


class AadhaarRecord(Base, TimestampMixin):
    """The only place a full Aadhaar number is kept.

    The number is encrypted with the same Fernet key as the document bytes.
    Every other layer (OCR fields, findings, logs, audit rows, the API and the
    PDF) sees only ``last4`` or the masked display value.
    """

    __tablename__ = "aadhaar_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    number_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    checksum_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qr_status: Mapped[str] = mapped_column(String(20), default="not_detected", nullable=False)
    qr_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)

    document: Mapped[Document] = relationship(back_populates="aadhaar_record")
