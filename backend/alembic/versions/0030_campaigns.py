"""add configurable lead campaigns

Revision ID: 0030_campaigns
Revises: 0029_lead_reassigned_at
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_campaigns"
down_revision: str | None = "0029_lead_reassigned_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("campaigns", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_campaigns_is_active", "campaigns", ["is_active"])
    op.add_column("leads", sa.Column("campaign_id", sa.String(36), nullable=True))
    op.create_index("ix_leads_campaign_id", "leads", ["campaign_id"])
    bind = op.get_bind()
    campaigns = [("00000000-0000-0000-0000-000000000001", "REDES_SOCIALES"), ("00000000-0000-0000-0000-000000000002", "COMERCIAL_TV"), ("00000000-0000-0000-0000-000000000003", "REFERIDO")]
    for campaign_id, name in campaigns:
        bind.execute(sa.text("INSERT INTO campaigns (id, name, is_active, created_at, updated_at) VALUES (:id, :name, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": campaign_id, "name": name})
        bind.execute(sa.text("UPDATE leads SET campaign_id = :id WHERE source = :name"), {"id": campaign_id, "name": name})
    op.alter_column("leads", "campaign_id", nullable=False)
    op.create_foreign_key("fk_leads_campaign_id", "leads", "campaigns", ["campaign_id"], ["id"], ondelete="RESTRICT")
    op.drop_index("ix_leads_source", table_name="leads")
    op.drop_column("leads", "source")


def downgrade() -> None:
    op.add_column("leads", sa.Column("source", sa.String(30), nullable=True))
    op.execute("UPDATE leads SET source = (SELECT name FROM campaigns WHERE campaigns.id = leads.campaign_id)")
    op.alter_column("leads", "source", nullable=False)
    op.create_index("ix_leads_source", "leads", ["source"])
    op.drop_constraint("fk_leads_campaign_id", "leads", type_="foreignkey")
    op.drop_index("ix_leads_campaign_id", table_name="leads")
    op.drop_column("leads", "campaign_id")
    op.drop_index("ix_campaigns_is_active", table_name="campaigns")
    op.drop_table("campaigns")
