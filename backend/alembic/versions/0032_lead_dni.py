"""Add DNI to leads.

Revision ID: 0032_lead_dni
Revises: 0031_lead_enrichment_scope
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_lead_dni"
down_revision = "0031_lead_enrichment_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("dni", sa.String(length=20), nullable=True))
    op.create_index("ix_leads_dni", "leads", ["dni"])


def downgrade() -> None:
    op.drop_index("ix_leads_dni", table_name="leads")
    op.drop_column("leads", "dni")
