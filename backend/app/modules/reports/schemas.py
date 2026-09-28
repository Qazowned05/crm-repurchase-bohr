from datetime import date

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


class MetricsResponse(BaseModel):
    alerts_considered: int
    contact_rate: float
    repurchase_rate: float
    average_days_between_purchases: float | None
