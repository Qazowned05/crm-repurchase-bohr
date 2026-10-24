from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.modules.customers.schemas import CustomerCreate
from app.modules.sales.schemas import SaleItemCreate


class LeadCreate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    dni: str | None = Field(default=None, max_length=20)
    phone: str = Field(min_length=6, max_length=30)
    campaign_id: str
    email: EmailStr | None = None
    condition: str | None = Field(default=None, max_length=500)
    initial_product_id: str | None = None
    notes: str | None = Field(default=None, max_length=4000)
    assigned_advisor_id: str | None = None


class LeadUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    dni: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    email: EmailStr | None = None
    condition: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    initial_product_id: str | None = None


class LeadAssignmentCreate(BaseModel):
    assigned_advisor_id: str | None = None
    reason: str = Field(min_length=3, max_length=4000)


class BulkLeadAssignmentCreate(LeadAssignmentCreate):
    lead_ids: list[str] = Field(min_length=1, max_length=200)


class LeadActivityCreate(BaseModel):
    channel: Literal["LLAMADA", "WHATSAPP"]
    typification_id: str
    note: str | None = Field(default=None, max_length=4000)
    next_action_date: date | None = None
    next_action_at: datetime | None = None

    @model_validator(mode="after")
    def action_date_matches_timestamp(self) -> "LeadActivityCreate":
        if self.next_action_at and self.next_action_date and self.next_action_at.date() != self.next_action_date:
            raise ValueError("next_action_date must match next_action_at")
        return self


class LeadConversionCreate(BaseModel):
    typification_id: str
    channel: Literal["LLAMADA", "WHATSAPP"]
    activity_note: str | None = Field(default=None, max_length=4000)
    customer_id: str | None = None
    customer: CustomerCreate | None = None
    customer_condition: str | None = Field(default=None, max_length=500)
    sale_date: date
    items: list[SaleItemCreate] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def customer_choice_is_exclusive(self) -> "LeadConversionCreate":
        if (self.customer_id is None) == (self.customer is None):
            raise ValueError("Provide exactly one of customer_id or customer")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("A product may only appear once per sale")
        return self
