from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.configuration.models import AlertOperationalSettings, ContactTypification
from app.modules.configuration.schemas import (
    AlertOperationalSettingsResponse,
    AlertOperationalSettingsUpdate,
    ContactTypificationCreate,
    ContactTypificationResponse,
    ContactTypificationTreeResponse,
    ContactTypificationUpdate,
)

router = APIRouter(prefix="/api/v1/configuration", tags=["configuration"])


def operational_settings(db: Session) -> AlertOperationalSettings:
    record = db.get(AlertOperationalSettings, 1)
    if record is None:
        record = AlertOperationalSettings(id=1, advisor_visibility_days=settings.alert_active_window_days)
        db.add(record)
        db.flush()
    return record


@router.get("/contact-typifications", response_model=list[ContactTypificationResponse])
def list_contact_typifications(current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> list[ContactTypification]:
    return list(db.scalars(select(ContactTypification).order_by(ContactTypification.code)))


@router.get("/contact-typifications/tree", response_model=list[ContactTypificationTreeResponse])
def contact_typification_tree(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    nodes = {
        record.id: {"id": record.id, "parent_id": record.parent_id, "code": record.code, "name": record.name,
                    "is_active": record.is_active, "requires_next_action": record.requires_next_action,
                    "requires_note": record.requires_note, "requires_close": record.requires_close,
                    "created_at": record.created_at, "updated_at": record.updated_at, "children": []}
        for record in db.scalars(select(ContactTypification).order_by(ContactTypification.code))
    }
    roots = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


def validate_parent(parent_id: str | None, record_id: str | None, db: Session) -> None:
    if parent_id is None:
        return
    parent = db.get(ContactTypification, parent_id)
    if parent is None:
        raise HTTPException(status_code=422, detail="Parent contact typification not found")
    if parent.id == record_id:
        raise HTTPException(status_code=422, detail="A contact typification cannot be its own parent")
    ancestor = parent
    visited: set[str] = set()
    while ancestor is not None:
        if ancestor.id in visited or ancestor.id == record_id:
            raise HTTPException(status_code=422, detail="Parent selection would create a typification cycle")
        visited.add(ancestor.id)
        ancestor = db.get(ContactTypification, ancestor.parent_id) if ancestor.parent_id else None


@router.post("/contact-typifications", response_model=ContactTypificationResponse, status_code=201)
def create_contact_typification(payload: ContactTypificationCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> ContactTypification:
    validate_parent(payload.parent_id, None, db)
    record = ContactTypification(**payload.model_dump())
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Contact typification code already exists")
    record_audit(db, actor_id=current_user.id, entity_type="contact_typification", entity_id=record.id, action="CREATED", after=payload.model_dump())
    db.commit()
    db.refresh(record)
    return record


@router.patch("/contact-typifications/{typification_id}", response_model=ContactTypificationResponse)
def update_contact_typification(typification_id: str, payload: ContactTypificationUpdate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> ContactTypification:
    record = db.get(ContactTypification, typification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Contact typification not found")
    changes = payload.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        validate_parent(changes["parent_id"], record.id, db)
    before = {field: getattr(record, field) for field in payload.model_fields_set}
    for field, value in changes.items():
        setattr(record, field, value.strip() if field == "name" else value)
    record_audit(db, actor_id=current_user.id, entity_type="contact_typification", entity_id=record.id, action="UPDATED", before=before, after=payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(record)
    return record


@router.delete("/contact-typifications/{typification_id}", status_code=204)
def delete_contact_typification(typification_id: str, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> None:
    record = db.get(ContactTypification, typification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Contact typification not found")
    if db.scalar(select(ContactTypification.id).where(ContactTypification.parent_id == record.id).limit(1)):
        raise HTTPException(status_code=409, detail="Contact typification cannot be deleted while it has children")
    from app.modules.alerts.models import AlertContactAttempt
    if db.scalar(select(AlertContactAttempt.id).where(AlertContactAttempt.result == record.code).limit(1)):
        raise HTTPException(status_code=409, detail="Contact typification cannot be deleted while referenced by contact attempts")
    record_audit(db, actor_id=current_user.id, entity_type="contact_typification", entity_id=record.id, action="DELETED", before={"code": record.code, "name": record.name})
    db.delete(record)
    db.commit()


@router.get("/alert-settings", response_model=AlertOperationalSettingsResponse)
def get_alert_settings(current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> AlertOperationalSettings:
    record = operational_settings(db)
    db.commit()
    return record


@router.put("/alert-settings", response_model=AlertOperationalSettingsResponse)
def update_alert_settings(payload: AlertOperationalSettingsUpdate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> AlertOperationalSettings:
    record = operational_settings(db)
    before = {field: getattr(record, field) for field in type(payload).model_fields}
    for field, value in payload.model_dump().items():
        setattr(record, field, value)
    record_audit(db, actor_id=current_user.id, entity_type="alert_operational_settings", entity_id="1", action="UPDATED", before=before, after=payload.model_dump())
    db.commit()
    db.refresh(record)
    return record
