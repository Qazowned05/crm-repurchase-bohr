from datetime import date, datetime, timedelta, timezone
from threading import Event, Lock, Thread
import logging

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.configuration.models import ContactTypification
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.configuration.models import AlertOperationalSettings
from app.modules.products.models import Product
from app.modules.sales.models import Sale, SaleItem

FINAL_STATUSES = {"RECOMPRA_LOGRADA", "NO_INTERESADO", "CANCELADO_POR_RECOMPRA", "CANCELADO_POR_ANULACION", "CERRADO_POR_TIPIFICACION", "VENCIDO_NO_GESTIONADO"}
RECOVERABLE_FINAL_STATUSES = {"VENCIDO_NO_GESTIONADO"}
logger = logging.getLogger(__name__)
_generation_lock = Lock()
_scheduler_stop = Event()
_scheduler_thread: Thread | None = None


def active_alerts_query():
    return select(Alert).where(Alert.status.not_in(FINAL_STATUSES))


def alert_response(alert: Alert, db: Session) -> dict:
    item = db.get(SaleItem, alert.sale_item_id)
    sale = db.get(Sale, item.sale_id) if item else None
    customer = db.get(Customer, sale.customer_id) if sale else None
    product = db.get(Product, item.product_id) if item else None
    advisor = db.get(User, sale.advisor_id) if sale else None
    assigned_advisor = db.get(User, alert.assigned_advisor_id) if alert.assigned_advisor_id else None
    return {
        **{column.name: getattr(alert, column.name) for column in Alert.__table__.columns},
        "customer_id": customer.id if customer else None, "customer_dni": customer.dni if customer else None,
        "customer_first_names": customer.first_names if customer else None, "customer_last_names": customer.last_names if customer else None,
        "customer_phone": customer.phone if customer else None, "customer_email": customer.email if customer else None,
        "product_id": product.id if product else None, "product_code": product.code if product else None,
        "product_name": product.name if product else None, "original_sale_id": sale.id if sale else None,
        "original_sale_date": sale.sale_date if sale else None, "seller_advisor_id": advisor.id if advisor else None,
        "seller_advisor_name": advisor.full_name if advisor else None, "seller_advisor_email": advisor.email if advisor else None,
        "assigned_advisor_name": assigned_advisor.full_name if assigned_advisor else None,
        "assigned_advisor_email": assigned_advisor.email if assigned_advisor else None,
    }


def contact_attempt_response(attempt: AlertContactAttempt, db: Session) -> dict:
    typification = db.get(ContactTypification, attempt.typification_id) if attempt.typification_id else db.scalar(
        select(ContactTypification).where(ContactTypification.code == attempt.result)
    )
    parent = db.get(ContactTypification, typification.parent_id) if typification and typification.parent_id else None
    advisor = db.get(User, attempt.advisor_id)
    return {
        **{column.name: getattr(attempt, column.name) for column in AlertContactAttempt.__table__.columns if column.name != "typification_id"},
        "observation": attempt.note,
        "user_name": advisor.full_name if advisor else None,
        # A root typification is the parent classification; a descendant is the child classification.
        "parent_typification_name": parent.name if parent else (typification.name if typification else None),
        "child_typification_name": typification.name if parent else None,
    }


def managed_alert_response(alert: Alert, db: Session) -> dict:
    return {
        **alert_response(alert, db),
        "contact_attempts": [
            contact_attempt_response(attempt, db)
            for attempt in db.scalars(
                select(AlertContactAttempt)
                .where(AlertContactAttempt.alert_id == alert.id)
                .order_by(AlertContactAttempt.contacted_at, AlertContactAttempt.id)
            )
        ],
    }


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


def generate_daily_alerts(run_date: date, db: Session) -> dict[str, int]:
    """Generate one due-date alert per confirmed sale item, including missed cycles."""
    created = pending = expired = 0
    config = alert_settings(db)
    rows = db.execute(
        select(SaleItem, Sale, Customer).join(Sale, Sale.id == SaleItem.sale_id).join(Customer, Customer.id == Sale.customer_id)
        .where(Sale.status == "CONFIRMADA")
    ).all()
    for item, sale, customer in rows:
        if item.expected_repurchase_date > run_date:
            continue
        if db.scalar(select(Alert.id).where(Alert.sale_item_id == item.id)) is not None:
            continue
        within_window = item.expected_repurchase_date >= run_date - timedelta(days=config.advisor_visibility_days)
        alert_status = "PENDIENTE" if within_window else "VENCIDO_NO_GESTIONADO"
        alert = Alert(sale_item_id=item.id, assigned_advisor_id=assigned_advisor(customer, sale, db),
                      alert_date=item.expected_repurchase_date, expected_repurchase_date=item.expected_repurchase_date,
                      status=alert_status, closed_at=None if alert_status == "PENDIENTE" else datetime.now(timezone.utc))
        db.add(alert)
        db.flush()
        record_audit(db, actor_id=None, entity_type="alert", entity_id=alert.id, action="GENERATED", after={"status": alert_status, "sale_item_id": item.id, "generation_actor": "SYSTEM"})
        created += 1
        pending += alert_status == "PENDIENTE"
        expired += alert_status == "VENCIDO_NO_GESTIONADO"
    return {"created": created, "pending": pending, "expired": expired}


def run_alert_generation(run_date: date, db: Session) -> dict[str, int]:
    """Serialize generation and commit it before another caller can inspect alerts."""
    with _generation_lock:
        try:
            result = generate_daily_alerts(run_date, db)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise


def _run_scheduled_generation() -> None:
    db = SessionLocal()
    try:
        run_alert_generation(date.today(), db)
    except Exception:
        logger.exception("Automatic alert generation failed")
    finally:
        db.close()


def _scheduler_loop() -> None:
    _run_scheduled_generation()
    while not _scheduler_stop.wait(settings.alert_scheduler_poll_seconds):
        _run_scheduled_generation()


def start_alert_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = Thread(target=_scheduler_loop, name="alert-scheduler", daemon=True)
    _scheduler_thread.start()


def stop_alert_scheduler() -> None:
    global _scheduler_thread
    _scheduler_stop.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)
        _scheduler_thread = None


def close_alerts_for_repurchase(customer_id: str, product_ids: set[str], new_sale_id: str, db: Session, actor_id: str | None, source_alert_id: str | None = None) -> None:
    alerts = db.scalars(
        active_alerts_query().join(SaleItem, SaleItem.id == Alert.sale_item_id).join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.customer_id == customer_id, SaleItem.product_id.in_(product_ids), Sale.id != new_sale_id)
    )
    for alert in alerts:
        alert.status = "RECOMPRA_LOGRADA" if alert.id == source_alert_id else "CANCELADO_POR_RECOMPRA"
        alert.closed_at = datetime.now(timezone.utc)
        alert.closure_reason = f"RECOMPRA_CONFIRMADA: venta {new_sale_id}"
        record_audit(db, actor_id=actor_id, entity_type="alert", entity_id=alert.id, action="REPURCHASE_ACHIEVED" if alert.id == source_alert_id else "CANCELLED_BY_REPURCHASE", after={"status": alert.status, "closure_reason": alert.closure_reason, "repurchase_sale_id": new_sale_id})


def close_alerts_for_annulment(sale_id: str, db: Session, actor_id: str | None) -> None:
    alerts = db.scalars(active_alerts_query().join(SaleItem, SaleItem.id == Alert.sale_item_id).where(SaleItem.sale_id == sale_id))
    for alert in alerts:
        alert.status = "CANCELADO_POR_ANULACION"
        alert.closed_at = datetime.now(timezone.utc)
        alert.closure_reason = "VENTA_ORIGINAL_ANULADA"
        record_audit(db, actor_id=actor_id, entity_type="alert", entity_id=alert.id, action="CANCELLED_BY_ANNULMENT", after={"status": alert.status})
