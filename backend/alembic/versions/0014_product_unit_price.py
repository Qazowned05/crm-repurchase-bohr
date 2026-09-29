"""add catalog unit price

Revision ID: 0014_product_unit_price
Revises: 0013_sale_item_unit_price
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_product_unit_price"
down_revision = "0013_sale_item_unit_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("unit_price", sa.Numeric(12, 2), nullable=True))
    op.execute("UPDATE products SET unit_price = 1 WHERE unit_price IS NULL")
    op.alter_column("products", "unit_price", nullable=False)


def downgrade() -> None:
    op.drop_column("products", "unit_price")
