"""add managed alert register history fields

Revision ID: 0012_alert_register_history
Revises: 0011_normalize_product_catalog
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_alert_register_history"
down_revision: str | None = "0011_normalize_product_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("closure_reason", sa.Text(), nullable=True))
    with op.batch_alter_table("alert_contact_attempts") as batch_op:
        batch_op.add_column(sa.Column("typification_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_alert_contact_attempts_typification_id", "contact_typifications", ["typification_id"], ["id"], ondelete="RESTRICT"
        )
        batch_op.create_index("ix_alert_contact_attempts_typification_id", ["typification_id"])


def downgrade() -> None:
    with op.batch_alter_table("alert_contact_attempts") as batch_op:
        batch_op.drop_index("ix_alert_contact_attempts_typification_id")
        batch_op.drop_constraint("fk_alert_contact_attempts_typification_id", type_="foreignkey")
        batch_op.drop_column("typification_id")
    op.drop_column("alerts", "closure_reason")
