import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.pagination import paginate_items
from app.dependencies import require_roles
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.configuration.models import ContactTypification
from app.modules.products.models import Product
from app.modules.sales.models import Sale, SaleItem
from app.modules.supervision.models import AlertAssignmentHistory
from app.modules.reports.schemas import AlertsReportResponse, MetricsResponse, SalesReportResponse

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def excel_value(value: object) -> object:
    # Excel does not support timezone-aware datetimes, while audit/contact data is UTC-aware.
    if isinstance(value, datetime) and value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    # Treat user-controlled values as literal text rather than Excel formulas.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def excel_response(sheets: dict[str, list[dict]], filename: str) -> StreamingResponse:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets.items():
        sheet = workbook.create_sheet(title)
        headers = list(rows[0]) if rows else []
        if headers:
            sheet.append(headers)
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            for row in rows:
                sheet.append([excel_value(row[field]) for field in headers])
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
        else:
            sheet.append(["Sin datos"])
    output = BytesIO(); workbook.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/operation.xlsx")
def operation_excel(
    start_date: date | None = None, end_date: date | None = None,
    customer_id: str | None = None, product_id: str | None = None, sale_advisor_id: str | None = None,
    portfolio_advisor_id: str | None = None, channel: str | None = None, purchase_type: str | None = None,
    alert_status: str | None = None, assigned_advisor_id: str | None = None,
    department: str | None = None, province: str | None = None, district: str | None = None,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
) -> StreamingResponse:
    sales_query = select(Sale, SaleItem, Product, Customer).join(SaleItem, SaleItem.sale_id == Sale.id).join(Product, Product.id == SaleItem.product_id).join(Customer, Customer.id == Sale.customer_id).where(Sale.status == "CONFIRMADA")
    if start_date: sales_query = sales_query.where(Sale.sale_date >= start_date)
    if end_date: sales_query = sales_query.where(Sale.sale_date <= end_date)
    if customer_id: sales_query = sales_query.where(Customer.id == customer_id)
    if product_id: sales_query = sales_query.where(Product.id == product_id)
    if sale_advisor_id: sales_query = sales_query.where(Sale.advisor_id == sale_advisor_id)
    if portfolio_advisor_id: sales_query = sales_query.where(Customer.responsible_advisor_id == portfolio_advisor_id)
    if channel: sales_query = sales_query.where(Sale.acquisition_channel == channel)
    if purchase_type: sales_query = sales_query.where(SaleItem.purchase_type == purchase_type)
    if department: sales_query = sales_query.where(Customer.department == department)
    if province: sales_query = sales_query.where(Customer.province == province)
    if district: sales_query = sales_query.where(Customer.district == district)
    reassignment_history: dict[str, AlertAssignmentHistory] = {}
    for history in db.scalars(
        select(AlertAssignmentHistory)
        .where(AlertAssignmentHistory.previous_advisor_id.is_not(None))
        .order_by(AlertAssignmentHistory.created_at.desc())
    ):
        reassignment_history.setdefault(history.alert_id, history)
    sales = []
    for sale, item, product, customer in db.execute(sales_query):
        reassignment = reassignment_history.get(sale.source_alert_id)
        sales.append({"sale_id": sale.id, "sale_date": sale.sale_date, "sale_advisor_id": sale.advisor_id, "customer_dni": customer.dni, "customer": f"{customer.first_names} {customer.last_names}", "department": customer.department, "province": customer.province, "district": customer.district, "product_code": product.code, "product": product.name, "quantity": item.quantity, "unit_price": item.unit_price, "amount": (item.unit_price or Decimal("0")) * item.quantity, "purchase_type": item.purchase_type, "channel": sale.acquisition_channel, "source_alert_id": sale.source_alert_id, "repurchase_after_reassignment": "SI" if reassignment else "NO", "reassigned_from_advisor_id": reassignment.previous_advisor_id if reassignment else None, "reassigned_to_advisor_id": reassignment.assigned_advisor_id if reassignment else None, "reassignment_reason": reassignment.reason if reassignment else None})
    alerts_query = select(Alert, Sale, SaleItem, Product, Customer).join(SaleItem, SaleItem.id == Alert.sale_item_id).join(Sale, Sale.id == SaleItem.sale_id).join(Product, Product.id == SaleItem.product_id).join(Customer, Customer.id == Sale.customer_id)
    if start_date: alerts_query = alerts_query.where(Alert.alert_date >= start_date)
    if end_date: alerts_query = alerts_query.where(Alert.alert_date <= end_date)
    if customer_id: alerts_query = alerts_query.where(Customer.id == customer_id)
    if product_id: alerts_query = alerts_query.where(Product.id == product_id)
    if alert_status: alerts_query = alerts_query.where(Alert.status == alert_status)
    if assigned_advisor_id: alerts_query = alerts_query.where(Alert.assigned_advisor_id == assigned_advisor_id)
    if portfolio_advisor_id: alerts_query = alerts_query.where(Customer.responsible_advisor_id == portfolio_advisor_id)
    if department: alerts_query = alerts_query.where(Customer.department == department)
    if province: alerts_query = alerts_query.where(Customer.province == province)
    if district: alerts_query = alerts_query.where(Customer.district == district)
    alerts = []
    alert_ids = []
    for alert, sale, item, product, customer in db.execute(alerts_query):
        alert_ids.append(alert.id)
        alerts.append({"alert_id": alert.id, "alert_date": alert.alert_date, "expected_repurchase_date": alert.expected_repurchase_date, "status": alert.status, "assigned_advisor_id": alert.assigned_advisor_id, "attempts": alert.attempts_count, "next_action_date": alert.next_action_date, "customer_dni": customer.dni, "customer": f"{customer.first_names} {customer.last_names}", "product": product.name, "original_sale_date": sale.sale_date})
    attempts = []
    if alert_ids:
        for attempt in db.scalars(select(AlertContactAttempt).where(AlertContactAttempt.alert_id.in_(alert_ids)).order_by(AlertContactAttempt.contacted_at)):
            attempts.append({"alert_id": attempt.alert_id, "contacted_at": attempt.contacted_at, "advisor_id": attempt.advisor_id, "channel": attempt.channel, "result": attempt.result, "note": attempt.note, "next_action_date": attempt.next_action_date})
    return excel_response({"Ventas": sales, "Alertas": alerts, "Gestiones": attempts}, "reporte_operacion.xlsx")


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
    page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
):
    rows = sales_rows(start_date, end_date, db)
    if export:
        return csv_response(rows, "sales_report.csv")
    paged = paginate_items(rows, page, page_size)
    return {"start_date": start_date, "end_date": end_date, "rows": paged if isinstance(paged, list) else paged["items"], **({} if isinstance(paged, list) else {key: paged[key] for key in ("page", "page_size", "total", "pages")})}


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
def alerts_report(start_date: date | None = None, end_date: date | None = None, export: bool = False, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)):
    rows = alert_rows(start_date, end_date, db)
    if export:
        return csv_response(rows, "alerts_report.csv")
    paged = paginate_items(rows, page, page_size)
    return {"start_date": start_date, "end_date": end_date, "rows": paged if isinstance(paged, list) else paged["items"], **({} if isinstance(paged, list) else {key: paged[key] for key in ("page", "page_size", "total", "pages")})}


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
    # An attended alert has at least one persisted contact attempt. This is the
    # denominator for conversion, so unworked alerts cannot inflate the rate.
    alert_ids = {alert.id for alert in alerts}
    attempts = list(db.scalars(select(AlertContactAttempt).where(AlertContactAttempt.alert_id.in_(alert_ids)))) if alert_ids else []
    attended_ids = {attempt.alert_id for attempt in attempts}
    attended = len(attended_ids)
    repurchased = sum(alert.status == "RECOMPRA_LOGRADA" for alert in alerts)
    sales_items_query = (
        select(Sale, SaleItem, Product)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(Sale.status == "CONFIRMADA")
    )
    if start_date:
        sales_items_query = sales_items_query.where(Sale.sale_date >= start_date)
    if end_date:
        sales_items_query = sales_items_query.where(Sale.sale_date <= end_date)
    product_sales: dict[str, dict] = {}
    sale_totals: dict[str, Decimal] = {}
    total_revenue = Decimal("0")
    repurchase_revenue = Decimal("0")
    revenue_by_advisor: dict[str, Decimal] = {}
    regular_revenue_by_advisor: dict[str, Decimal] = {}
    repurchase_revenue_by_advisor: dict[str, Decimal] = {}
    total_units_sold = 0
    for sale, item, product in db.execute(sales_items_query):
        amount = (item.unit_price or Decimal("0")) * item.quantity
        row = product_sales.setdefault(
            product.id,
            {"product_id": product.id, "product_name": product.name, "product_code": product.code, "units": 0, "revenue": Decimal("0")},
        )
        row["units"] += item.quantity
        row["revenue"] += amount
        sale_totals[sale.id] = sale_totals.get(sale.id, Decimal("0")) + amount
        total_revenue += amount
        revenue_by_advisor[sale.advisor_id] = revenue_by_advisor.get(sale.advisor_id, Decimal("0")) + amount
        if item.purchase_type == "RECOMPRA":
            repurchase_revenue += amount
            repurchase_revenue_by_advisor[sale.advisor_id] = repurchase_revenue_by_advisor.get(sale.advisor_id, Decimal("0")) + amount
        else:
            regular_revenue_by_advisor[sale.advisor_id] = regular_revenue_by_advisor.get(sale.advisor_id, Decimal("0")) + amount
        total_units_sold += item.quantity
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
    advisors = {advisor.id: advisor for advisor in db.scalars(select(User).where(User.role == "ASESOR"))}
    ranking: dict[str, dict] = {
        advisor_id: {"advisor_id": advisor_id, "advisor_name": advisor.full_name, "confirmed_repurchases": 0, "regular_revenue": regular_revenue_by_advisor.get(advisor_id, Decimal("0")), "repurchase_revenue": repurchase_revenue_by_advisor.get(advisor_id, Decimal("0")), "total_revenue": revenue_by_advisor.get(advisor_id, Decimal("0")),
                     "managed_alerts": 0, "contact_attempts": 0, "closed_alerts": 0}
        for advisor_id, advisor in advisors.items()
    }
    repurchase_query = (
        select(Sale.advisor_id, Sale.id)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .where(Sale.status == "CONFIRMADA", SaleItem.purchase_type == "RECOMPRA")
        .distinct()
    )
    if start_date:
        repurchase_query = repurchase_query.where(Sale.sale_date >= start_date)
    if end_date:
        repurchase_query = repurchase_query.where(Sale.sale_date <= end_date)
    for advisor_id, _ in db.execute(repurchase_query):
        if advisor_id in ranking:
            ranking[advisor_id]["confirmed_repurchases"] += 1
    for attempt in attempts:
        if attempt.advisor_id in ranking:
            ranking[attempt.advisor_id]["contact_attempts"] += 1
    # Count distinct alerts managed by each advisor, not just repeated attempts.
    for row in ranking.values():
        advisor_attempts = {attempt.alert_id for attempt in attempts if attempt.advisor_id == row["advisor_id"]}
        row["managed_alerts"] = len(advisor_attempts)
        row["closed_alerts"] = sum(
            alert.id in advisor_attempts and alert.status in {"RECOMPRA_LOGRADA", "COMPRA_OTRO_PRODUCTO", "NO_INTERESADO", "CANCELADO_POR_RECOMPRA", "CERRADO_POR_TIPIFICACION"}
            for alert in alerts
        )

    typifications = {typification.id: typification for typification in db.scalars(select(ContactTypification))}
    typification_counts: dict[str, dict] = {}
    for attempt in attempts:
        node = typifications.get(attempt.typification_id) if attempt.typification_id else None
        if node is None:
            continue
        visited: set[str] = set()
        while node.parent_id and node.parent_id not in visited:
            visited.add(node.id)
            parent = typifications.get(node.parent_id)
            if parent is None:
                break
            node = parent
        bucket = typification_counts.setdefault(node.id, {"typification_id": node.id, "typification_code": node.code, "typification_name": node.name, "attempts": 0})
        bucket["attempts"] += 1
    return {
        "alerts_considered": total,
        "contact_rate": attended / total if total else 0,
        "repurchase_rate": repurchased / attended if attended else 0,
        "repurchase_denominator": attended,
        "average_days_between_purchases": sum(intervals) / len(intervals) if intervals else None,
        "advisor_ranking": sorted(ranking.values(), key=lambda row: (-row["total_revenue"], -row["repurchase_revenue"], -row["managed_alerts"], row["advisor_name"])),
        "attention_typifications": sorted(typification_counts.values(), key=lambda row: (-row["attempts"], row["typification_name"])),
        "total_revenue": total_revenue,
        "regular_revenue": total_revenue - repurchase_revenue,
        "repurchase_revenue": repurchase_revenue,
        "total_units_sold": total_units_sold,
        "confirmed_sales": len(sale_totals),
        "average_ticket": total_revenue / len(sale_totals) if sale_totals else Decimal("0"),
        "top_products_by_units": sorted(product_sales.values(), key=lambda row: (-row["units"], -row["revenue"], row["product_name"]))[:5],
        "top_products_by_revenue": sorted(product_sales.values(), key=lambda row: (-row["revenue"], -row["units"], row["product_name"]))[:5],
    }
