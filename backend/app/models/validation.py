from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin
from app.models.enums import RunStatus


class ValidationRun(Base, TimestampMixin):
    __tablename__ = "validation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.pending.value, nullable=False)
    overall: Mapped[str | None] = mapped_column(String(20), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped["Application"] = relationship(back_populates="runs")  # noqa: F821
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Finding.sort_order"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("validation_runs.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(160), nullable=False)
    subject_norm: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    entered_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    measured_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difference: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    run: Mapped[ValidationRun] = relationship(back_populates="findings")
