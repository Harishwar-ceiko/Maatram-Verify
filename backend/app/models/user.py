
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Role


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), default=Role.student.value, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Optional student profile information
    volunteer_activities: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    achievements: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="Application.id.desc()",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == Role.admin.value
