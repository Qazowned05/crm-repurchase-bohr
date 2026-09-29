from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SalesReportRow(BaseModel):
    product_id: str
    product: str
    channel: str
    sale_advisor_id: str
    current_portfolio_owner_id: str | None
    confirmed_sales: int
    repurchases: int
    units: int


class SalesReportResponse(BaseModel):
    start_date: date | None
    end_date: date | None
    rows: list[SalesReportRow]
    page: int | None = None
    page_size: int | None = None
    total: int | None = None
    pages: int | None = None


class AlertsReportRow(BaseModel):
    status: str
    alert_handling_advisor_id: str | None
    alerts: int
    pending: int
    expired: int
    attended: int


class AlertsReportResponse(BaseModel):
    start_date: date | None
    end_date: date | None
    rows: list[AlertsReportRow]
    page: int | None = None
    page_size: int | None = None
    total: int | None = None
    pages: int | None = None


class MetricsResponse(BaseModel):
    alerts_considered: int
    contact_rate: float
    repurchase_rate: float
    average_days_between_purchases: float | None
    repurchase_denominator: int
    advisor_ranking: list[dict]
    attention_typifications: list[dict]
    total_revenue: Decimal
    regular_revenue: Decimal
    repurchase_revenue: Decimal
    total_units_sold: int
    confirmed_sales: int
    average_ticket: Decimal
    top_products_by_units: list[dict]
    top_products_by_revenue: list[dict]
