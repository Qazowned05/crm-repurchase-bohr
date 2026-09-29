from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginate_items
from app.dependencies import require_roles
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.alerts.schemas import AlertResponse
from app.modules.alerts.service import active_alerts_query, alert_response
from app.modules.alerts.service import recovery_alerts_query
from app.modules.auth.models import User
from app.modules.configuration.models import ContactTypification
from app.modules.customers.models import Customer
from app.modules.customers.routes import validate_responsible
from app.modules.sales.models import Sale, SaleItem
from app.modules.products.models import Product
from app.modules.supervision.models import AlertAssignmentHistory, CustomerAssignmentHistory
from app.modules.supervision.schemas import (
    AlertAssignmentHistoryResponse,
    AssignmentCreate,
    BulkAssignmentCreate,
    CustomerAssignmentHistoryResponse,
    RecoveryCustomerResponse,
)

router = APIRouter(prefix="/api/v1/supervision", tags=["supervision"])


def customer_or_404(customer_id: str, db: Session) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def alert_or_404(alert_id: str, db: Session) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def typification_descendant_codes(typification_id: str, db: Session) -> set[str]:
    root = db.get(ContactTypification, typification_id)
    if root is None:
        raise HTTPException(status_code=404, detail="Contact typification not found")
    ids = {root.id}
    pending = [root.id]
    while pending:
        children = list(db.scalars(select(ContactTypification).where(ContactTypification.parent_id.in_(pending))))
        pending = [child.id for child in children if child.id not in ids]
        ids.update(pending)
    return set(db.scalars(select(ContactTypification.code).where(ContactTypification.id.in_(ids))))


def record_alert_assignment(alert: Alert, advisor_id: str | None, reason: str, actor_id: str, db: Session) -> None:
    previous = alert.assigned_advisor_id
    alert.assigned_advisor_id = advisor_id
    db.add(AlertAssignmentHistory(
        alert_id=alert.id, previous_advisor_id=previous, assigned_advisor_id=advisor_id,
        reason=reason, assigned_by_user_id=actor_id,
    ))
    record_audit(db, actor_id=actor_id, entity_type="alert", entity_id=alert.id, action="ASSIGNED",
                 before={"assigned_advisor_id": previous}, after={"assigned_advisor_id": advisor_id, "reason": reason})


@router.post("/customers/{customer_id}/transfer")
def transfer_portfolio(
    customer_id: str, payload: AssignmentCreate,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
) -> dict:
    customer = customer_or_404(customer_id, db)
    validate_responsible(payload.assigned_advisor_id, db)
    reason = payload.reason.strip()
    previous = customer.responsible_advisor_id
    customer.responsible_advisor_id = payload.assigned_advisor_id
    db.add(CustomerAssignmentHistory(
        customer_id=customer.id, previous_advisor_id=previous, assigned_advisor_id=payload.assigned_advisor_id,
        reason=reason, assigned_by_user_id=current_user.id,
    ))
    record_audit(db, actor_id=current_user.id, entity_type="customer", entity_id=customer.id, action="PORTFOLIO_TRANSFERRED",
                 before={"responsible_advisor_id": previous}, after={"responsible_advisor_id": payload.assigned_advisor_id, "reason": reason})
    alerts = list(db.scalars(
        active_alerts_query()
        .join(SaleItem, SaleItem.id == Alert.sale_item_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.customer_id == customer.id)
    ))
    for alert in alerts:
        record_alert_assignment(alert, payload.assigned_advisor_id, reason, current_user.id, db)
    db.commit()
    return {"customer_id": customer.id, "assigned_advisor_id": customer.responsible_advisor_id, "transferred_alerts": len(alerts)}


@router.get("/customers/{customer_id}/assignment-history", response_model=None)
def customer_assignment_history(customer_id: str, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[CustomerAssignmentHistory] | dict:
    customer_or_404(customer_id, db)
    return paginate_items(list(db.scalars(select(CustomerAssignmentHistory).where(CustomerAssignmentHistory.customer_id == customer_id).order_by(CustomerAssignmentHistory.created_at))), page, page_size)


@router.get("/recovery-alerts")
def recovery_alerts(
    page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
) -> list[dict] | dict:
    rows = [alert_response(alert, db) for alert in db.scalars(recovery_alerts_query(db).order_by(Alert.alert_date))]
    return paginate_items(rows, page, page_size)


@router.get("/recovery-queue")
def recovery_queue(
    typification_id: str | None = None,
    min_days_overdue: int | None = Query(default=None, ge=0),
    max_days_overdue: int | None = Query(default=None, ge=0),
    q: str | None = None,
    product_id: str | None = None,
    alert_status: str | None = Query(default=None, alias="status"),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=200),
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")),
    db: Session = Depends(get_db),
) -> list[dict] | dict:
    if min_days_overdue is not None and max_days_overdue is not None and min_days_overdue > max_days_overdue:
        raise HTTPException(status_code=422, detail="min_days_overdue cannot exceed max_days_overdue")
    latest_result = (
        select(AlertContactAttempt.result).where(AlertContactAttempt.alert_id == Alert.id)
        .order_by(AlertContactAttempt.contacted_at.desc(), AlertContactAttempt.id.desc()).limit(1).correlate(Alert).scalar_subquery()
    )
    query = (
        recovery_alerts_query(db)
        .join(SaleItem, SaleItem.id == Alert.sale_item_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Customer, Customer.id == Sale.customer_id)
        .join(Product, Product.id == SaleItem.product_id)
        .with_only_columns(Alert, Sale, SaleItem, Customer, Product)
        .order_by(Customer.last_names, Customer.first_names, Alert.alert_date)
    )
    if typification_id is not None:
        query = query.where(latest_result.in_(typification_descendant_codes(typification_id, db)))
    today = date.today()
    if min_days_overdue is not None:
        query = query.where(Alert.alert_date <= today - timedelta(days=min_days_overdue))
    if max_days_overdue is not None:
        query = query.where(Alert.alert_date >= today - timedelta(days=max_days_overdue))
    if q:
        term = f"%{q.strip()}%"
        query = query.where(or_(
            Customer.dni.ilike(term), Customer.first_names.ilike(term), Customer.last_names.ilike(term),
            Customer.phone.ilike(term), Customer.email.ilike(term),
        ))
    if product_id:
        query = query.where(Product.id == product_id)
    if alert_status:
        query = query.where(Alert.status == alert_status)
    rows = db.execute(query).all()
    alert_ids = [alert.id for alert, *_ in rows]
    latest_attempts: dict[str, AlertContactAttempt] = {}
    if alert_ids:
        for attempt in db.scalars(select(AlertContactAttempt).where(AlertContactAttempt.alert_id.in_(alert_ids)).order_by(AlertContactAttempt.contacted_at.desc(), AlertContactAttempt.id.desc())):
            latest_attempts.setdefault(attempt.alert_id, attempt)
    grouped: dict[str, dict] = {}
    for alert, sale, item, customer, product in rows:
        assigned_advisor = db.get(User, alert.assigned_advisor_id) if alert.assigned_advisor_id else None
        customer_row = grouped.setdefault(customer.id, {
            "customer_id": customer.id, "dni": customer.dni, "first_names": customer.first_names,
            "last_names": customer.last_names, "phone": customer.phone, "alerts": [],
        })
        customer_row["alerts"].append({
            "id": alert.id, "status": alert.status, "alert_date": alert.alert_date,
            "expected_repurchase_date": alert.expected_repurchase_date, "attempts_count": alert.attempts_count,
            "next_action_date": alert.next_action_date, "last_contact_at": alert.last_contact_at,
            "assigned_advisor_id": alert.assigned_advisor_id,
            "assigned_advisor_name": assigned_advisor.full_name if assigned_advisor else None,
            "assigned_advisor_email": assigned_advisor.email if assigned_advisor else None,
            "latest_contact_typification": latest_attempts[alert.id].result if alert.id in latest_attempts else None,
            "latest_contact_date": latest_attempts[alert.id].contacted_at if alert.id in latest_attempts else None,
            "sale_id": sale.id, "sale_date": sale.sale_date, "product_id": product.id,
            "product_code": product.code, "product_name": product.name,
        })
    return paginate_items(list(grouped.values()), page, page_size)


@router.post("/alerts/{alert_id}/assign", response_model=AlertResponse)
def assign_recovery_alert(alert_id: str, payload: AssignmentCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    if payload.assigned_advisor_id is None:
        raise HTTPException(status_code=422, detail="An active advisor is required")
    validate_responsible(payload.assigned_advisor_id, db)
    alert = alert_or_404(alert_id, db)
    if alert.status not in {"PENDIENTE", "REPROGRAMADO", "SIN_RESPUESTA", "VENCIDO_NO_GESTIONADO"}:
        raise HTTPException(status_code=409, detail="Only recoverable alerts can be assigned")
    record_alert_assignment(alert, payload.assigned_advisor_id, payload.reason.strip(), current_user.id, db)
    alert.status, alert.closed_at = "REASIGNADO", None
    db.commit()
    db.refresh(alert)
    return alert_response(alert, db)


@router.post("/alerts/bulk-assign")
def bulk_assign_recovery_alerts(
    payload: BulkAssignmentCreate,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
) -> dict:
    if payload.assigned_advisor_id is None:
        raise HTTPException(status_code=422, detail="An active advisor is required")
    if len(set(payload.alert_ids)) != len(payload.alert_ids):
        raise HTTPException(status_code=422, detail="alert_ids must not contain duplicates")
    validate_responsible(payload.assigned_advisor_id, db)
    alerts = list(db.scalars(select(Alert).where(Alert.id.in_(payload.alert_ids)).with_for_update()))
    if len(alerts) != len(payload.alert_ids):
        raise HTTPException(status_code=404, detail="One or more alerts were not found")
    recoverable_ids = set(db.scalars(recovery_alerts_query(db).where(Alert.id.in_(payload.alert_ids)).with_only_columns(Alert.id)))
    if recoverable_ids != set(payload.alert_ids) or any(alert.status not in {"PENDIENTE", "REPROGRAMADO", "SIN_RESPUESTA", "VENCIDO_NO_GESTIONADO"} for alert in alerts):
        raise HTTPException(status_code=409, detail="Only alerts currently in the recovery scope can be assigned")
    reason = payload.reason.strip()
    for alert in alerts:
        record_alert_assignment(alert, payload.assigned_advisor_id, reason, current_user.id, db)
        alert.status, alert.closed_at = "REASIGNADO", None
    db.commit()
    return {"assigned_advisor_id": payload.assigned_advisor_id, "assigned_alert_ids": payload.alert_ids, "count": len(alerts)}


@router.get("/alerts/{alert_id}/assignment-history", response_model=None)
def alert_assignment_history(alert_id: str, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[AlertAssignmentHistory] | dict:
    alert_or_404(alert_id, db)
    return paginate_items(list(db.scalars(select(AlertAssignmentHistory).where(AlertAssignmentHistory.alert_id == alert_id).order_by(AlertAssignmentHistory.created_at))), page, page_size)
