from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#176b87", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Campaign name cannot be blank")
        return value

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.upper()


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class CampaignResponse(CampaignCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
