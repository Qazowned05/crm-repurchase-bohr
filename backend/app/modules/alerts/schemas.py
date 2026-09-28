from datetime import date, datetime
from pydantic import BaseModel, Field


class ContactAttemptCreate(BaseModel):
    channel: str = Field(min_length=1, max_length=20)
    result: str = Field(min_length=1, max_length=40)
    typification_id: str | None = None
    note: str | None = Field(default=None, max_length=4000)
    next_action_date: date | None = None
    close_alert: bool = False

class AlertResponse(BaseModel):
    id: str
    sale_item_id: str
    assigned_advisor_id: str | None
    alert_date: date
    expected_repurchase_date: date
    status: str
    attempts_count: int
    next_action_date: date | None
    last_contact_at: datetime | None
    closed_at: datetime | None
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

    model_config = {"from_attributes": True}
