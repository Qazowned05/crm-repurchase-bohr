from datetime import date, datetime

from pydantic import BaseModel, Field


class AssignmentCreate(BaseModel):
    assigned_advisor_id: str | None = None
    reason: str = Field(min_length=1, max_length=4000)


class BulkAssignmentCreate(AssignmentCreate):
    alert_ids: list[str] = Field(min_length=1, max_length=200)


class CustomerAssignmentHistoryResponse(BaseModel):
    id: str
    customer_id: str
    previous_advisor_id: str | None
    assigned_advisor_id: str | None
    reason: str
    assigned_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertAssignmentHistoryResponse(BaseModel):
    id: str
    alert_id: str
    previous_advisor_id: str | None
    assigned_advisor_id: str | None
    reason: str
    assigned_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RecoveryAlertResponse(BaseModel):
    id: str
    status: str
    alert_date: date
    expected_repurchase_date: date
    attempts_count: int
    next_action_date: date | None
    last_contact_at: datetime | None
    latest_contact_typification: str | None
    latest_contact_date: datetime | None
    sale_id: str
    sale_date: date
    product_id: str
    product_code: str
    product_name: str
    assigned_advisor_id: str | None = None
    assigned_advisor_name: str | None = None
    assigned_advisor_email: str | None = None


class RecoveryCustomerResponse(BaseModel):
    customer_id: str
    dni: str
    first_names: str
    last_names: str
    phone: str
    alerts: list[RecoveryAlertResponse]
