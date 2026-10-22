"""Add lead research table for Tavily and Exa intelligence.

Revision ID: f8c1d3e52a44
Revises: e7b9a1c24f33
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f8c1d3e52a44"
down_revision: str | Sequence[str] | None = "e7b9a1c24f33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lead_researches" not in set(inspector.get_table_names()):
        op.create_table(
            "lead_researches",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("lead_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=32), server_default=sa.text("'PENDING'"), nullable=False),
            sa.Column("query_used", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("research_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("raw_tavily", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("raw_exa", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("lead_id"),
        )
        op.create_index("ix_lead_researches_lead_id", "lead_researches", ["lead_id"], unique=True)
        op.create_index("ix_lead_researches_status", "lead_researches", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lead_researches" in set(inspector.get_table_names()):
        op.drop_index("ix_lead_researches_status", table_name="lead_researches")
        op.drop_index("ix_lead_researches_lead_id", table_name="lead_researches")
        op.drop_table("lead_researches")
