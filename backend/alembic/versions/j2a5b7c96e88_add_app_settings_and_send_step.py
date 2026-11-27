"""Add app_settings and allow the send pipeline step.

Revision ID: j2a5b7c96e88
Revises: i1f4a6b85d77
Create Date: 2026-11-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.migration_helpers import (
    add_column_if_missing,
    create_index_if_missing,
    create_table_if_missing,
)

revision: str = "j2a5b7c96e88"
down_revision: str | Sequence[str] | None = "i1f4a6b85d77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    create_table_if_missing(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute("ALTER TABLE pipeline_jobs DROP CONSTRAINT IF EXISTS ck_pipeline_jobs_step")
    op.create_check_constraint(
        "ck_pipeline_jobs_step",
        "pipeline_jobs",
        "step IN ('enrich', 'audit', 'research', 'mockup', 'draft', 'send')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM pipeline_jobs WHERE step = 'send'")
    op.drop_constraint("ck_pipeline_jobs_step", "pipeline_jobs", type_="check")
    op.create_check_constraint(
        "ck_pipeline_jobs_step",
        "pipeline_jobs",
        "step IN ('enrich', 'audit', 'research', 'mockup', 'draft')",
    )
    op.drop_table("app_settings")
