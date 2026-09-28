from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class CustomerCreate(BaseModel):
    dni: str = Field(min_length=6, max_length=20)
    first_names: str = Field(min_length=2, max_length=120)
    last_names: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    email: EmailStr | None = None
    responsible_advisor_id: str | None = None

    @field_validator("dni")
    @classmethod
    def normalize_dni(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.isalnum():
            raise ValueError("DNI must contain only letters and numbers")
        return normalized.upper()


class CustomerUpdate(BaseModel):
    first_names: str | None = Field(default=None, min_length=2, max_length=120)
    last_names: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    email: EmailStr | None = None


class CustomerSupervisorUpdate(CustomerUpdate):
    responsible_advisor_id: str | None = None
    status: Literal["ACTIVO", "INACTIVO"] | None = None


class CustomerResponse(BaseModel):
    id: str
    dni: str
    first_names: str
    last_names: str
    phone: str
    email: EmailStr | None
    status: str
    responsible_advisor_id: str | None
    acquisition_channel: str | None
    acquisition_channel_detail: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
