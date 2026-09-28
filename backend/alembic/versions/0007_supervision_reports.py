"""add assignment histories for supervision

Revision ID: 0007_supervision_reports
Revises: 0006_alerts
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_supervision_reports"
down_revision: str | None = "0006_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_assignment_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("previous_advisor_id", sa.String(36)),
        sa.Column("assigned_advisor_id", sa.String(36)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["previous_advisor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_advisor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_customer_assignment_history_customer_id", "customer_assignment_history", ["customer_id"])
    op.create_index("ix_customer_assignment_history_assigned_by_user_id", "customer_assignment_history", ["assigned_by_user_id"])
    op.create_table(
        "alert_assignment_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alert_id", sa.String(36), nullable=False),
        sa.Column("previous_advisor_id", sa.String(36)),
        sa.Column("assigned_advisor_id", sa.String(36)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_advisor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_advisor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_alert_assignment_history_alert_id", "alert_assignment_history", ["alert_id"])
    op.create_index("ix_alert_assignment_history_assigned_by_user_id", "alert_assignment_history", ["assigned_by_user_id"])


def downgrade() -> None:
    op.drop_table("alert_assignment_history")
    op.drop_table("customer_assignment_history")
