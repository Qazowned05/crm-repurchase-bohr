from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class CustomerCreate(BaseModel):
    dni: str = Field(min_length=6, max_length=20)
    customer_type: Literal["PERSONA", "EMPRESA"] = "PERSONA"
    business_name: str | None = Field(default=None, max_length=255)
    first_names: str | None = Field(default=None, max_length=120)
    last_names: str | None = Field(default=None, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    email: EmailStr | None = None
    responsible_advisor_id: str | None = None
    condition: str | None = Field(default=None, max_length=500)
    birth_date: date | None = Field(default=None, le=date.today())
    department: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    ubigeo: str | None = Field(default=None, pattern=r"^\d{6}$")

    @field_validator("dni")
    @classmethod
    def normalize_dni(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.isalnum():
            raise ValueError("DNI must contain only letters and numbers")
        return normalized.upper()

    @model_validator(mode="after")
    def validate_customer_identity(self) -> "CustomerCreate":
        if self.customer_type == "EMPRESA":
            if not self.dni.isdigit() or len(self.dni) != 11:
                raise ValueError("RUC must contain exactly 11 digits")
            if not self.business_name or len(self.business_name.strip()) < 2:
                raise ValueError("business_name is required for an EMPRESA customer")
            self.business_name = self.business_name.strip()
            # Existing sales, alerts, and reports use these presentation fields.
            self.first_names = self.business_name
            self.last_names = ""
            self.birth_date = None
        else:
            if not self.first_names or len(self.first_names.strip()) < 2:
                raise ValueError("first_names is required for a PERSONA customer")
            if not self.last_names or len(self.last_names.strip()) < 2:
                raise ValueError("last_names is required for a PERSONA customer")
            self.first_names = self.first_names.strip()
            self.last_names = self.last_names.strip()
            self.business_name = None
        return self


class CustomerUpdate(BaseModel):
    customer_type: Literal["PERSONA", "EMPRESA"] | None = None
    business_name: str | None = Field(default=None, max_length=255)
    first_names: str | None = Field(default=None, max_length=120)
    last_names: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    email: EmailStr | None = None
    condition: str | None = Field(default=None, max_length=500)
    birth_date: date | None = Field(default=None, le=date.today())
    department: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    ubigeo: str | None = Field(default=None, pattern=r"^\d{6}$")


class CustomerSupervisorUpdate(CustomerUpdate):
    responsible_advisor_id: str | None = None
    status: Literal["ACTIVO", "INACTIVO"] | None = None


class CustomerResponse(BaseModel):
    id: str
    dni: str
    customer_type: Literal["PERSONA", "EMPRESA"]
    business_name: str | None
    first_names: str
    last_names: str
    phone: str
    email: EmailStr | None
    status: str
    responsible_advisor_id: str | None
    acquisition_channel: str | None
    acquisition_channel_detail: str | None
    condition: str | None
    birth_date: date | None
    department: str | None
    province: str | None
    district: str | None
    ubigeo: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
