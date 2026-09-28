from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.dependencies import get_current_user, require_roles
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.alerts.schemas import AlertResponse, ContactAttemptCreate, ContactAttemptResponse, GenerationResponse
from app.modules.alerts.service import FINAL_STATUSES, active_alerts_query, generate_daily_alerts
from app.modules.auth.models import User

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def alert_or_404(alert_id: str, db: Session) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def assert_alert_access(alert: Alert, user: User) -> None:
    if user.role == "ASESOR" and alert.assigned_advisor_id != user.id:
        raise HTTPException(status_code=403, detail="You can only manage your assigned alerts")


@router.post("/generate", response_model=GenerationResponse)
def generate_alerts(run_date: date | None = None, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    effective_date = run_date or date.today()
    result = generate_daily_alerts(effective_date, db, current_user.id)
    db.commit()
    return {"run_date": effective_date, **result}


@router.get("/inbox", response_model=list[AlertResponse])
def inbox(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Alert]:
    today = date.today()
    priority = case(
        (Alert.status == "REPROGRAMADO", 4),
        (Alert.next_action_date < today, 0),
        (Alert.alert_date < today, 1),
        (Alert.next_action_date == today, 2),
        else_=3,
    )
    query = active_alerts_query().order_by(priority, Alert.next_action_date, Alert.alert_date)
    if current_user.role == "ASESOR":
        query = query.where(Alert.assigned_advisor_id == current_user.id)
    return list(db.scalars(query))


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Alert:
    alert = alert_or_404(alert_id, db)
    assert_alert_access(alert, current_user)
    return alert


@router.get("/{alert_id}/attempts", response_model=list[ContactAttemptResponse])
def list_attempts(alert_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AlertContactAttempt]:
    alert = alert_or_404(alert_id, db)
    assert_alert_access(alert, current_user)
    return list(db.scalars(select(AlertContactAttempt).where(AlertContactAttempt.alert_id == alert.id).order_by(AlertContactAttempt.contacted_at)))


@router.post("/{alert_id}/attempts", response_model=AlertResponse)
def add_attempt(alert_id: str, payload: ContactAttemptCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Alert:
    alert = alert_or_404(alert_id, db)
    assert_alert_access(alert, current_user)
    if alert.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="A final alert cannot receive contact attempts")
    if payload.result == "RECOMPRA_REGISTRADA":
        raise HTTPException(status_code=422, detail="RECOMPRA_REGISTRADA requires recording a confirmed sale")
    attempt = AlertContactAttempt(alert_id=alert.id, advisor_id=current_user.id, channel=payload.channel, result=payload.result,
                                  note=payload.note.strip() if payload.note else None, next_action_date=payload.next_action_date)
    db.add(attempt)
    alert.attempts_count += 1
    alert.last_contact_at = datetime.now(timezone.utc)
    alert.next_action_date = payload.next_action_date
    if payload.result in {"AUN_TIENE_PRODUCTO", "SOLICITA_SEGUIMIENTO"}:
        alert.status = "REPROGRAMADO"
    elif payload.result == "SIN_RESPUESTA":
        alert.status = "SIN_RESPUESTA"
    elif payload.result == "NO_INTERESADO":
        alert.status, alert.closed_at = "NO_INTERESADO", datetime.now(timezone.utc)
    elif payload.result == "DATOS_DE_CONTACTO_INCORRECTOS":
        alert.assigned_advisor_id, alert.status = None, "PENDIENTE"
    elif payload.close_alert:
        alert.status, alert.closed_at = "CANCELADO_POR_RECOMPRA", datetime.now(timezone.utc)
    record_audit(db, actor_id=current_user.id, entity_type="alert", entity_id=alert.id, action="CONTACT_ATTEMPT", after={"result": payload.result, "status": alert.status, "next_action_date": str(alert.next_action_date) if alert.next_action_date else None})
    db.commit()
    return alert
