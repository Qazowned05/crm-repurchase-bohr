from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.modules.alerts.models import Alert
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.sales.models import Sale, SaleItem

FINAL_STATUSES = {"RECOMPRA_LOGRADA", "NO_INTERESADO", "CANCELADO_POR_RECOMPRA", "CANCELADO_POR_ANULACION", "VENCIDO_NO_GESTIONADO"}


def active_alerts_query():
    return select(Alert).where(Alert.status.not_in(FINAL_STATUSES))


def assigned_advisor(customer: Customer, sale: Sale, db: Session) -> str | None:
    if customer.responsible_advisor_id:
        advisor = db.get(User, customer.responsible_advisor_id)
        if advisor and advisor.is_active:
            return advisor.id
    sale_advisor = db.get(User, sale.advisor_id)
    return sale_advisor.id if sale_advisor and sale_advisor.is_active else None


def generate_daily_alerts(run_date: date, db: Session, actor_id: str | None = None) -> dict[str, int]:
    """Generate scheduled alerts once, or one catch-up record for a past cycle."""
    created = pending = expired = 0
    rows = db.execute(
        select(SaleItem, Sale, Customer).join(Sale, Sale.id == SaleItem.sale_id).join(Customer, Customer.id == Sale.customer_id)
        .where(Sale.status == "CONFIRMADA")
    ).all()
    for item, sale, customer in rows:
        scheduled_dates = {item.expected_repurchase_date - timedelta(days=days) for days in item.rule_alert_days}
        dates_to_create = {run_date} if run_date in scheduled_dates else set()
        existing = set(db.scalars(select(Alert.alert_date).where(Alert.sale_item_id == item.id)))
        if not dates_to_create and item.expected_repurchase_date <= run_date and not existing:
            dates_to_create = {run_date}
        for alert_date in dates_to_create - existing:
            within_window = item.expected_repurchase_date >= run_date - timedelta(days=settings.alert_active_window_days)
            alert_status = "PENDIENTE" if within_window else "VENCIDO_NO_GESTIONADO"
            alert = Alert(sale_item_id=item.id, assigned_advisor_id=assigned_advisor(customer, sale, db), alert_date=alert_date,
                          expected_repurchase_date=item.expected_repurchase_date, status=alert_status,
                          closed_at=None if alert_status == "PENDIENTE" else datetime.now(timezone.utc))
            db.add(alert)
            db.flush()
            record_audit(db, actor_id=actor_id, entity_type="alert", entity_id=alert.id, action="GENERATED", after={"status": alert_status, "sale_item_id": item.id})
            created += 1
            pending += alert_status == "PENDIENTE"
            expired += alert_status == "VENCIDO_NO_GESTIONADO"
    return {"created": created, "pending": pending, "expired": expired}


def close_alerts_for_repurchase(customer_id: str, product_ids: set[str], new_sale_id: str, db: Session, actor_id: str | None, source_alert_id: str | None = None) -> None:
    alerts = db.scalars(
        active_alerts_query().join(SaleItem, SaleItem.id == Alert.sale_item_id).join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.customer_id == customer_id, SaleItem.product_id.in_(product_ids), Sale.id != new_sale_id)
    )
    for alert in alerts:
        alert.status = "RECOMPRA_LOGRADA" if alert.id == source_alert_id else "CANCELADO_POR_RECOMPRA"
        alert.closed_at = datetime.now(timezone.utc)
        record_audit(db, actor_id=actor_id, entity_type="alert", entity_id=alert.id, action="REPURCHASE_ACHIEVED" if alert.id == source_alert_id else "CANCELLED_BY_REPURCHASE", after={"status": alert.status})


def close_alerts_for_annulment(sale_id: str, db: Session, actor_id: str | None) -> None:
    alerts = db.scalars(active_alerts_query().join(SaleItem, SaleItem.id == Alert.sale_item_id).where(SaleItem.sale_id == sale_id))
    for alert in alerts:
        alert.status = "CANCELADO_POR_ANULACION"
        alert.closed_at = datetime.now(timezone.utc)
        record_audit(db, actor_id=actor_id, entity_type="alert", entity_id=alert.id, action="CANCELLED_BY_ANNULMENT", after={"status": alert.status})
