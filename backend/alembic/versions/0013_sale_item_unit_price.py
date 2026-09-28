"""add sale item unit price

Revision ID: 0013_sale_item_unit_price
Revises: 0012_alert_register_history
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_sale_item_unit_price"
down_revision: str | None = "0012_alert_register_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sale_items", sa.Column("unit_price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("sale_items", "unit_price")
