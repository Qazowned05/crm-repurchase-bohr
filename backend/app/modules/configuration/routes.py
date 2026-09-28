from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.configuration.models import AlertOperationalSettings, ContactTypification
from app.modules.configuration.schemas import (
    AlertOperationalSettingsResponse,
    AlertOperationalSettingsUpdate,
    ContactTypificationCreate,
    ContactTypificationResponse,
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


@router.post("/contact-typifications", response_model=ContactTypificationResponse, status_code=201)
def create_contact_typification(payload: ContactTypificationCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> ContactTypification:
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
    before = {field: getattr(record, field) for field in payload.model_fields_set}
    for field, value in payload.model_dump(exclude_unset=True).items():
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
