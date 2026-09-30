"""backfill legacy sale item prices

Revision ID: 0018_backfill_item_prices
Revises: 0017_historical_sale_references
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0018_backfill_item_prices"
down_revision: str | None = "0017_historical_sale_references"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0013 added this nullable column without populating existing sale snapshots.
    op.execute(
        "UPDATE sale_items SET unit_price = ("
        "SELECT products.unit_price FROM products WHERE products.id = sale_items.product_id"
        ") WHERE unit_price IS NULL"
    )


def downgrade() -> None:
    # Historical snapshots cannot be safely distinguished from newly created prices.
    pass
