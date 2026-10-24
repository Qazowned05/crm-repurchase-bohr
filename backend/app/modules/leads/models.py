from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    full_name: Mapped[str] = mapped_column(String(255))
    dni: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(500), nullable=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="RESTRICT"), index=True)
    initial_product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDIENTE", index=True)
    reassigned_from_recovery: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    assigned_advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    converted_customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True)
    converted_sale_id: Mapped[str | None] = mapped_column(ForeignKey("sales.id", ondelete="RESTRICT", use_alter=True, name="fk_leads_converted_sale_id"), nullable=True, unique=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    advisor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    typification_id: Mapped[str] = mapped_column(ForeignKey("contact_typifications.id", ondelete="RESTRICT"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LeadAssignmentHistory(Base):
    __tablename__ = "lead_assignment_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    previous_advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    assigned_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LeadNotification(Base):
    __tablename__ = "lead_notifications"
    __table_args__ = (UniqueConstraint("lead_id", "user_id", "scheduled_for", name="uq_lead_notifications_schedule"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
