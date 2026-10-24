"""add lead enrichment and typification scope

Revision ID: 0031_lead_enrichment_scope
Revises: 0030_campaigns
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0031_lead_enrichment_scope"
down_revision: str | None = "0030_campaigns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("condition", sa.String(500), nullable=True))
    op.add_column("contact_typifications", sa.Column("scope", sa.String(20), nullable=False, server_default="BOTH"))
    op.execute("UPDATE contact_typifications SET scope = 'LEADS_ONLY', lead_outcome = 'EFECTIVO' WHERE code = 'PEDIDO_CONFIRMADO'")
    op.execute("""
        INSERT INTO contact_typifications (id, code, name, is_active, requires_next_action, requires_note, requires_close, lead_outcome, scope, created_at, updated_at)
        SELECT '00000000-0000-0000-0000-000000000031', 'PEDIDO_CONFIRMADO', 'Pedido de recompra confirmado', true, false, false, false, 'EFECTIVO', 'LEADS_ONLY', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM contact_typifications WHERE code = 'PEDIDO_CONFIRMADO')
    """)


def downgrade() -> None:
    op.drop_column("contact_typifications", "scope")
    op.drop_column("leads", "condition")
