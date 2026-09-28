from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SaleItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, le=100000)


class SaleCreate(BaseModel):
    customer_id: str
    sale_date: date
    notes: str | None = Field(default=None, max_length=4000)
    acquisition_channel: Literal["TV", "DIGITAL", "OTROS"] | None = None
    acquisition_channel_detail: str | None = Field(default=None, max_length=255)
    replaces_sale_id: str | None = None
    source_alert_id: str | None = None
    items: list[SaleItemCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_channel_detail(self) -> "SaleCreate":
        if self.acquisition_channel == "OTROS" and not (self.acquisition_channel_detail or "").strip():
            raise ValueError("Acquisition channel detail is required for OTROS")
        if self.acquisition_channel != "OTROS" and self.acquisition_channel_detail is not None:
            raise ValueError("Acquisition channel detail is only allowed for OTROS")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("A product may only appear once per sale")
        return self


class DuplicateReviewCreate(BaseModel):
    decision: Literal["APROBADA", "RECHAZADA"]
    reason: str = Field(min_length=3, max_length=4000)


class AnnulSaleCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=4000)


class AdvisorSalesMetricsResponse(BaseModel):
    confirmed_sales: int
    confirmed_items: int
    repurchase_sales: int
    repurchase_items: int


class SaleItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    rule_duration_days: int
    rule_alert_days: list[int]
    expected_repurchase_date: date
    purchase_type: str | None
    prior_confirmed_item_id: str | None

    model_config = {"from_attributes": True}


class SaleResponse(BaseModel):
    id: str
    customer_id: str
    advisor_id: str
    sale_date: date
    notes: str | None
    status: str
    acquisition_channel: str | None
    acquisition_channel_detail: str | None
    replaces_sale_id: str | None
    source_alert_id: str | None
    annulled_by_user_id: str | None
    annulment_reason: str | None
    annulled_at: datetime | None
    created_at: datetime
    items: list[SaleItemResponse]
