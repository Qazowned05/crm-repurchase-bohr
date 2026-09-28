"""add repurchase alerts and contact attempts

Revision ID: 0006_alerts
Revises: 0005_sale_replacements
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_alerts"
down_revision: str | None = "0005_sale_replacements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("alerts", sa.Column("id", sa.String(36), primary_key=True), sa.Column("sale_item_id", sa.String(36), nullable=False), sa.Column("assigned_advisor_id", sa.String(36)), sa.Column("alert_date", sa.Date(), nullable=False), sa.Column("expected_repurchase_date", sa.Date(), nullable=False), sa.Column("status", sa.String(40), nullable=False), sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("next_action_date", sa.Date()), sa.Column("last_contact_at", sa.DateTime(timezone=True)), sa.Column("closed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["sale_item_id"], ["sale_items.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["assigned_advisor_id"], ["users.id"], ondelete="SET NULL"), sa.UniqueConstraint("sale_item_id", "alert_date", name="uq_alerts_sale_item_alert_date"))
    for column in ("sale_item_id", "assigned_advisor_id", "alert_date", "expected_repurchase_date", "status", "next_action_date"):
        op.create_index(f"ix_alerts_{column}", "alerts", [column])
    op.create_table("alert_contact_attempts", sa.Column("id", sa.String(36), primary_key=True), sa.Column("alert_id", sa.String(36), nullable=False), sa.Column("advisor_id", sa.String(36), nullable=False), sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("channel", sa.String(20), nullable=False), sa.Column("result", sa.String(40), nullable=False), sa.Column("note", sa.Text()), sa.Column("next_action_date", sa.Date()), sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["advisor_id"], ["users.id"], ondelete="RESTRICT"))
    op.create_index("ix_alert_contact_attempts_alert_id", "alert_contact_attempts", ["alert_id"])
    op.create_index("ix_alert_contact_attempts_advisor_id", "alert_contact_attempts", ["advisor_id"])
    op.add_column("sales", sa.Column("source_alert_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_sales_source_alert_id", "sales", "alerts", ["source_alert_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_sales_source_alert_id", "sales", ["source_alert_id"])
    op.create_index("ix_sales_source_alert_id", "sales", ["source_alert_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_source_alert_id", table_name="sales")
    op.drop_constraint("uq_sales_source_alert_id", "sales", type_="unique")
    op.drop_constraint("fk_sales_source_alert_id", "sales", type_="foreignkey")
    op.drop_column("sales", "source_alert_id")
    op.drop_table("alert_contact_attempts")
    op.drop_table("alerts")
