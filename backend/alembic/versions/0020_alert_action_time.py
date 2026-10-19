"""add scheduled action time to alerts

Revision ID: 0020_alert_action_time
Revises: 0019_customer_business_identity
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0020_alert_action_time"
down_revision: str | None = "0019_customer_business_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_alerts_next_action_at", "alerts", ["next_action_at"])
    op.add_column("alert_contact_attempts", sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("alert_contact_attempts", "next_action_at")
    op.drop_index("ix_alerts_next_action_at", table_name="alerts")
    op.drop_column("alerts", "next_action_at")
