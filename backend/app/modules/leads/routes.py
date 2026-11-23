from datetime import date, datetime, timedelta, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginated_scalars
from app.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.campaigns.models import Campaign
from app.modules.configuration.models import ContactTypification
from app.modules.customers.models import Customer
from app.modules.customers.routes import validate_location
from app.modules.leads.models import Lead, LeadActivity, LeadAssignmentHistory, LeadNotification
from app.modules.leads.schemas import BulkLeadAssignmentCreate, LeadActivityCreate, LeadAssignmentCreate, LeadConversionCreate, LeadCreate, LeadUpdate
from app.modules.leads.service import lead_response
from app.modules.products.models import Product
from app.modules.sales.models import Sale, SaleItem
from app.modules.alerts.service import close_alerts_for_repurchase
from app.modules.sales.routes import confirmed_sale_exists, recompute_chain, rule_for, sale_response

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])
FINAL_STATUSES = {"CERRADO_EFECTIVO"}


def lead_or_404(lead_id: str, db: Session) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def assert_access(lead: Lead, user: User) -> None:
    if user.role == "ASESOR" and lead.assigned_advisor_id != user.id:
        raise HTTPException(status_code=403, detail="Lead is outside your assignments")


def validate_advisor(advisor_id: str | None, db: Session) -> None:
    if advisor_id is None:
        return
    advisor = db.get(User, advisor_id)
    if advisor is None or not advisor.is_active or advisor.role != "ASESOR":
        raise HTTPException(status_code=422, detail="Assigned advisor must be active")


def activity_response(activity: LeadActivity, db: Session) -> dict:
    advisor = db.get(User, activity.advisor_id)
    typification = db.get(ContactTypification, activity.typification_id)
    return {
        **{column.name: getattr(activity, column.name) for column in LeadActivity.__table__.columns},
        "advisor_name": advisor.full_name if advisor else None,
        "typification_code": typification.code if typification else None,
        "typification_name": typification.name if typification else None,
        "typification_lead_outcome": typification.lead_outcome if typification else None,
    }


def validate_lead_typification(typification: ContactTypification, db: Session, *, effective_allowed: bool = False) -> str:
    if not typification.is_active:
        raise HTTPException(status_code=422, detail="Typification must be active")
    if db.scalar(select(ContactTypification.id).where(ContactTypification.parent_id == typification.id).limit(1)):
        raise HTTPException(status_code=422, detail="Lead typification must be a leaf")
    if typification.lead_outcome is None:
        raise HTTPException(status_code=422, detail="Lead typification must define a lead outcome")
    if typification.lead_outcome == "EFECTIVO" and not effective_allowed:
        raise HTTPException(status_code=422, detail="Use lead conversion to register an effective outcome")
    return typification.lead_outcome


def latest_activity_subquery():
    return select(
        LeadActivity.lead_id.label("lead_id"),
        LeadActivity.typification_id.label("typification_id"),
        func.row_number().over(
            partition_by=LeadActivity.lead_id,
            order_by=(LeadActivity.created_at.desc(), LeadActivity.id.desc()),
        ).label("row_number"),
    ).subquery()


def excel_text(value: object) -> object:
    return f"'{value}" if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value


def assign_from_excel(lead: Lead, advisor_id: str, actor_id: str, db: Session) -> None:
    previous = lead.assigned_advisor_id
    was_recoverable = lead.status == "RECUPERABLE"
    lead.assigned_advisor_id = advisor_id
    if was_recoverable:
        lead.status = "PENDIENTE"
        lead.reassigned_from_recovery = True
        lead.reassigned_at = datetime.now(timezone.utc)
    db.add(LeadAssignmentHistory(
        lead_id=lead.id, previous_advisor_id=previous, assigned_advisor_id=advisor_id,
        reason="Reasignación masiva mediante Excel", assigned_by_user_id=actor_id,
    ))
    record_audit(db, actor_id=actor_id, entity_type="lead", entity_id=lead.id, action="ASSIGNED",
                 before={"assigned_advisor_id": previous}, after={"assigned_advisor_id": advisor_id, "status": lead.status, "reason": "Reasignación masiva mediante Excel"})


def add_advisor_dropdown(workbook: Workbook, sheet, db: Session) -> None:
    emails = list(db.scalars(select(User.email).where(User.role == "ASESOR", User.is_active.is_(True)).order_by(User.email)))
    if not emails:
        return
    advisors = workbook.create_sheet("Asesores")
    for email in emails:
        advisors.append([email])
    advisors.sheet_state = "hidden"
    workbook.defined_names.add(DefinedName("active_advisor_emails", attr_text=f"'Asesores'!$A$1:$A${len(emails)}"))
    validation = DataValidation(type="list", formula1="active_advisor_emails", allow_blank=False)
    sheet.add_data_validation(validation)
    validation.add(f"G2:G{max(2, sheet.max_row)}")


def filtered_leads_query(
    current_user: User, *, status_filter: str | None = None, advisor_id: str | None = None,
    q: str | None = None, campaign_ids: str | None = None, initial_product_id: str | None = None,
    created_from: date | None = None, created_to: date | None = None, created_on: date | None = None,
    reassigned_on: date | None = None, activity_on: date | None = None,
    activity_from: date | None = None, activity_to: date | None = None, next_action: str | None = None,
    typification_id: str | None = None,
):
    latest = latest_activity_subquery()
    query = select(Lead).outerjoin(latest, (latest.c.lead_id == Lead.id) & (latest.c.row_number == 1))
    if current_user.role == "ASESOR":
        query = query.where(Lead.assigned_advisor_id == current_user.id)
    elif advisor_id:
        query = query.where(Lead.assigned_advisor_id == advisor_id)
    if status_filter:
        statuses = {"CERRADO"} if status_filter == "CERRADO" else {status_filter}
        if status_filter == "CERRADO":
            statuses = {"CERRADO_EFECTIVO"}
        query = query.where(Lead.status.in_(statuses))
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(Lead.full_name.ilike(term), Lead.phone.ilike(term), Lead.email.ilike(term)))
    if campaign_ids:
        values = [value.strip() for value in campaign_ids.split(",") if value.strip()]
        if values:
            query = query.where(Lead.campaign_id.in_(values))
    if initial_product_id:
        query = query.where(Lead.initial_product_id == initial_product_id)
    if created_from:
        query = query.where(func.date(Lead.created_at) >= created_from)
    if created_to:
        query = query.where(func.date(Lead.created_at) <= created_to)
    if created_on:
        query = query.where(func.date(Lead.created_at) == created_on)
    if reassigned_on:
        query = query.where(func.date(Lead.reassigned_at) == reassigned_on)
    if activity_on:
        query = query.where(or_(func.date(Lead.created_at) == activity_on, func.date(Lead.reassigned_at) == activity_on))
    if activity_from or activity_to:
        if status_filter == "AGENDADO":
            if activity_from:
                query = query.where(Lead.next_action_date >= activity_from)
            if activity_to:
                query = query.where(Lead.next_action_date <= activity_to)
        else:
            created_period = []
            reassigned_period = []
            if activity_from:
                created_period.append(func.date(Lead.created_at) >= activity_from)
                reassigned_period.append(func.date(Lead.reassigned_at) >= activity_from)
            if activity_to:
                created_period.append(func.date(Lead.created_at) <= activity_to)
                reassigned_period.append(func.date(Lead.reassigned_at) <= activity_to)
            query = query.where(or_(and_(*created_period), and_(*reassigned_period)))
    if typification_id:
        query = query.where(latest.c.typification_id == typification_id)
    today = datetime.now(timezone.utc).date()
    query = query.where(or_(Lead.status != "AGENDADO", Lead.next_action_date <= today))
    if next_action == "OVERDUE":
        query = query.where(Lead.next_action_date < today)
    elif next_action == "DUE":
        query = query.where(Lead.next_action_date <= today)
    elif next_action == "TODAY":
        query = query.where(Lead.next_action_date == today)
    elif next_action == "NEXT_7":
        query = query.where(Lead.next_action_date > today, Lead.next_action_date <= today + timedelta(days=7))
    elif next_action == "UNSCHEDULED":
        query = query.where(Lead.next_action_date.is_(None))
    elif next_action:
        raise HTTPException(status_code=422, detail="Invalid next_action filter")
    return query


def board_order(query, status_filter: str | None):
    if status_filter == "AGENDADO":
        return query.order_by(Lead.next_action_at.asc().nullslast(), Lead.created_at.asc())
    if status_filter in {"CERRADO", "CERRADO_EFECTIVO"}:
        return query.order_by(Lead.updated_at.desc())
    return query.order_by(Lead.created_at.asc())


@router.post("", status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, current_user: User = Depends(require_roles("ASESOR", "SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    assigned_advisor_id = payload.assigned_advisor_id
    if current_user.role == "ASESOR":
        if assigned_advisor_id not in {None, current_user.id}:
            raise HTTPException(status_code=403, detail="Advisors cannot assign leads")
        assigned_advisor_id = current_user.id
    elif assigned_advisor_id is None:
        raise HTTPException(status_code=422, detail="An assigned advisor is required")
    validate_advisor(assigned_advisor_id, db)
    if payload.initial_product_id and db.get(Product, payload.initial_product_id) is None:
        raise HTTPException(status_code=422, detail="Initial product does not exist")
    campaign = db.get(Campaign, payload.campaign_id)
    if campaign is None or not campaign.is_active:
        raise HTTPException(status_code=422, detail="Campaign must be active")
    phone = payload.phone.strip()
    lead = Lead(full_name=payload.full_name.strip() if payload.full_name and payload.full_name.strip() else f"Lead {phone}", dni=payload.dni.strip() if payload.dni else None, phone=phone, email=str(payload.email).lower() if payload.email else None,
                  condition=payload.condition.strip() if payload.condition else None, campaign_id=payload.campaign_id, initial_product_id=payload.initial_product_id, notes=payload.notes.strip() if payload.notes else None,
                assigned_advisor_id=assigned_advisor_id)
    db.add(lead)
    db.flush()
    if assigned_advisor_id:
        db.add(LeadAssignmentHistory(lead_id=lead.id, previous_advisor_id=None, assigned_advisor_id=assigned_advisor_id,
                                     reason="Asignación inicial", assigned_by_user_id=current_user.id))
    record_audit(db, actor_id=current_user.id, entity_type="lead", entity_id=lead.id, action="CREATED", after={"campaign_id": lead.campaign_id, "assigned_advisor_id": assigned_advisor_id})
    db.commit()
    return lead_response(lead, db)


@router.get("")
def list_leads(status_filter: str | None = Query(default=None, alias="status"), advisor_id: str | None = None, q: str | None = None,
               campaign_ids: str | None = None, initial_product_id: str | None = None, created_from: date | None = None,
                 created_to: date | None = None, created_on: date | None = None, reassigned_on: date | None = None,
                 activity_on: date | None = None, activity_from: date | None = None, activity_to: date | None = None,
                 next_action: str | None = None, typification_id: str | None = None,
               page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
               current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict] | dict:
    query = filtered_leads_query(
        current_user, status_filter=status_filter, advisor_id=advisor_id, q=q, campaign_ids=campaign_ids,
        initial_product_id=initial_product_id, created_from=created_from, created_to=created_to, created_on=created_on,
        reassigned_on=reassigned_on, activity_on=activity_on, activity_from=activity_from, activity_to=activity_to,
        next_action=next_action, typification_id=typification_id,
    ).order_by(Lead.created_at.desc())
    result = paginated_scalars(db, query, page, page_size)
    return [lead_response(lead, db) for lead in result] if isinstance(result, list) else {**result, "items": [lead_response(lead, db) for lead in result["items"]]}


@router.get("/assignment.xlsx")
def export_lead_assignments(
    status_filter: str | None = Query(default=None, alias="status"), advisor_id: str | None = None, q: str | None = None,
    campaign_ids: str | None = None, initial_product_id: str | None = None, created_from: date | None = None,
    created_to: date | None = None, created_on: date | None = None, reassigned_on: date | None = None,
    activity_on: date | None = None, activity_from: date | None = None, activity_to: date | None = None,
    next_action: str | None = None, typification_id: str | None = None,
    current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
) -> StreamingResponse:
    assigned_advisor = aliased(User)
    rows = db.execute(
        filtered_leads_query(current_user, status_filter=status_filter, advisor_id=advisor_id, q=q, campaign_ids=campaign_ids,
                             initial_product_id=initial_product_id, created_from=created_from, created_to=created_to, created_on=created_on,
                             reassigned_on=reassigned_on, activity_on=activity_on, activity_from=activity_from, activity_to=activity_to,
                             next_action=next_action, typification_id=typification_id)
        .add_columns(Campaign, assigned_advisor)
        .join(Campaign, Campaign.id == Lead.campaign_id)
        .outerjoin(assigned_advisor, assigned_advisor.id == Lead.assigned_advisor_id)
        .order_by(Lead.created_at.desc())
    )
    workbook = Workbook(); sheet = workbook.active; sheet.title = "Data"
    sheet.append(["lead_id", "full_name", "phone", "campaign", "status", "current_advisor_email", "responsible_advisor_email"])
    for cell in sheet[1]: cell.font = Font(bold=True)
    for lead, campaign, advisor in rows:
        sheet.append([lead.id, excel_text(lead.full_name), excel_text(lead.phone), excel_text(campaign.name), lead.status, advisor.email if advisor else "", advisor.email if advisor else ""])
    add_advisor_dropdown(workbook, sheet, db)
    sheet.freeze_panes = "A2"; sheet.auto_filter.ref = sheet.dimensions
    output = BytesIO(); workbook.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="asignacion_leads.xlsx"'})


@router.post("/assignments/import")
async def import_lead_assignments(
    file: UploadFile = File(...), current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db),
) -> dict:
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Upload an XLSX file")
    try:
        workbook = load_workbook(BytesIO(await file.read()), data_only=False, read_only=True)
        if "Data" not in workbook.sheetnames:
            raise ValueError("Workbook must contain a Data sheet")
        sheet = workbook["Data"]
        headers = [str(cell.value or "").strip() for cell in sheet[1]]
        if headers != ["lead_id", "full_name", "phone", "campaign", "status", "current_advisor_email", "responsible_advisor_email"]:
            raise ValueError("Headers must match the downloaded assignment file")
        rows = []
        for number, cells in enumerate(sheet.iter_rows(min_row=2), start=2):
            if all(cell.value is None for cell in cells): continue
            if any(cell.data_type == "f" for cell in cells): raise ValueError(f"Row {number}: formulas are not allowed")
            lead_id, advisor_email = str(cells[0].value or "").strip(), str(cells[6].value or "").strip().lower()
            if not lead_id or not advisor_email: raise ValueError(f"Row {number}: lead_id and responsible_advisor_email are required")
            rows.append((number, lead_id, advisor_email))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Invalid assignment file: {error}") from error
    if not rows:
        raise HTTPException(status_code=422, detail="The assignment file has no rows")
    if len({lead_id for _, lead_id, _ in rows}) != len(rows):
        raise HTTPException(status_code=422, detail="A lead can only appear once in the assignment file")
    leads = {lead.id: lead for lead in db.scalars(select(Lead).where(Lead.id.in_({lead_id for _, lead_id, _ in rows})).with_for_update())}
    advisors = {advisor.email.lower(): advisor for advisor in db.scalars(select(User).where(User.email.in_({email for _, _, email in rows})))}
    changes = []
    for number, lead_id, email in rows:
        lead, advisor = leads.get(lead_id), advisors.get(email)
        if lead is None: raise HTTPException(status_code=422, detail=f"Row {number}: lead was not found")
        if advisor is None or not advisor.is_active or advisor.role != "ASESOR": raise HTTPException(status_code=422, detail=f"Row {number}: responsible advisor must be active")
        if lead.assigned_advisor_id != advisor.id or lead.status == "RECUPERABLE": changes.append((lead, advisor))
    for lead, advisor in changes:
        assign_from_excel(lead, advisor.id, current_user.id, db)
    db.commit()
    return {"processed": len(rows), "reassigned": len(changes)}


@router.get("/board")
def lead_board(status_filter: str | None = Query(default=None, alias="status"), advisor_id: str | None = None,
               q: str | None = None, campaign_ids: str | None = None, initial_product_id: str | None = None,
                 created_from: date | None = None, created_to: date | None = None, created_on: date | None = None,
                 reassigned_on: date | None = None, activity_on: date | None = None,
                 activity_from: date | None = None, activity_to: date | None = None, next_action: str | None = None,
               typification_id: str | None = None, page: int = Query(default=1, ge=1),
               page_size: int | None = Query(default=None, ge=1, le=200),
               pagesize: int | None = Query(default=None, ge=1, le=200),
               current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    size = page_size or pagesize or 20
    query = board_order(filtered_leads_query(
        current_user, status_filter=status_filter, advisor_id=advisor_id, q=q, campaign_ids=campaign_ids,
        initial_product_id=initial_product_id, created_from=created_from, created_to=created_to, created_on=created_on,
        reassigned_on=reassigned_on, activity_on=activity_on, activity_from=activity_from, activity_to=activity_to,
        next_action=next_action, typification_id=typification_id,
    ), status_filter)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    leads = list(db.scalars(query.limit(size).offset((page - 1) * size)))
    return {"items": [lead_response(lead, db) for lead in leads], "total": total, "page": page, "page_size": size}


@router.get("/board-summary")
def lead_board_summary(advisor_id: str | None = None, q: str | None = None, campaign_ids: str | None = None,
                       initial_product_id: str | None = None, created_from: date | None = None,
                         created_to: date | None = None, created_on: date | None = None, reassigned_on: date | None = None,
                         activity_on: date | None = None, activity_from: date | None = None,
                         activity_to: date | None = None, next_action: str | None = None,
                       typification_id: str | None = None, current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> dict:
    query = filtered_leads_query(
        current_user, advisor_id=advisor_id, q=q, campaign_ids=campaign_ids, initial_product_id=initial_product_id,
        created_from=created_from, created_to=created_to, created_on=created_on, reassigned_on=reassigned_on,
        activity_on=activity_on, activity_from=activity_from, activity_to=activity_to,
        next_action=next_action, typification_id=typification_id,
    )
    leads = query.order_by(None).subquery()
    counts = dict(db.execute(select(leads.c.status, func.count()).group_by(leads.c.status)).all())
    return {
        "PENDIENTE": counts.get("PENDIENTE", 0),
        "AGENDADO": counts.get("AGENDADO", 0),
        "RECUPERABLE": counts.get("RECUPERABLE", 0),
        "CERRADO": counts.get("CERRADO_EFECTIVO", 0),
    }


@router.get("/recovery")
def recovery_queue(q: str | None = None, campaign_id: str | None = None, advisor_id: str | None = None,
                   initial_product_id: str | None = None, created_on: date | None = None,
                   page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200),
                   current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[dict] | dict:
    result = paginated_scalars(
        db,
        filtered_leads_query(current_user, status_filter="RECUPERABLE", q=q, campaign_ids=campaign_id,
                             advisor_id=advisor_id, initial_product_id=initial_product_id, created_on=created_on)
        .order_by(Lead.updated_at),
        page,
        page_size,
    )
    return [lead_response(lead, db) for lead in result] if isinstance(result, list) else {**result, "items": [lead_response(lead, db) for lead in result["items"]]}


@router.get("/notifications")
def list_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    notifications = db.scalars(select(LeadNotification).where(LeadNotification.user_id == current_user.id, LeadNotification.dismissed_at.is_(None)).order_by(LeadNotification.created_at.desc()))
    return [{"id": item.id, "lead_id": item.lead_id, "scheduled_for": item.scheduled_for, "created_at": item.created_at, "lead": lead_response(lead_or_404(item.lead_id, db), db)} for item in notifications]


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(notification_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    notification = db.get(LeadNotification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{lead_id}")
def get_lead(lead_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    lead = lead_or_404(lead_id, db)
    assert_access(lead, current_user)
    return lead_response(lead, db)


@router.patch("/{lead_id}")
def update_lead(lead_id: str, payload: LeadUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    lead = lead_or_404(lead_id, db)
    assert_access(lead, current_user)
    changes = payload.model_dump(exclude_unset=True)
    if "initial_product_id" in changes and changes["initial_product_id"]:
        product = db.get(Product, changes["initial_product_id"])
        if product is None or not product.is_active:
            raise HTTPException(status_code=422, detail="Initial product must exist and be active")
    before = {field: getattr(lead, field) for field in changes}
    for field, value in changes.items():
        if field == "email" and value is not None:
            value = str(value).lower()
        elif field in {"full_name", "dni", "phone", "condition", "notes"} and value is not None:
            value = value.strip() or None
        if field in {"full_name", "phone"} and not value:
            raise HTTPException(status_code=422, detail=f"{field} cannot be blank")
        setattr(lead, field, value)
        changes[field] = value
    record_audit(db, actor_id=current_user.id, entity_type="lead", entity_id=lead.id, action="UPDATED", before=before, after=changes)
    db.commit()
    db.refresh(lead)
    return lead_response(lead, db)


@router.get("/{lead_id}/activities")
def list_activities(lead_id: str, page: int | None = Query(default=None, ge=1),
                    page_size: int | None = Query(default=None, ge=1, le=100),
                    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict] | dict:
    lead = lead_or_404(lead_id, db)
    assert_access(lead, current_user)
    result = paginated_scalars(
        db,
        select(LeadActivity).where(LeadActivity.lead_id == lead.id).order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc()),
        page,
        page_size,
    )
    return [activity_response(activity, db) for activity in result] if isinstance(result, list) else {
        **result,
        "items": [activity_response(activity, db) for activity in result["items"]],
    }


@router.post("/{lead_id}/assign")
def assign_lead(lead_id: str, payload: LeadAssignmentCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    lead = lead_or_404(lead_id, db)
    validate_advisor(payload.assigned_advisor_id, db)
    previous = lead.assigned_advisor_id
    was_recoverable = lead.status == "RECUPERABLE"
    if previous != payload.assigned_advisor_id or was_recoverable:
        lead.assigned_advisor_id = payload.assigned_advisor_id
        if was_recoverable:
            lead.status = "PENDIENTE"
            lead.reassigned_from_recovery = True
            lead.reassigned_at = datetime.now(timezone.utc)
        db.add(LeadAssignmentHistory(lead_id=lead.id, previous_advisor_id=previous, assigned_advisor_id=lead.assigned_advisor_id, reason=payload.reason.strip(), assigned_by_user_id=current_user.id))
        record_audit(db, actor_id=current_user.id, entity_type="lead", entity_id=lead.id, action="ASSIGNED", before={"assigned_advisor_id": previous, "status": "RECUPERABLE" if was_recoverable else lead.status}, after={"assigned_advisor_id": lead.assigned_advisor_id, "status": lead.status, "reason": payload.reason.strip()})
        db.commit()
    return lead_response(lead, db)


@router.post("/bulk-assign")
def bulk_assign_recoverable_leads(payload: BulkLeadAssignmentCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> dict:
    if len(set(payload.lead_ids)) != len(payload.lead_ids):
        raise HTTPException(status_code=422, detail="lead_ids must not contain duplicates")
    validate_advisor(payload.assigned_advisor_id, db)
    leads = list(db.scalars(select(Lead).where(Lead.id.in_(payload.lead_ids)).with_for_update()))
    if len(leads) != len(payload.lead_ids):
        raise HTTPException(status_code=404, detail="One or more leads were not found")
    if any(lead.status != "RECUPERABLE" for lead in leads):
        raise HTTPException(status_code=409, detail="Only recoverable leads can be reassigned in bulk")
    reason = payload.reason.strip()
    reassigned_at = datetime.now(timezone.utc)
    for lead in leads:
        previous = lead.assigned_advisor_id
        lead.assigned_advisor_id = payload.assigned_advisor_id
        lead.status = "PENDIENTE"
        lead.reassigned_from_recovery = True
        lead.reassigned_at = reassigned_at
        db.add(LeadAssignmentHistory(lead_id=lead.id, previous_advisor_id=previous, assigned_advisor_id=lead.assigned_advisor_id, reason=reason, assigned_by_user_id=current_user.id))
        record_audit(db, actor_id=current_user.id, entity_type="lead", entity_id=lead.id, action="ASSIGNED", before={"assigned_advisor_id": previous, "status": "RECUPERABLE"}, after={"assigned_advisor_id": lead.assigned_advisor_id, "status": "PENDIENTE", "reason": reason})
    db.commit()
    return {"assigned_advisor_id": payload.assigned_advisor_id, "lead_ids": payload.lead_ids, "count": len(leads)}


@router.post("/{lead_id}/activities")
def add_activity(lead_id: str, payload: LeadActivityCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    lead = lead_or_404(lead_id, db)
    assert_access(lead, current_user)
    if lead.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="A closed lead cannot receive activities")
    typification = db.get(ContactTypification, payload.typification_id)
    if typification is None:
        raise HTTPException(status_code=422, detail="Typification not found")
    outcome = validate_lead_typification(typification, db)
    next_date = payload.next_action_date or (payload.next_action_at.date() if payload.next_action_at else None)
    if outcome == "AGENDADO" and (next_date is None or payload.next_action_at is None):
        raise HTTPException(status_code=422, detail="An agenda outcome requires a next action date and time")
    if typification.requires_note and not (payload.note or "").strip():
        raise HTTPException(status_code=422, detail="A descriptive note is required for this typification")
    if outcome != "AGENDADO":
        next_date = None
        next_action_at = None
    else:
        next_action_at = payload.next_action_at
    activity = LeadActivity(lead_id=lead.id, advisor_id=current_user.id, typification_id=typification.id, channel=payload.channel,
                            note=payload.note.strip() if payload.note else None, next_action_date=next_date, next_action_at=next_action_at)
    db.add(activity)
    lead.next_action_date, lead.next_action_at = next_date, next_action_at
    lead.status = "RECUPERABLE" if outcome == "NO_RECUPERABLE" else outcome
    db.execute(delete(LeadNotification).where(LeadNotification.lead_id == lead.id))
    record_audit(db, actor_id=current_user.id, entity_type="lead", entity_id=lead.id, action="ACTIVITY_RECORDED", after={"typification_id": typification.id, "status": lead.status})
    db.commit()
    return lead_response(lead, db)


@router.post("/{lead_id}/convert")
def convert_lead(lead_id: str, payload: LeadConversionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    lead = lead_or_404(lead_id, db)
    assert_access(lead, current_user)
    if lead.converted_sale_id or lead.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Lead has already been converted")
    try:
        typification = db.get(ContactTypification, payload.typification_id)
        if typification is None:
            raise HTTPException(status_code=422, detail="Typification not found")
        if validate_lead_typification(typification, db, effective_allowed=True) != "EFECTIVO":
            raise HTTPException(status_code=422, detail="Conversion requires an effective lead typification")
        if typification.requires_note and not (payload.activity_note or "").strip():
            raise HTTPException(status_code=422, detail="A descriptive note is required for this typification")
        if payload.customer_id:
            customer = db.scalar(select(Customer).where(Customer.id == payload.customer_id).with_for_update())
            if customer is None or customer.status != "ACTIVO":
                raise HTTPException(status_code=422, detail="Customer must exist and be active")
            if payload.customer_condition is not None:
                previous_condition = customer.condition
                customer.condition = payload.customer_condition.strip() or None
                if customer.condition != previous_condition:
                    record_audit(db, actor_id=current_user.id, entity_type="customer", entity_id=customer.id,
                                 action="UPDATED", before={"condition": previous_condition},
                                 after={"condition": customer.condition, "source": "lead_conversion"})
        else:
            customer_data = payload.customer
            assert customer_data is not None
            validate_location(customer_data)
            if db.scalar(select(Customer.id).where(Customer.dni == customer_data.dni)):
                raise HTTPException(status_code=409, detail="DNI already exists")
            customer_values = customer_data.model_dump()
            customer_values["email"] = str(customer_data.email).lower() if customer_data.email else None
            customer_values["phone"] = customer_data.phone.strip()
            customer_values["responsible_advisor_id"] = lead.assigned_advisor_id
            customer = Customer(**customer_values)
            db.add(customer)
            db.flush()
            record_audit(db, actor_id=current_user.id, entity_type="customer", entity_id=customer.id, action="CREATED", after={"source": "lead_conversion"})
        products = {item.product_id: db.get(Product, item.product_id) for item in payload.items}
        if any(product is None or not product.is_active for product in products.values()):
            raise HTTPException(status_code=422, detail="All products must exist and be active")
        rules = {product_id: rule_for(product_id, payload.sale_date, db) for product_id in products}
        if any(rule is None for rule in rules.values()):
            raise HTTPException(status_code=422, detail="Each product needs an effective repurchase rule on the sale date")
        if customer.acquisition_channel is None and not confirmed_sale_exists(customer.id, db):
            campaign = db.get(Campaign, lead.campaign_id)
            customer.acquisition_channel, customer.acquisition_channel_detail = "OTROS", campaign.name if campaign else None
        if lead.assigned_advisor_id is None:
            raise HTTPException(status_code=422, detail="Lead must be assigned to an advisor before conversion")
        sale = Sale(customer_id=customer.id, advisor_id=lead.assigned_advisor_id or current_user.id, sale_date=payload.sale_date,
                    notes=payload.notes.strip() if payload.notes else None, status="CONFIRMADA",
                    acquisition_channel=customer.acquisition_channel, acquisition_channel_detail=customer.acquisition_channel_detail)
        db.add(sale)
        db.flush()
        for item in payload.items:
            rule = rules[item.product_id]
            db.add(SaleItem(sale_id=sale.id, product_id=item.product_id, quantity=item.quantity, unit_price=products[item.product_id].unit_price,
                            rule_duration_days=rule.duration_days, rule_alert_days=rule.alert_days, expected_repurchase_date=payload.sale_date + timedelta(days=rule.duration_days)))
        db.flush()
        recompute_chain(customer.id, set(products), db)
        close_alerts_for_repurchase(customer.id, set(products), sale.id, db, current_user.id)
        db.add(LeadActivity(lead_id=lead.id, advisor_id=current_user.id, typification_id=typification.id,
                            channel=payload.channel, note=payload.activity_note.strip() if payload.activity_note else None))
        lead.converted_customer_id, lead.converted_sale_id, lead.converted_at, lead.status = customer.id, sale.id, datetime.now(timezone.utc), "CERRADO_EFECTIVO"
        lead.next_action_date = lead.next_action_at = None
        db.execute(delete(LeadNotification).where(LeadNotification.lead_id == lead.id))
        record_audit(db, actor_id=current_user.id, entity_type="sale", entity_id=sale.id, action="CONFIRMED", after={"customer_id": customer.id, "source": "lead_conversion"})
        record_audit(db, actor_id=current_user.id, entity_type="lead", entity_id=lead.id, action="CONVERTED", after={"converted_customer_id": customer.id, "converted_sale_id": sale.id, "status": lead.status})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"lead": lead_response(lead, db), "sale": sale_response(sale, db)}


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Response:
    lead = lead_or_404(lead_id, db)
    record_audit(db, actor_id=current_user.id, entity_type="lead", entity_id=lead.id, action="HARD_DELETED", before=lead_response(lead, db))
    db.delete(lead)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
