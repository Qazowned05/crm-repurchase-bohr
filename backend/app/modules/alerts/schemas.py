from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ContactAttemptCreate(BaseModel):
    channel: Literal["LLAMADA", "WHATSAPP", "EMAIL", "OTRO"]
    result: Literal["RECOMPRA_REGISTRADA", "AUN_TIENE_PRODUCTO", "SOLICITA_SEGUIMIENTO", "SIN_RESPUESTA", "NO_INTERESADO", "DATOS_DE_CONTACTO_INCORRECTOS", "OTRO"]
    note: str | None = Field(default=None, max_length=4000)
    next_action_date: date | None = None
    close_alert: bool = False

    @model_validator(mode="after")
    def validate_result_requirements(self) -> "ContactAttemptCreate":
        if self.result in {"AUN_TIENE_PRODUCTO", "SOLICITA_SEGUIMIENTO", "SIN_RESPUESTA"} and self.next_action_date is None:
            raise ValueError("A next action date is required for this result")
        if self.result == "OTRO" and not (self.note or "").strip():
            raise ValueError("A descriptive note is required for OTRO")
        if self.result == "OTRO" and not self.close_alert and self.next_action_date is None:
            raise ValueError("OTRO requires a next action date or close_alert")
        return self


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


class GenerationResponse(BaseModel):
    run_date: date
    created: int
    pending: int
    expired: int
