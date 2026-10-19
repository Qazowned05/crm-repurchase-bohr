"""persist notification dismissal

Revision ID: 0022_notification_dismissal
Revises: 0021_alert_notifications
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0022_notification_dismissal"
down_revision: str | None = "0021_alert_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alert_notifications", sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("alert_notifications", "dismissed_at")
