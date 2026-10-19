"""allow multiple lead conversions per customer

Revision ID: 0024_multi_lead_customer
Revises: 0023_leads
"""
from collections.abc import Sequence

from alembic import op


revision: str = "0024_multi_lead_customer"
down_revision: str | None = "0023_leads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("leads_converted_customer_id_key", "leads", type_="unique")
    op.create_index("ix_leads_converted_customer_id", "leads", ["converted_customer_id"])


def downgrade() -> None:
    op.drop_index("ix_leads_converted_customer_id", table_name="leads")
    op.create_unique_constraint("leads_converted_customer_id_key", "leads", ["converted_customer_id"])
