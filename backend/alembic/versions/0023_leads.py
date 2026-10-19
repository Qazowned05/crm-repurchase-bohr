"""add leads and lead notifications

Revision ID: 0023_leads
Revises: 0022_notification_dismissal
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0023_leads"
down_revision: str | None = "0022_notification_dismissal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("leads", sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("full_name", sa.String(length=255), nullable=False), sa.Column("phone", sa.String(length=30), nullable=False), sa.Column("email", sa.String(length=255)), sa.Column("source", sa.String(length=30), nullable=False), sa.Column("initial_product_id", sa.String(length=36), sa.ForeignKey("products.id", ondelete="RESTRICT")), sa.Column("notes", sa.Text()), sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDIENTE"), sa.Column("assigned_advisor_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("next_action_date", sa.Date()), sa.Column("next_action_at", sa.DateTime(timezone=True)), sa.Column("converted_customer_id", sa.String(length=36), sa.ForeignKey("customers.id", ondelete="RESTRICT")), sa.Column("converted_sale_id", sa.String(length=36), sa.ForeignKey("sales.id", ondelete="RESTRICT", name="fk_leads_converted_sale_id"), unique=True), sa.Column("converted_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    for table, columns in (("leads", ["phone", "source", "status", "assigned_advisor_id", "next_action_date", "next_action_at", "converted_customer_id"]),):
        for column in columns: op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_table("lead_activities", sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("lead_id", sa.String(length=36), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False), sa.Column("advisor_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("typification_id", sa.String(length=36), sa.ForeignKey("contact_typifications.id", ondelete="RESTRICT"), nullable=False), sa.Column("channel", sa.String(length=20), nullable=False), sa.Column("note", sa.Text()), sa.Column("next_action_date", sa.Date()), sa.Column("next_action_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("lead_assignment_history", sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("lead_id", sa.String(length=36), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False), sa.Column("previous_advisor_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("assigned_advisor_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("reason", sa.Text(), nullable=False), sa.Column("assigned_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("lead_notifications", sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("lead_id", sa.String(length=36), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("dismissed_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("lead_id", "user_id", "scheduled_for", name="uq_lead_notifications_schedule"))


def downgrade() -> None:
    op.drop_table("lead_notifications")
    op.drop_table("lead_assignment_history")
    op.drop_table("lead_activities")
    op.drop_table("leads")
