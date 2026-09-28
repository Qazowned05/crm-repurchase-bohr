"""import jobs and validation errors

Revision ID: 0003_import_jobs
Revises: 0002_customers_products_audit
Create Date: 2026-09-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_import_jobs"
down_revision: str | None = "0002_customers_products_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("import_jobs",
        sa.Column("id", sa.String(36), nullable=False), sa.Column("import_type", sa.String(20), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=False), sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("source_file", sa.LargeBinary(), nullable=False), sa.Column("state", sa.String(30), nullable=False),
        sa.Column("allow_updates", sa.Boolean(), nullable=False), sa.Column("allow_reassignment", sa.Boolean(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False), sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("new_rows", sa.Integer(), nullable=False), sa.Column("update_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False), sa.Column("rows_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_import_jobs_import_type", "import_jobs", ["import_type"])
    op.create_index("ix_import_jobs_created_by_user_id", "import_jobs", ["created_by_user_id"])
    op.create_table("import_row_errors",
        sa.Column("id", sa.String(36), nullable=False), sa.Column("import_job_id", sa.String(36), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=True), sa.Column("field", sa.String(120), nullable=True),
        sa.Column("message", sa.String(500), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_import_row_errors_import_job_id", "import_row_errors", ["import_job_id"])


def downgrade() -> None:
    op.drop_index("ix_import_row_errors_import_job_id", table_name="import_row_errors")
    op.drop_table("import_row_errors")
    op.drop_index("ix_import_jobs_created_by_user_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_import_type", table_name="import_jobs")
    op.drop_table("import_jobs")
