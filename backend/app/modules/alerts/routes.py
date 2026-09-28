from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginate_items
from app.dependencies import get_current_user
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.alerts.schemas import AlertResponse, ContactAttemptCreate, ContactAttemptResponse, ManagedAlertResponse
from app.modules.alerts.service import FINAL_STATUSES, active_alerts_query, alert_response, contact_attempt_response, managed_alert_response, run_alert_generation
from app.modules.alerts.service import advisor_visible_alerts_query
from app.modules.auth.models import User
from app.modules.configuration.models import ContactTypification

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def alert_or_404(alert_id: str, db: Session) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def assert_alert_access(alert: Alert, user: User) -> None:
    if user.role == "ASESOR" and alert.assigned_advisor_id != user.id:
        raise HTTPException(status_code=403, detail="You can only manage your assigned alerts")


@router.get("/inbox")
def inbox(page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict] | dict:
    today = date.today()
    # Catch up after a restart or a system date change before reading the inbox.
    run_alert_generation(today, db)
    priority = case(
        (Alert.status == "REPROGRAMADO", 4),
        (Alert.next_action_date < today, 0),
        (Alert.alert_date < today, 1),
        (Alert.next_action_date == today, 2),
        else_=3,
    )
    query = (advisor_visible_alerts_query(db) if current_user.role == "ASESOR" else active_alerts_query()).order_by(priority, Alert.next_action_date, Alert.alert_date)
    if current_user.role == "ASESOR":
        query = query.where(Alert.assigned_advisor_id == current_user.id)
    return paginate_items([alert_response(alert, db) for alert in db.scalars(query)], page, page_size)


@router.get("/register")
def managed_register(
    date_from: date | None = None,
    date_to: date | None = None,
    state: str | None = Query(default=None, pattern="^(open-follow-up|closed)$"),
    page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict] | dict:
    """Persistent managed-alert register; unlike inbox, it includes follow-up and closed alerts."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from cannot exceed date_to")
    query = select(Alert)
    if current_user.role == "ASESOR":
        query = query.where(Alert.assigned_advisor_id == current_user.id)
    if date_from:
        query = query.where(Alert.alert_date >= date_from)
    if date_to:
        query = query.where(Alert.alert_date <= date_to)
    if state == "open-follow-up":
        query = query.where(Alert.status.not_in(FINAL_STATUSES))
    elif state == "closed":
        query = query.where(Alert.status.in_(FINAL_STATUSES))
    rows = [managed_alert_response(alert, db) for alert in db.scalars(query.order_by(Alert.alert_date.desc(), Alert.created_at.desc()))]
    return paginate_items(rows, page, page_size)


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    alert = alert_or_404(alert_id, db)
    assert_alert_access(alert, current_user)
    return alert_response(alert, db)


@router.get("/{alert_id}/attempts")
def list_attempts(alert_id: str, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict] | dict:
    alert = alert_or_404(alert_id, db)
    assert_alert_access(alert, current_user)
    rows = [contact_attempt_response(attempt, db) for attempt in db.scalars(select(AlertContactAttempt).where(AlertContactAttempt.alert_id == alert.id).order_by(AlertContactAttempt.contacted_at, AlertContactAttempt.id))]
    return paginate_items(rows, page, page_size)


@router.post("/{alert_id}/attempts", response_model=AlertResponse)
def add_attempt(alert_id: str, payload: ContactAttemptCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    alert = alert_or_404(alert_id, db)
    assert_alert_access(alert, current_user)
    if alert.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="A final alert cannot receive contact attempts")
    result = payload.result.strip().upper()
    fixed_results = {"RECOMPRA_REGISTRADA", "AUN_TIENE_PRODUCTO", "SOLICITA_SEGUIMIENTO", "SIN_RESPUESTA", "NO_INTERESADO", "DATOS_DE_CONTACTO_INCORRECTOS", "OTRO"}
    typification = None
    if payload.typification_id:
        typification = db.get(ContactTypification, payload.typification_id)
    if typification is None:
        typification = db.scalar(select(ContactTypification).where(
            (ContactTypification.id == payload.result.strip()) | (ContactTypification.code == result),
            ContactTypification.is_active.is_(True),
        ))
    if typification is not None and not typification.is_active:
        typification = None
    if typification is not None:
        result = typification.code
    if result not in fixed_results and typification is None:
        raise HTTPException(status_code=422, detail="Contact result is not an active typification")
    requires_next_action = result in {"AUN_TIENE_PRODUCTO", "SOLICITA_SEGUIMIENTO", "SIN_RESPUESTA"} or (typification and typification.requires_next_action)
    requires_note = result == "OTRO" or (typification and typification.requires_note)
    requires_close = bool(typification and typification.requires_close)
    if requires_next_action and payload.next_action_date is None:
        raise HTTPException(status_code=422, detail="A next action date is required for this result")
    if requires_note and not (payload.note or "").strip():
        raise HTTPException(status_code=422, detail="A descriptive note is required for this result")
    if result == "OTRO" and not payload.close_alert and payload.next_action_date is None:
        raise HTTPException(status_code=422, detail="OTRO requires a next action date or close_alert")
    if result == "RECOMPRA_REGISTRADA":
        raise HTTPException(status_code=422, detail="RECOMPRA_REGISTRADA requires recording a confirmed sale")
    attempt = AlertContactAttempt(alert_id=alert.id, advisor_id=current_user.id, channel=payload.channel.strip().upper(), result=result, typification_id=typification.id if typification else None,
                                  note=payload.note.strip() if payload.note else None, next_action_date=payload.next_action_date)
    db.add(attempt)
    alert.attempts_count += 1
    alert.last_contact_at = datetime.now(timezone.utc)
    alert.next_action_date = payload.next_action_date
    if result in {"AUN_TIENE_PRODUCTO", "SOLICITA_SEGUIMIENTO"}:
        alert.status = "REPROGRAMADO"
    elif result == "SIN_RESPUESTA":
        alert.status = "SIN_RESPUESTA"
    elif result == "NO_INTERESADO":
        alert.status, alert.closed_at = "NO_INTERESADO", datetime.now(timezone.utc)
        alert.closure_reason = "NO_INTERESADO"
    elif result == "DATOS_DE_CONTACTO_INCORRECTOS":
        alert.assigned_advisor_id, alert.status = None, "PENDIENTE"
    elif requires_close:
        alert.status, alert.closed_at = "CERRADO_POR_TIPIFICACION", datetime.now(timezone.utc)
        alert.closure_reason = f"TIPIFICACION_DE_CIERRE: {typification.name}"
    elif payload.close_alert:
        alert.status, alert.closed_at = "CANCELADO_POR_RECOMPRA", datetime.now(timezone.utc)
        alert.closure_reason = "CIERRE_MANUAL"
    record_audit(db, actor_id=current_user.id, entity_type="alert", entity_id=alert.id, action="CONTACT_ATTEMPT", after={"result": result, "status": alert.status, "next_action_date": str(alert.next_action_date) if alert.next_action_date else None})
    db.commit()
    return alert_response(alert, db)
