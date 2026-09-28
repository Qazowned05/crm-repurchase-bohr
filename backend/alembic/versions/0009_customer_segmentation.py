"""add optional customer segmentation fields

Revision ID: 0009_customer_segmentation
Revises: 0008_contact_typifications
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_customer_segmentation"
down_revision: str | None = "0008_contact_typifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("condition", sa.String(length=500), nullable=True))
    op.add_column("customers", sa.Column("birth_year", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("sales_district", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "sales_district")
    op.drop_column("customers", "birth_year")
    op.drop_column("customers", "condition")
