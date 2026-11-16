from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ApplicationStatus


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    program: Mapped[str] = mapped_column(String(160), nullable=False)
    applicant_name: Mapped[str] = mapped_column(String(160), nullable=False)
    register_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exam_year: Mapped[int] = mapped_column(Integer, nullable=False)
    board: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default=ApplicationStatus.submitted.value, nullable=False, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped["User"] = relationship(back_populates="applications")  # noqa: F821
    entered_marks: Mapped[list["EnteredMark"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="EnteredMark.id"
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


class EnteredMark(Base):
    __tablename__ = "entered_marks"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    marks_obtained: Mapped[float] = mapped_column(Float, nullable=False)
    max_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(12), nullable=True)

    application: Mapped[Application] = relationship(back_populates="entered_marks")
