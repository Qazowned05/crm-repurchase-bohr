import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_roles
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.products.models import Product
from app.modules.sales.models import Sale, SaleItem
from app.modules.reports.schemas import AlertsReportResponse, MetricsResponse, SalesReportResponse

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def csv_response(rows: list[dict], filename: str) -> Response:
    output = StringIO()
    fields = list(rows[0]) if rows else []
    writer = csv.DictWriter(output, fieldnames=fields)
    if fields:
        writer.writeheader()
        writer.writerows(rows)
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def sales_rows(start_date: date | None, end_date: date | None, db: Session) -> list[dict]:
    query = (
        select(Sale, SaleItem, Product, Customer)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .join(Customer, Customer.id == Sale.customer_id)
        .where(Sale.status == "CONFIRMADA")
    )
    if start_date:
        query = query.where(Sale.sale_date >= start_date)
    if end_date:
        query = query.where(Sale.sale_date <= end_date)
    grouped: dict[tuple, dict] = {}
    for sale, item, product, customer in db.execute(query):
        key = (product.id, sale.acquisition_channel, sale.advisor_id, customer.responsible_advisor_id)
        row = grouped.setdefault(key, {
            "product_id": product.id, "product": product.name, "channel": sale.acquisition_channel or "SIN_CANAL",
            "sale_advisor_id": sale.advisor_id, "current_portfolio_owner_id": customer.responsible_advisor_id,
            "confirmed_sales": 0, "repurchases": 0, "units": 0,
        })
        row["confirmed_sales"] += 1
        row["repurchases"] += item.purchase_type == "RECOMPRA"
        row["units"] += item.quantity
    return list(grouped.values())


@router.get("/sales", response_model=SalesReportResponse)
def sales_report(
    start_date: date | None = None, end_date: date | None = None, export: bool = False,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
):
    rows = sales_rows(start_date, end_date, db)
    return csv_response(rows, "sales_report.csv") if export else {"start_date": start_date, "end_date": end_date, "rows": rows}


@router.get("/sales.csv")
def sales_report_csv(start_date: date | None = None, end_date: date | None = None, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Response:
    return csv_response(sales_rows(start_date, end_date, db), "sales_report.csv")


def alert_rows(start_date: date | None, end_date: date | None, db: Session) -> list[dict]:
    query = select(Alert).where(Alert.status != "CANCELADO_POR_ANULACION")
    if start_date:
        query = query.where(Alert.alert_date >= start_date)
    if end_date:
        query = query.where(Alert.alert_date <= end_date)
    alerts = list(db.scalars(query))
    attempt_advisors = dict(db.execute(
        select(AlertContactAttempt.alert_id, AlertContactAttempt.advisor_id).order_by(AlertContactAttempt.alert_id, AlertContactAttempt.contacted_at)
    ).all())
    rows: dict[tuple, dict] = {}
    for alert in alerts:
        handling_advisor = attempt_advisors.get(alert.id, alert.assigned_advisor_id)
        key = (alert.status, handling_advisor)
        row = rows.setdefault(key, {"status": alert.status, "alert_handling_advisor_id": handling_advisor, "alerts": 0, "pending": 0, "expired": 0, "attended": 0})
        row["alerts"] += 1
        row["pending"] += alert.status in {"PENDIENTE", "REPROGRAMADO", "SIN_RESPUESTA"}
        row["expired"] += alert.status == "VENCIDO_NO_GESTIONADO"
        row["attended"] += alert.attempts_count > 0
    return list(rows.values())


@router.get("/alerts", response_model=AlertsReportResponse)
def alerts_report(start_date: date | None = None, end_date: date | None = None, export: bool = False, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)):
    rows = alert_rows(start_date, end_date, db)
    return csv_response(rows, "alerts_report.csv") if export else {"start_date": start_date, "end_date": end_date, "rows": rows}


@router.get("/alerts.csv")
def alerts_report_csv(start_date: date | None = None, end_date: date | None = None, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Response:
    return csv_response(alert_rows(start_date, end_date, db), "alerts_report.csv")


@router.get("/metrics", response_model=MetricsResponse)
def metrics(start_date: date | None = None, end_date: date | None = None, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    alerts_query = select(Alert).where(Alert.status != "CANCELADO_POR_ANULACION")
    if start_date:
        alerts_query = alerts_query.where(Alert.alert_date >= start_date)
    if end_date:
        alerts_query = alerts_query.where(Alert.alert_date <= end_date)
    alerts = list(db.scalars(alerts_query))
    attended = sum(alert.attempts_count > 0 for alert in alerts)
    repurchased = sum(alert.status == "RECOMPRA_LOGRADA" for alert in alerts)
    items_query = select(SaleItem, Sale.sale_date).join(Sale, Sale.id == SaleItem.sale_id).where(Sale.status == "CONFIRMADA", SaleItem.prior_confirmed_item_id.is_not(None))
    if start_date:
        items_query = items_query.where(Sale.sale_date >= start_date)
    if end_date:
        items_query = items_query.where(Sale.sale_date <= end_date)
    intervals = []
    for item, sale_date in db.execute(items_query):
        previous_date = db.scalar(select(Sale.sale_date).join(SaleItem, SaleItem.sale_id == Sale.id).where(SaleItem.id == item.prior_confirmed_item_id, Sale.status == "CONFIRMADA"))
        if previous_date:
            intervals.append((sale_date - previous_date).days)
    total = len(alerts)
    return {
        "alerts_considered": total,
        "contact_rate": attended / total if total else 0,
        "repurchase_rate": repurchased / total if total else 0,
        "average_days_between_purchases": sum(intervals) / len(intervals) if intervals else None,
    }
