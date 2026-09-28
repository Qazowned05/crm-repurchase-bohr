from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class ProductCreate(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=120)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    category: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None


class RuleCreate(BaseModel):
    duration_days: int = Field(gt=0, le=730)
    alert_days: list[int] = Field(min_length=1, max_length=5)
    effective_from: date
    medical_approval_reference: str = Field(min_length=2, max_length=120)
    medical_approved_by: str = Field(min_length=2, max_length=255)
    medical_approved_at: datetime

    @field_validator("alert_days")
    @classmethod
    def validate_unique_positive_days(cls, value: list[int]) -> list[int]:
        if any(day <= 0 for day in value) or len(set(value)) != len(value):
            raise ValueError("Alert days must be unique positive values")
        return sorted(value, reverse=True)

    def validate_for_duration(self) -> None:
        if any(day >= self.duration_days for day in self.alert_days):
            raise ValueError("Alert days must be lower than duration")


class RuleResponse(BaseModel):
    id: str
    product_id: str
    duration_days: int
    alert_days: list[int]
    effective_from: date
    medical_approval_reference: str
    medical_approved_by: str
    medical_approved_at: datetime
    created_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: str
    code: str
    name: str
    category: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
