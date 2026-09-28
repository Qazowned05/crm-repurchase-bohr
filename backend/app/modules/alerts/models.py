from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("sale_item_id", "alert_date", name="uq_alerts_sale_item_alert_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sale_item_id: Mapped[str] = mapped_column(ForeignKey("sale_items.id", ondelete="RESTRICT"), index=True)
    assigned_advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    alert_date: Mapped[date] = mapped_column(Date, index=True)
    expected_repurchase_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDIENTE", index=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AlertContactAttempt(Base):
    __tablename__ = "alert_contact_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    advisor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    contacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    channel: Mapped[str] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(40))
    typification_id: Mapped[str | None] = mapped_column(ForeignKey("contact_typifications.id", ondelete="RESTRICT"), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)
