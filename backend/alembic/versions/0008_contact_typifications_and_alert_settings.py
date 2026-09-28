"""add configurable contact typifications and alert settings

Revision ID: 0008_contact_typifications
Revises: 0007_supervision_reports
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_contact_typifications"
down_revision: str | None = "0007_supervision_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_typifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requires_next_action", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_note", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_close", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_contact_typifications_code", "contact_typifications", ["code"])
    op.create_table(
        "alert_operational_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("advisor_visibility_days", sa.Integer(), nullable=False),
        sa.Column("maximum_attempts", sa.Integer(), nullable=False),
        sa.Column("stale_days", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("INSERT INTO alert_operational_settings (id, advisor_visibility_days, maximum_attempts, stale_days, updated_at) VALUES (1, 30, 3, 7, CURRENT_TIMESTAMP)")


def downgrade() -> None:
    op.drop_table("alert_operational_settings")
    op.drop_index("ix_contact_typifications_code", table_name="contact_typifications")
    op.drop_table("contact_typifications")
