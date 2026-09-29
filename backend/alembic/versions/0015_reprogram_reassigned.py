"""mark scheduled reassignments as reprogrammed

Revision ID: 0015_reprogram_reassigned
Revises: 0014_product_unit_price
"""

from alembic import op


revision = "0015_reprogram_reassigned"
down_revision = "0014_product_unit_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE alerts SET status = 'REPROGRAMADO' "
        "WHERE status = 'REASIGNADO' AND next_action_date IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE alerts SET status = 'REASIGNADO' "
        "WHERE status = 'REPROGRAMADO' AND next_action_date IS NOT NULL"
    )
