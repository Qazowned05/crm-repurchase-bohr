from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), index=True)
    advisor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="CONFIRMADA", index=True)
    acquisition_channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    acquisition_channel_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    replaces_sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True, unique=True, index=True
    )
    source_alert_id: Mapped[str | None] = mapped_column(ForeignKey("alerts.id", ondelete="RESTRICT", use_alter=True, name="fk_sales_source_alert_id"), nullable=True, unique=True, index=True)
    annulled_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    annulment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    annulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sale_id: Mapped[str] = mapped_column(ForeignKey("sales.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column()
    rule_duration_days: Mapped[int] = mapped_column()
    rule_alert_days: Mapped[list[int]] = mapped_column(JSON)
    expected_repurchase_date: Mapped[date] = mapped_column(Date)
    purchase_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prior_confirmed_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("sale_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SaleDuplicateReview(Base):
    __tablename__ = "sales_duplicate_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sale_id: Mapped[str] = mapped_column(ForeignKey("sales.id", ondelete="RESTRICT"), unique=True, index=True)
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    reviewed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
