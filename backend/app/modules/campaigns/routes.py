from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.pagination import paginate_items
from app.dependencies import get_current_user, require_roles
from app.modules.auth.models import User
from app.modules.campaigns.models import Campaign
from app.modules.campaigns.schemas import CampaignCreate, CampaignResponse, CampaignUpdate

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.get("", response_model=None)
def list_campaigns(active_only: bool = False, page: int | None = Query(default=None, ge=1), page_size: int | None = Query(default=None, ge=1, le=200), _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Campaign] | dict:
    query = select(Campaign).order_by(Campaign.name)
    if active_only:
        query = query.where(Campaign.is_active.is_(True))
    return paginate_items(list(db.scalars(query)), page, page_size)


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Campaign:
    record = Campaign(**payload.model_dump())
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Campaign name already exists")
    record_audit(db, actor_id=current_user.id, entity_type="campaign", entity_id=record.id, action="CREATED", after=payload.model_dump())
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(campaign_id: str, payload: CampaignUpdate, current_user: User = Depends(require_roles("SUPERVISOR", "ADMIN")), db: Session = Depends(get_db)) -> Campaign:
    record = db.get(Campaign, campaign_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(record, field) for field in changes}
    for field, value in changes.items():
        setattr(record, field, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Campaign name already exists")
    record_audit(db, actor_id=current_user.id, entity_type="campaign", entity_id=record.id, action="UPDATED", before=before, after=changes)
    db.commit()
    db.refresh(record)
    return record
