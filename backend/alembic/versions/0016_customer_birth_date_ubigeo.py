"""replace customer birth year and free district with UBIGEO fields

Revision ID: 0016_customer_birth_date_ubigeo
Revises: 0015_reprogram_reassigned
"""

import sqlalchemy as sa
from alembic import op


revision = "0016_customer_birth_date_ubigeo"
down_revision = "0015_reprogram_reassigned"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("customers", sa.Column("department", sa.String(length=120), nullable=True))
    op.add_column("customers", sa.Column("province", sa.String(length=120), nullable=True))
    op.add_column("customers", sa.Column("district", sa.String(length=120), nullable=True))
    op.add_column("customers", sa.Column("ubigeo", sa.String(length=6), nullable=True))
    # Retain the information represented by the legacy, less precise fields.
    # January 1 is deliberately used as an unknown-day/month placeholder.
    op.execute("UPDATE customers SET birth_date = make_date(birth_year, 1, 1) WHERE birth_year IS NOT NULL")
    op.execute("UPDATE customers SET district = sales_district WHERE sales_district IS NOT NULL")
    op.drop_column("customers", "birth_year")
    op.drop_column("customers", "sales_district")


def downgrade() -> None:
    op.add_column("customers", sa.Column("birth_year", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("sales_district", sa.String(length=120), nullable=True))
    op.drop_column("customers", "ubigeo")
    op.drop_column("customers", "district")
    op.drop_column("customers", "province")
    op.drop_column("customers", "department")
    op.drop_column("customers", "birth_date")
