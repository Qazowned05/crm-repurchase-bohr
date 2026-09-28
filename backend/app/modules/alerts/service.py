from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.modules.alerts.models import Alert
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.configuration.models import AlertOperationalSettings
from app.modules.sales.models import Sale, SaleItem

FINAL_STATUSES = {"RECOMPRA_LOGRADA", "NO_INTERESADO", "CANCELADO_POR_RECOMPRA", "CANCELADO_POR_ANULACION", "VENCIDO_NO_GESTIONADO"}
RECOVERABLE_FINAL_STATUSES = {"VENCIDO_NO_GESTIONADO"}


def active_alerts_query():
    return select(Alert).where(Alert.status.not_in(FINAL_STATUSES))


def alert_settings(db: Session) -> AlertOperationalSettings:
    record = db.get(AlertOperationalSettings, 1)
    if record is None:
        record = AlertOperationalSettings(id=1, advisor_visibility_days=settings.alert_active_window_days)
        db.add(record)
        db.flush()
    return record


def advisor_visible_alerts_query(db: Session, today: date | None = None):
    current_date = today or date.today()
    config = alert_settings(db)
    stale_cutoff = datetime.combine(current_date - timedelta(days=config.stale_days), datetime.min.time(), tzinfo=timezone.utc)
    return active_alerts_query().where(
        Alert.alert_date >= current_date - timedelta(days=config.advisor_visibility_days),
        Alert.attempts_count < config.maximum_attempts,
        func.coalesce(Alert.last_contact_at, Alert.created_at) >= stale_cutoff,
    )


def recovery_alerts_query(db: Session, today: date | None = None):
    current_date = today or date.today()
    config = alert_settings(db)
    stale_cutoff = datetime.combine(current_date - timedelta(days=config.stale_days), datetime.min.time(), tzinfo=timezone.utc)
    return select(Alert).where(
        Alert.status.not_in(FINAL_STATUSES - RECOVERABLE_FINAL_STATUSES),
        or_(
            Alert.assigned_advisor_id.is_(None),
            Alert.status.in_(RECOVERABLE_FINAL_STATUSES),
            Alert.alert_date < current_date - timedelta(days=config.advisor_visibility_days),
            Alert.attempts_count >= config.maximum_attempts,
            func.coalesce(Alert.last_contact_at, Alert.created_at) < stale_cutoff,
        ),
    )


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
    config = alert_settings(db)
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
            within_window = item.expected_repurchase_date >= run_date - timedelta(days=config.advisor_visibility_days)
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
