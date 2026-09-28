from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ContactTypificationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True
    requires_next_action: bool = False
    requires_note: bool = False
    requires_close: bool = False

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Code cannot be blank")
        return value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class ContactTypificationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    requires_next_action: bool | None = None
    requires_note: bool | None = None
    requires_close: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class ContactTypificationResponse(ContactTypificationCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertOperationalSettingsUpdate(BaseModel):
    advisor_visibility_days: int = Field(ge=1, le=3650)
    maximum_attempts: int = Field(ge=1, le=100)
    stale_days: int = Field(ge=1, le=3650)


class AlertOperationalSettingsResponse(AlertOperationalSettingsUpdate):
    updated_at: datetime

    model_config = {"from_attributes": True}
