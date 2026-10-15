"""add business customer identity

Revision ID: 0019_customer_business_identity
Revises: 0018_backfill_item_prices
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0019_customer_business_identity"
down_revision: str | None = "0018_backfill_item_prices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("customer_type", sa.String(length=10), nullable=False, server_default="PERSONA"))
    op.add_column("customers", sa.Column("business_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "business_name")
    op.drop_column("customers", "customer_type")
