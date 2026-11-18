from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ApplicationStatus


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    applicant_name: Mapped[str] = mapped_column(String(160), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    father_name: Mapped[str] = mapped_column(String(160), nullable=False)
    mother_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(24), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    is_orphan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_first_graduate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default=ApplicationStatus.submitted.value, nullable=False, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped["User"] = relationship(back_populates="applications")  # noqa: F821
    education_records: Mapped[list["EducationRecord"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="EducationRecord.class_level",
    )
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        back_populates="application", cascade="all, delete-orphan", order_by="Document.id"
    )
    runs: Mapped[list["ValidationRun"]] = relationship(  # noqa: F821
        back_populates="application", cascade="all, delete-orphan", order_by="ValidationRun.id.desc()"
    )
    review_item: Mapped["ReviewItem | None"] = relationship(  # noqa: F821
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def latest_run(self):
        return self.runs[0] if self.runs else None

    @property
    def classes(self) -> list["EducationRecord"]:
        return sorted(self.education_records, key=lambda record: record.class_level)

    def class_record(self, class_level: int) -> "EducationRecord | None":
        return next(
            (record for record in self.education_records if record.class_level == class_level),
            None,
        )

    @property
    def class_12(self) -> "EducationRecord | None":
        return self.class_record(12)


class EducationRecord(Base):
    __tablename__ = "education_records"
    __table_args__ = (
        UniqueConstraint(
            "application_id", "class_level", name="uq_education_application_class"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    class_level: Mapped[int] = mapped_column(Integer, nullable=False)
    register_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exam_year: Mapped[int] = mapped_column(Integer, nullable=False)
    board: Mapped[str] = mapped_column(String(160), default="", nullable=False)

    application: Mapped[Application] = relationship(back_populates="education_records")
    marks: Mapped[list["EnteredMark"]] = relationship(
        back_populates="education_record",
        cascade="all, delete-orphan",
        order_by="EnteredMark.id",
    )

    @property
    def label(self) -> str:
        return f"Class {self.class_level}"


class EnteredMark(Base):
    __tablename__ = "entered_marks"

    id: Mapped[int] = mapped_column(primary_key=True)
    education_record_id: Mapped[int] = mapped_column(
        ForeignKey("education_records.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    marks_obtained: Mapped[float] = mapped_column(Float, nullable=False)
    max_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(12), nullable=True)

    education_record: Mapped[EducationRecord] = relationship(back_populates="marks")
