"""add durable historical sale references

Revision ID: 0017_historical_sale_references
Revises: 0016_customer_birth_date_ubigeo
"""

import sqlalchemy as sa
from alembic import op


revision = "0017_historical_sale_references"
down_revision = "0016_customer_birth_date_ubigeo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("external_reference", sa.String(length=120), nullable=True))
    op.create_unique_constraint("uq_sales_external_reference", "sales", ["external_reference"])

    # Cover databases that applied the initial 0016 script before this fix.
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("customers")}
    if "birth_year" in columns:
        op.execute("UPDATE customers SET birth_date = make_date(birth_year, 1, 1) WHERE birth_year IS NOT NULL AND birth_date IS NULL")
    if "sales_district" in columns:
        op.execute("UPDATE customers SET district = sales_district WHERE sales_district IS NOT NULL AND district IS NULL")

    # A different-product purchase must not consume the source alert's unique link.
    op.execute(
        "UPDATE sales SET source_alert_id = NULL WHERE source_alert_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM alerts JOIN sale_items source_item ON source_item.id = alerts.sale_item_id "
        "JOIN sale_items purchased_item ON purchased_item.sale_id = sales.id "
        "WHERE alerts.id = sales.source_alert_id AND purchased_item.product_id = source_item.product_id)"
    )


def downgrade() -> None:
    op.drop_constraint("uq_sales_external_reference", "sales", type_="unique")
    op.drop_column("sales", "external_reference")
