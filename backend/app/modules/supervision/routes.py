from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.dependencies import require_roles
from app.modules.alerts.models import Alert
from app.modules.alerts.schemas import AlertResponse
from app.modules.alerts.service import active_alerts_query
from app.modules.alerts.service import recovery_alerts_query
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.customers.routes import validate_responsible
from app.modules.sales.models import Sale, SaleItem
from app.modules.products.models import Product
from app.modules.supervision.models import AlertAssignmentHistory, CustomerAssignmentHistory
from app.modules.supervision.schemas import (
    AlertAssignmentHistoryResponse,
    AssignmentCreate,
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


@router.get("/customers/{customer_id}/assignment-history", response_model=list[CustomerAssignmentHistoryResponse])
def customer_assignment_history(customer_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[CustomerAssignmentHistory]:
    customer_or_404(customer_id, db)
    return list(db.scalars(select(CustomerAssignmentHistory).where(CustomerAssignmentHistory.customer_id == customer_id).order_by(CustomerAssignmentHistory.created_at)))


@router.get("/recovery-alerts", response_model=list[AlertResponse])
def recovery_alerts(current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[Alert]:
    return list(db.scalars(recovery_alerts_query(db).order_by(Alert.alert_date)))


@router.get("/recovery-queue", response_model=list[RecoveryCustomerResponse])
def recovery_queue(current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        recovery_alerts_query(db)
        .join(SaleItem, SaleItem.id == Alert.sale_item_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Customer, Customer.id == Sale.customer_id)
        .join(Product, Product.id == SaleItem.product_id)
        .with_only_columns(Alert, Sale, SaleItem, Customer, Product)
        .order_by(Customer.last_names, Customer.first_names, Alert.alert_date)
    ).all()
    grouped: dict[str, dict] = {}
    for alert, sale, item, customer, product in rows:
        customer_row = grouped.setdefault(customer.id, {
            "customer_id": customer.id, "dni": customer.dni, "first_names": customer.first_names,
            "last_names": customer.last_names, "phone": customer.phone, "alerts": [],
        })
        customer_row["alerts"].append({
            "id": alert.id, "status": alert.status, "alert_date": alert.alert_date,
            "expected_repurchase_date": alert.expected_repurchase_date, "attempts_count": alert.attempts_count,
            "next_action_date": alert.next_action_date, "last_contact_at": alert.last_contact_at,
            "sale_id": sale.id, "sale_date": sale.sale_date, "product_id": product.id,
            "product_code": product.code, "product_name": product.name,
        })
    return list(grouped.values())


@router.post("/alerts/{alert_id}/assign", response_model=AlertResponse)
def assign_recovery_alert(alert_id: str, payload: AssignmentCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Alert:
    if payload.assigned_advisor_id is None:
        raise HTTPException(status_code=422, detail="An active advisor is required")
    validate_responsible(payload.assigned_advisor_id, db)
    alert = alert_or_404(alert_id, db)
    if alert.status not in {"PENDIENTE", "REPROGRAMADO", "SIN_RESPUESTA", "VENCIDO_NO_GESTIONADO"}:
        raise HTTPException(status_code=409, detail="Only recoverable alerts can be assigned")
    record_alert_assignment(alert, payload.assigned_advisor_id, payload.reason.strip(), current_user.id, db)
    if alert.status == "VENCIDO_NO_GESTIONADO":
        alert.status, alert.closed_at = "PENDIENTE", None
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/alerts/{alert_id}/assignment-history", response_model=list[AlertAssignmentHistoryResponse])
def alert_assignment_history(alert_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[AlertAssignmentHistory]:
    alert_or_404(alert_id, db)
    return list(db.scalars(select(AlertAssignmentHistory).where(AlertAssignmentHistory.alert_id == alert_id).order_by(AlertAssignmentHistory.created_at)))
