from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


def record_audit(
    db: Session,
    *,
    actor_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_data=jsonable_encoder(before),
            after_data=jsonable_encoder(after),
        )
    )
