from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ContactAttemptCreate(BaseModel):
    channel: str = Field(min_length=1, max_length=20)
    result: str = Field(min_length=1, max_length=40)
    typification_id: str | None = None
    note: str | None = Field(default=None, max_length=4000)
    next_action_date: date | None = None
    close_alert: bool = False


class RepurchaseItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, le=100000)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class AlertRepurchaseCreate(BaseModel):
    sale_date: date = Field(default_factory=date.today)
    notes: str | None = Field(default=None, max_length=4000)
    acquisition_channel: Literal["TV", "DIGITAL", "OTROS"] | None = None
    acquisition_channel_detail: str | None = Field(default=None, max_length=255)
    items: list[RepurchaseItemCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_sale(self) -> "AlertRepurchaseCreate":
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("A product may only appear once per sale")
        if self.acquisition_channel == "OTROS" and not (self.acquisition_channel_detail or "").strip():
            raise ValueError("Acquisition channel detail is required for OTROS")
        if self.acquisition_channel != "OTROS" and self.acquisition_channel_detail is not None:
            raise ValueError("Acquisition channel detail is only allowed for OTROS")
        return self

class AlertResponse(BaseModel):
    id: str
    sale_item_id: str
    assigned_advisor_id: str | None
    assigned_advisor_name: str | None = None
    assigned_advisor_email: str | None = None
    alert_date: date
    expected_repurchase_date: date
    status: str
    attempts_count: int
    next_action_date: date | None
    last_contact_at: datetime | None
    closed_at: datetime | None
    closure_reason: str | None
    created_at: datetime
    customer_id: str | None = None
    customer_dni: str | None = None
    customer_first_names: str | None = None
    customer_last_names: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    product_id: str | None = None
    product_code: str | None = None
    product_name: str | None = None
    original_sale_id: str | None = None
    original_sale_date: date | None = None
    seller_advisor_id: str | None = None
    seller_advisor_name: str | None = None
    seller_advisor_email: str | None = None

    model_config = {"from_attributes": True}


class ContactAttemptResponse(BaseModel):
    id: str
    alert_id: str
    advisor_id: str
    contacted_at: datetime
    channel: str
    result: str
    note: str | None
    next_action_date: date | None
    observation: str | None
    user_name: str | None
    parent_typification_name: str | None
    child_typification_name: str | None

    model_config = {"from_attributes": True}


class ManagedAlertResponse(AlertResponse):
    contact_attempts: list[ContactAttemptResponse]
