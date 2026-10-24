"""Add configurable campaign colors.

Revision ID: 0033_campaign_colors
Revises: 0032_lead_dni
"""

from alembic import op
import sqlalchemy as sa


revision = "0033_campaign_colors"
down_revision = "0032_lead_dni"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("color", sa.String(length=7), nullable=False, server_default="#176b87"))


def downgrade() -> None:
    op.drop_column("campaigns", "color")
