"""link replacement sales to annulled sales

Revision ID: 0005_sale_replacements
Revises: 0004_sales
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_sale_replacements"
down_revision: str | None = "0004_sales"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("replaces_sale_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_sales_replaces_sale_id", "sales", "sales", ["replaces_sale_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_sales_replaces_sale_id", "sales", ["replaces_sale_id"])
    op.create_index("ix_sales_replaces_sale_id", "sales", ["replaces_sale_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_replaces_sale_id", table_name="sales")
    op.drop_constraint("uq_sales_replaces_sale_id", "sales", type_="unique")
    op.drop_constraint("fk_sales_replaces_sale_id", "sales", type_="foreignkey")
    op.drop_column("sales", "replaces_sale_id")
