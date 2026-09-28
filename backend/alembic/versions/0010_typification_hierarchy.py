"""add contact typification hierarchy

Revision ID: 0010_typification_hierarchy
Revises: 0009_customer_segmentation
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_typification_hierarchy"
down_revision: str | None = "0009_customer_segmentation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contact_typifications", sa.Column("parent_id", sa.String(length=36), nullable=True))
    op.create_index("ix_contact_typifications_parent_id", "contact_typifications", ["parent_id"])
    op.create_foreign_key("fk_contact_typifications_parent_id", "contact_typifications", "contact_typifications", ["parent_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_contact_typifications_parent_id", "contact_typifications", type_="foreignkey")
    op.drop_index("ix_contact_typifications_parent_id", table_name="contact_typifications")
    op.drop_column("contact_typifications", "parent_id")
