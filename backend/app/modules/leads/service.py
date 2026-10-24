from datetime import datetime, timedelta, timezone
import logging
from threading import Event, Thread

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.auth.models import User
from app.modules.campaigns.models import Campaign
from app.modules.configuration.models import ContactTypification
from app.modules.leads.models import Lead, LeadActivity, LeadNotification
from app.modules.products.models import Product

logger = logging.getLogger(__name__)
_scheduler_stop = Event()
_scheduler_thread: Thread | None = None


def lead_response(lead: Lead, db: Session) -> dict:
    advisor = db.get(User, lead.assigned_advisor_id) if lead.assigned_advisor_id else None
    product = db.get(Product, lead.initial_product_id) if lead.initial_product_id else None
    campaign = db.get(Campaign, lead.campaign_id)
    latest_typification = db.scalar(
        select(ContactTypification)
        .join(LeadActivity, LeadActivity.typification_id == ContactTypification.id)
        .where(LeadActivity.lead_id == lead.id)
        .order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc())
        .limit(1)
    )
    return {
        **{column.name: getattr(lead, column.name) for column in Lead.__table__.columns},
        "assigned_advisor_name": advisor.full_name if advisor else None,
        "assigned_advisor_email": advisor.email if advisor else None,
        "initial_product_code": product.code if product else None,
        "initial_product_name": product.name if product else None,
        "campaign_name": campaign.name if campaign else None,
        "campaign_is_active": campaign.is_active if campaign else None,
        "latest_typification_id": latest_typification.id if latest_typification else None,
        "latest_typification_code": latest_typification.code if latest_typification else None,
        "latest_typification_name": latest_typification.name if latest_typification else None,
        "latest_typification_lead_outcome": latest_typification.lead_outcome if latest_typification else None,
    }


def generate_due_lead_notifications(db: Session) -> int:
    now = datetime.now(timezone.utc)
    leads = db.scalars(select(Lead).where(
        Lead.status == "AGENDADO", Lead.assigned_advisor_id.is_not(None),
        Lead.next_action_at >= now, Lead.next_action_at <= now + timedelta(minutes=5),
    ))
    monitors = set(db.scalars(select(User.id).where(User.is_active.is_(True), User.role.in_({"SUPERVISOR", "ADMIN"}))))
    created = 0
    for lead in leads:
        for user_id in monitors | {lead.assigned_advisor_id}:
            exists = db.scalar(select(LeadNotification.id).where(
                LeadNotification.lead_id == lead.id, LeadNotification.user_id == user_id,
                LeadNotification.scheduled_for == lead.next_action_at,
            ))
            if exists is None:
                db.add(LeadNotification(lead_id=lead.id, user_id=user_id, scheduled_for=lead.next_action_at))
                created += 1
    return created


def _scheduler_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            generate_due_lead_notifications(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Lead notification generation failed")
        finally:
            db.close()
        if _scheduler_stop.wait(settings.alert_scheduler_poll_seconds):
            return


def start_lead_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = Thread(target=_scheduler_loop, name="lead-scheduler", daemon=True)
    _scheduler_thread.start()


def stop_lead_scheduler() -> None:
    global _scheduler_thread
    _scheduler_stop.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)
        _scheduler_thread = None
