"""Add the automation job queue and a per-lead pause flag.

Revision ID: i1f4a6b85d77
Revises: h0e3f5a74c66
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

revision: str = "i1f4a6b85d77"
down_revision: str | Sequence[str] | None = "h0e3f5a74c66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    add_column_if_missing(
        "leads",
        sa.Column("pipeline_paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    add_column_if_missing(
        "leads", sa.Column("pipeline_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    create_table_if_missing(
        "pipeline_jobs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'QUEUED'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'DONE', 'SKIPPED', 'FAILED')",
            name="ck_pipeline_jobs_status",
        ),
        sa.CheckConstraint(
            "step IN ('enrich', 'audit', 'research', 'mockup', 'draft')",
            name="ck_pipeline_jobs_step",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index_if_missing("ix_pipeline_jobs_lead_id", "pipeline_jobs", ["lead_id"])
    create_index_if_missing("ix_pipeline_jobs_status_run_after", "pipeline_jobs", ["status", "run_after"])
    create_index_if_missing(
        "uq_pipeline_jobs_open",
        "pipeline_jobs",
        ["lead_id", "step"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_table("pipeline_jobs")
    op.drop_column("leads", "pipeline_checked_at")
    op.drop_column("leads", "pipeline_paused")
