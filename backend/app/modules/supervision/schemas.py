from datetime import datetime

from pydantic import BaseModel, Field


class AssignmentCreate(BaseModel):
    assigned_advisor_id: str | None = None
    reason: str = Field(min_length=1, max_length=4000)


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
