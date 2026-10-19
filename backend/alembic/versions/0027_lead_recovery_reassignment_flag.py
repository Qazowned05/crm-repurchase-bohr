"""mark leads reassigned from recovery

Revision ID: 0027_recovery_reassigned
Revises: 0026_seed_lead_outcomes
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0027_recovery_reassigned"
down_revision: str | None = "0026_seed_lead_outcomes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("reassigned_from_recovery", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("leads", "reassigned_from_recovery")
