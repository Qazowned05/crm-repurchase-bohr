from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.dependencies import require_roles
from app.modules.alerts.models import Alert
from app.modules.alerts.schemas import AlertResponse
from app.modules.alerts.service import active_alerts_query
from app.modules.auth.models import User
from app.modules.customers.models import Customer
from app.modules.customers.routes import validate_responsible
from app.modules.sales.models import Sale, SaleItem
from app.modules.supervision.models import AlertAssignmentHistory, CustomerAssignmentHistory
from app.modules.supervision.schemas import (
    AlertAssignmentHistoryResponse,
    AssignmentCreate,
    CustomerAssignmentHistoryResponse,
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
    return list(db.scalars(active_alerts_query().where(Alert.assigned_advisor_id.is_(None)).order_by(Alert.alert_date)))


@router.post("/alerts/{alert_id}/assign", response_model=AlertResponse)
def assign_recovery_alert(alert_id: str, payload: AssignmentCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Alert:
    if payload.assigned_advisor_id is None:
        raise HTTPException(status_code=422, detail="An active advisor is required")
    validate_responsible(payload.assigned_advisor_id, db)
    alert = alert_or_404(alert_id, db)
    if alert.status not in {"PENDIENTE", "REPROGRAMADO", "SIN_RESPUESTA"}:
        raise HTTPException(status_code=409, detail="Only active alerts can be assigned")
    record_alert_assignment(alert, payload.assigned_advisor_id, payload.reason.strip(), current_user.id, db)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/alerts/{alert_id}/assignment-history", response_model=list[AlertAssignmentHistoryResponse])
def alert_assignment_history(alert_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[AlertAssignmentHistory]:
    alert_or_404(alert_id, db)
    return list(db.scalars(select(AlertAssignmentHistory).where(AlertAssignmentHistory.alert_id == alert_id).order_by(AlertAssignmentHistory.created_at)))
