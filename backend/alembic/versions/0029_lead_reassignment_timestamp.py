"""track the date a recoverable lead is reassigned

Revision ID: 0029_lead_reassigned_at
Revises: 0028_effective_lead_closure
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0029_lead_reassigned_at"
down_revision: str | None = "0028_effective_lead_closure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("reassigned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_leads_reassigned_at", "leads", ["reassigned_at"])


def downgrade() -> None:
    op.drop_index("ix_leads_reassigned_at", table_name="leads")
    op.drop_column("leads", "reassigned_at")
