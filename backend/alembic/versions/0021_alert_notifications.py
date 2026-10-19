"""add persistent alert notifications

Revision ID: 0021_alert_notifications
Revises: 0020_alert_action_time
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0021_alert_notifications"
down_revision: str | None = "0020_alert_action_time"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("alert_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", "user_id", "scheduled_for", name="uq_alert_notifications_schedule"),
    )
    op.create_index("ix_alert_notifications_alert_id", "alert_notifications", ["alert_id"])
    op.create_index("ix_alert_notifications_user_id", "alert_notifications", ["user_id"])
    op.create_index("ix_alert_notifications_scheduled_for", "alert_notifications", ["scheduled_for"])


def downgrade() -> None:
    op.drop_table("alert_notifications")
