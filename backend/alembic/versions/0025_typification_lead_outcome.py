"""add lead outcome to contact typifications

Revision ID: 0025_typif_lead_outcome
Revises: 0024_multi_lead_customer
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0025_typif_lead_outcome"
down_revision: str | None = "0024_multi_lead_customer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contact_typifications", sa.Column("lead_outcome", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("contact_typifications", "lead_outcome")
