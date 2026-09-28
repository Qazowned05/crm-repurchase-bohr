"""sales, items and duplicate reviews

Revision ID: 0004_sales
Revises: 0003_import_jobs
Create Date: 2026-09-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_sales"
down_revision: str | None = "0003_import_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("advisor_id", sa.String(36), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("acquisition_channel", sa.String(20), nullable=True),
        sa.Column("acquisition_channel_detail", sa.String(255), nullable=True),
        sa.Column("annulled_by_user_id", sa.String(36), nullable=True),
        sa.Column("annulment_reason", sa.Text(), nullable=True),
        sa.Column("annulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["advisor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["annulled_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])
    op.create_index("ix_sales_advisor_id", "sales", ["advisor_id"])
    op.create_index("ix_sales_sale_date", "sales", ["sale_date"])
    op.create_index("ix_sales_status", "sales", ["status"])
    op.create_table(
        "sale_items",
        sa.Column("id", sa.String(36), nullable=False), sa.Column("sale_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("rule_duration_days", sa.Integer(), nullable=False), sa.Column("rule_alert_days", sa.JSON(), nullable=False),
        sa.Column("expected_repurchase_date", sa.Date(), nullable=False), sa.Column("purchase_type", sa.String(20), nullable=True),
        sa.Column("prior_confirmed_item_id", sa.String(36), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prior_confirmed_item_id"], ["sale_items.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("ix_sale_items_product_id", "sale_items", ["product_id"])
    op.create_index("ix_sale_items_prior_confirmed_item_id", "sale_items", ["prior_confirmed_item_id"])
    op.create_table(
        "sales_duplicate_reviews",
        sa.Column("id", sa.String(36), nullable=False), sa.Column("sale_id", sa.String(36), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(36), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sale_id"),
    )
    op.create_index("ix_sales_duplicate_reviews_sale_id", "sales_duplicate_reviews", ["sale_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_duplicate_reviews_sale_id", table_name="sales_duplicate_reviews")
    op.drop_table("sales_duplicate_reviews")
    op.drop_index("ix_sale_items_prior_confirmed_item_id", table_name="sale_items")
    op.drop_index("ix_sale_items_product_id", table_name="sale_items")
    op.drop_index("ix_sale_items_sale_id", table_name="sale_items")
    op.drop_table("sale_items")
    op.drop_index("ix_sales_status", table_name="sales")
    op.drop_index("ix_sales_sale_date", table_name="sales")
    op.drop_index("ix_sales_advisor_id", table_name="sales")
    op.drop_index("ix_sales_customer_id", table_name="sales")
    op.drop_table("sales")
