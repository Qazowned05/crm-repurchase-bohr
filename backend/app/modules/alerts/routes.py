from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginated_scalars, paginate_items
from app.dependencies import get_current_user
from app.modules.alerts.models import Alert, AlertContactAttempt
from app.modules.alerts.schemas import AlertRepurchaseCreate, AlertResponse, ContactAttemptCreate, ContactAttemptResponse, ManagedAlertResponse
from app.modules.alerts.service import FINAL_STATUSES, active_alerts_query, alert_response, contact_attempt_response, ensure_daily_alerts, managed_alert_response
from app.modules.alerts.service import advisor_visible_alerts_query
from app.modules.auth.models import User
from app.modules.configuration.models import ContactTypification
from app.modules.customers.models import Customer
from app.modules.products.models import Product
from app.modules.sales.models import Sale, SaleItem
from app.modules.sales.routes import recompute_chain, rule_for, sale_response
from app.modules.sales.schemas import SaleResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def alert_or_404(alert_id: str, db: Session) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def assert_alert_access(alert: Alert, user: User) -> None:
    if user.role == "ASESOR" and alert.assigned_advisor_id != user.id:
        raise HTTPException(status_code=403, detail="You can only manage your assigned alerts")


def apply_alert_filters(query, q: str | None, product_id: str | None, alert_status: str | None, alert_type: str | None):
    if q:
        term = f"%{q.strip()}%"
        customer_ids = select(Customer.id).where(or_(
            Customer.dni.ilike(term), Customer.first_names.ilike(term), Customer.last_names.ilike(term),
            Customer.phone.ilike(term), Customer.email.ilike(term),
        ))
        query = query.where(Alert.sale_item_id.in_(
            select(SaleItem.id).join(Sale, Sale.id == SaleItem.sale_id).where(Sale.customer_id.in_(customer_ids))
        ))
    if product_id:
        query = query.where(Alert.sale_item_id.in_(select(SaleItem.id).where(SaleItem.product_id == product_id)))
    if alert_status:
        query = query.where(Alert.status == alert_status)
    if alert_type == "AUTOMATICA":
        query = query.where(Alert.status.not_in({"REASIGNADO", "REPROGRAMADO"}), Alert.next_action_date.is_(None))
    elif alert_type == "REASIGNADA":
        query = query.where(Alert.status == "REASIGNADO")
    elif alert_type == "SEGUIMIENTO":
        query = query.where(or_(Alert.status == "REPROGRAMADO", Alert.next_action_date.is_not(None)))
    return query


def apply_priority_filter(query, priority: str | None, today: date):
    if priority == "VENCIDA":
        return query.where(or_(Alert.next_action_date < today, and_(Alert.next_action_date.is_(None), Alert.alert_date < today)))
    if priority == "HOY":
        return query.where(or_(Alert.next_action_date == today, and_(Alert.next_action_date.is_(None), Alert.alert_date == today)))
    if priority == "PROXIMA":
        return query.where(or_(Alert.next_action_date > today, and_(Alert.next_action_date.is_(None), Alert.alert_date > today)))
    if priority == "SIN_GESTION":
        return query.where(Alert.attempts_count == 0)
    return query


@router.post("/{alert_id}/repurchase", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def register_repurchase(
    alert_id: str,
    payload: AlertRepurchaseCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # Locking the alert serializes repurchase registration; the unique sale link is a second guard.
    alert = db.scalar(select(Alert).where(Alert.id == alert_id).with_for_update())
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    assert_alert_access(alert, current_user)

    linked_sale = db.scalar(select(Sale).where(Sale.source_alert_id == alert.id))
    if linked_sale is not None:
        response.status_code = status.HTTP_200_OK
        return sale_response(linked_sale, db)
    if alert.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="A final alert cannot register a repurchase")

    source_item = db.get(SaleItem, alert.sale_item_id)
    source_sale = db.get(Sale, source_item.sale_id) if source_item else None
    customer = db.get(Customer, source_sale.customer_id) if source_sale else None
    if source_item is None or source_sale is None or customer is None or customer.status != "ACTIVO":
        raise HTTPException(status_code=422, detail="Alert source must belong to an active customer")
    if payload.sale_date < source_sale.sale_date:
        raise HTTPException(status_code=422, detail="Repurchase date cannot precede the original sale")

    products = {item.product_id: db.get(Product, item.product_id) for item in payload.items}
    if any(product is None or not product.is_active for product in products.values()):
        raise HTTPException(status_code=422, detail="All products must exist and be active")
    rules = {product_id: rule_for(product_id, payload.sale_date, db) for product_id in products}
    if any(rule is None for rule in rules.values()):
        raise HTTPException(status_code=422, detail="Each product needs an effective repurchase rule on the sale date")

    advisor_id = current_user.id if current_user.role == "ASESOR" else (alert.assigned_advisor_id or current_user.id)
    sale = Sale(
        customer_id=customer.id,
        advisor_id=advisor_id,
        sale_date=payload.sale_date,
        notes=payload.notes.strip() if payload.notes else None,
        acquisition_channel=payload.acquisition_channel.strip().upper() if payload.acquisition_channel else None,
        acquisition_channel_detail=payload.acquisition_channel_detail.strip() if payload.acquisition_channel_detail else None,
        source_alert_id=alert.id if source_item.product_id in products else None,
    )
    try:
        with db.begin_nested():
            db.add(sale)
            db.flush()
    except IntegrityError:
        # The unique source-alert link also protects this endpoint from writers that do not lock alerts.
        linked_sale = db.scalar(select(Sale).where(Sale.source_alert_id == alert.id))
        if linked_sale is None:
            raise
        response.status_code = status.HTTP_200_OK
        return sale_response(linked_sale, db)
    for payload_item in payload.items:
        rule = rules[payload_item.product_id]
        db.add(SaleItem(
            sale_id=sale.id,
            product_id=payload_item.product_id,
            quantity=payload_item.quantity,
            unit_price=products[payload_item.product_id].unit_price,
            rule_duration_days=rule.duration_days,
            rule_alert_days=rule.alert_days,
            expected_repurchase_date=payload.sale_date + timedelta(days=rule.duration_days),
        ))
    db.flush()
    product_ids = set(products)
    recompute_chain(customer.id, product_ids, db)
    source_product_purchased = source_item.product_id in product_ids
    if payload.customer_condition is not None:
        previous_condition = customer.condition
        customer.condition = payload.customer_condition.strip() or None
        if customer.condition != previous_condition:
            record_audit(db, actor_id=current_user.id, entity_type="customer", entity_id=customer.id, action="UPDATED", before={"condition": previous_condition}, after={"condition": customer.condition, "source": "repurchase"})
    alert.status = "RECOMPRA_LOGRADA" if source_product_purchased else "COMPRA_OTRO_PRODUCTO"
    managed_at = datetime.now(timezone.utc)
    alert.closed_at = managed_at
    alert.last_contact_at = managed_at
    alert.attempts_count += 1
    alert.closure_reason = (
        f"RECOMPRA_CONFIRMADA: venta {sale.id}"
        if source_product_purchased
        else f"COMPRA_OTRO_PRODUCTO: venta {sale.id}"
    )
    # A confirmed repurchase is a commercial management and must remain visible in the alert history.
    db.add(AlertContactAttempt(
        alert_id=alert.id,
        advisor_id=current_user.id,
        contacted_at=managed_at,
        channel="SISTEMA",
        result="RECOMPRA_REGISTRADA" if source_product_purchased else "COMPRA_OTRO_PRODUCTO",
        note=payload.notes.strip() if payload.notes else "Recompra confirmada desde la alerta.",
    ))
    record_audit(db, actor_id=current_user.id, entity_type="alert", entity_id=alert.id, action="REPURCHASE_ACHIEVED" if source_product_purchased else "OTHER_PRODUCT_PURCHASED", after={"status": alert.status, "closure_reason": alert.closure_reason, "repurchase_sale_id": sale.id})
    record_audit(db, actor_id=current_user.id, entity_type="sale", entity_id=sale.id, action="CONFIRMED", after={"status": sale.status, "customer_id": customer.id, "source_alert_id": alert.id})
    db.commit()
    return sale_response(sale, db)


@router.get("/inbox")
def inbox(
    q: str | None = None, product_id: str | None = None, alert_status: str | None = Query(default=None, alias="status"),
    alert_type: str | None = Query(default=None, pattern="^(AUTOMATICA|REASIGNADA|SEGUIMIENTO)$"),
    priority_filter: str | None = Query(default=None, alias="priority", pattern="^(VENCIDA|HOY|PROXIMA|SIN_GESTION)$"),
    page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[dict] | dict:
    today = date.today()
    ensure_daily_alerts(db)
    query = advisor_visible_alerts_query(db) if current_user.role == "ASESOR" else active_alerts_query()
    if current_user.role == "ASESOR":
        query = query.where(Alert.assigned_advisor_id == current_user.id)
        due_date = func.coalesce(Alert.next_action_date, Alert.alert_date)
        priority = case(
            (due_date == today, 0),
            (due_date < today, 1),
            else_=2,
        )
        query = query.order_by(priority, due_date.desc(), Alert.created_at.desc())
    else:
        query = query.order_by(Alert.alert_date.desc(), Alert.created_at.desc())
    query = apply_priority_filter(apply_alert_filters(query, q, product_id, alert_status, alert_type), priority_filter, today)
    result = paginated_scalars(db, query, page, page_size)
    if isinstance(result, list):
        return [managed_alert_response(alert, db) for alert in result]
    return {**result, "items": [managed_alert_response(alert, db) for alert in result["items"]]}


@router.get("/inbox-summary")
def inbox_summary(
    q: str | None = None, product_id: str | None = None, alert_status: str | None = Query(default=None, alias="status"),
    alert_type: str | None = Query(default=None, pattern="^(AUTOMATICA|REASIGNADA|SEGUIMIENTO)$"),
    priority_filter: str | None = Query(default=None, alias="priority", pattern="^(VENCIDA|HOY|PROXIMA|SIN_GESTION)$"),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> dict[str, int]:
    today = date.today()
    query = advisor_visible_alerts_query(db) if current_user.role == "ASESOR" else active_alerts_query()
    if current_user.role == "ASESOR":
        query = query.where(Alert.assigned_advisor_id == current_user.id)
    alerts = list(db.scalars(apply_priority_filter(apply_alert_filters(query, q, product_id, alert_status, alert_type), priority_filter, today)))
    return {
        "total": len(alerts),
        "unmanaged": sum(alert.attempts_count == 0 for alert in alerts),
        "due_today": sum(alert.next_action_date == today or (alert.next_action_date is None and alert.alert_date == today) for alert in alerts),
        "overdue": sum((alert.next_action_date is not None and alert.next_action_date < today) or (alert.next_action_date is None and alert.alert_date < today) for alert in alerts),
    }


@router.get("/register")
def managed_register(
    date_from: date | None = None,
    date_to: date | None = None,
    state: str | None = Query(default=None, pattern="^(open-follow-up|closed)$"),
    q: str | None = None, product_id: str | None = None, alert_status: str | None = Query(default=None, alias="status"),
    advisor_id: str | None = None,
    alert_type: str | None = Query(default=None, pattern="^(AUTOMATICA|REASIGNADA|SEGUIMIENTO)$"),
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
    elif advisor_id:
        query = query.where(Alert.assigned_advisor_id == advisor_id)
    if date_from:
        query = query.where(Alert.alert_date >= date_from)
    if date_to:
        query = query.where(Alert.alert_date <= date_to)
    if state == "open-follow-up":
        query = query.where(Alert.status.not_in(FINAL_STATUSES))
    elif state == "closed":
        query = query.where(Alert.status.in_(FINAL_STATUSES))
    query = apply_alert_filters(query, q, product_id, alert_status, alert_type)
    result = paginated_scalars(db, query.order_by(Alert.alert_date.desc(), Alert.created_at.desc()), page, page_size)
    if isinstance(result, list):
        return [managed_alert_response(alert, db) for alert in result]
    return {**result, "items": [managed_alert_response(alert, db) for alert in result["items"]]}


@router.get("/upcoming")
def upcoming_alerts(
    limit: int = Query(default=12, ge=1, le=50),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[dict]:
    """Return planned reminders without making them actionable before their date."""
    if current_user.role != "ASESOR":
        raise HTTPException(status_code=403, detail="Upcoming alerts are available to advisors only")
    today = date.today()
    rows = db.execute(
        select(SaleItem, Sale, Customer, Product)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Customer, Customer.id == Sale.customer_id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(
            Sale.status == "CONFIRMADA",
            or_(Sale.advisor_id == current_user.id, Customer.responsible_advisor_id == current_user.id),
        )
    ).all()
    upcoming: list[dict] = []
    for item, sale, customer, product in rows:
        scheduled = sorted({item.expected_repurchase_date - timedelta(days=days) for days in item.rule_alert_days})
        for alert_date in scheduled:
            if alert_date <= today:
                continue
            upcoming.append({
                "sale_item_id": item.id, "alert_date": alert_date,
                "expected_repurchase_date": item.expected_repurchase_date,
                "alert_kind": "VENCIMIENTO" if alert_date == scheduled[-1] else "SEGUIMIENTO",
                "customer_name": f"{customer.first_names} {customer.last_names}".strip(),
                "customer_dni": customer.dni, "product_name": product.name, "product_code": product.code,
            })
    return sorted(upcoming, key=lambda alert: (alert["alert_date"], alert["customer_name"]))[:limit]


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
    if result in {"AUN_TIENE_PRODUCTO", "SOLICITA_SEGUIMIENTO"} or (typification and typification.requires_next_action):
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
