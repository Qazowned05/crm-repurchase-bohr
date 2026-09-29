from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ProductCreate(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=180)
    brand_id: str
    category_id: str
    unit_price: Decimal = Field(default=Decimal("1.00"), gt=0, max_digits=12, decimal_places=2)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    brand_id: str | None = None
    category_id: str | None = None
    is_active: bool | None = None
    unit_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class RuleCreate(BaseModel):
    duration_days: int = Field(gt=0, le=730)
    alert_days: list[int] = Field(min_length=1, max_length=5)
    effective_from: date

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
    created_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: str
    code: str
    name: str
    brand_id: str
    category_id: str
    brand_name: str
    category_name: str
    unit_price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CatalogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class CatalogUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class CatalogResponse(CatalogCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
