from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContactTypification(Base):
    __tablename__ = "contact_typifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("contact_typifications.id", ondelete="RESTRICT"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_next_action: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_note: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_close: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AlertOperationalSettings(Base):
    __tablename__ = "alert_operational_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    advisor_visibility_days: Mapped[int] = mapped_column(Integer, default=30)
    maximum_attempts: Mapped[int] = mapped_column(Integer, default=3)
    stale_days: Mapped[int] = mapped_column(Integer, default=7)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
