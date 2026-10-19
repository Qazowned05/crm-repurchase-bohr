"""keep non-effective lead outcomes recoverable

Revision ID: 0028_effective_lead_closure
Revises: 0027_recovery_reassigned
"""
from collections.abc import Sequence

from alembic import op


revision: str = "0028_effective_lead_closure"
down_revision: str | None = "0027_recovery_reassigned"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE contact_typifications SET lead_outcome = 'RECUPERABLE' WHERE lead_outcome = 'NO_RECUPERABLE'")
    op.execute("UPDATE leads SET status = 'RECUPERABLE' WHERE status = 'CERRADO_NO_RECUPERABLE'")


def downgrade() -> None:
    pass
