from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dni: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    first_names: Mapped[str] = mapped_column(String(120))
    last_names: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVO")
    responsible_advisor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acquisition_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    acquisition_channel_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(500), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    province: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ubigeo: Mapped[str | None] = mapped_column(String(6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
