"""Add automation runs, outreach attempts and exclusions.

Revision ID: k3b6c8d07f99
Revises: j2a5b7c96e88
Create Date: 2026-11-28

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

revision: str = "k3b6c8d07f99"
down_revision: str | Sequence[str] | None = "j2a5b7c96e88"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    create_table_if_missing(
        "automation_runs",
        _id(),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("run_key", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'RUNNING'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'OK', 'FAILED', 'SKIPPED')", name="ck_automation_runs_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index_if_missing("uq_automation_runs_run_key", "automation_runs", ["run_key"], unique=True)
    create_index_if_missing("ix_automation_runs_kind_created", "automation_runs", ["kind", "created_at"])

    create_table_if_missing(
        "outreach_attempts",
        _id(),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("email_id", sa.Uuid(), nullable=True),
        sa.Column("outreach_message_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("sequence_step", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=True),
        sa.Column("framework", sa.String(length=64), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("mockup_included", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("automatic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=16), server_default=sa.text("'none'"), nullable=False),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('first', 'followup')", name="ck_outreach_attempts_kind"),
        sa.CheckConstraint(
            "outcome IN ('none', 'bounce', 'unsubscribe', 'reply', 'negative', 'positive', "
            "'interested', 'meeting', 'won')",
            name="ck_outreach_attempts_outcome",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_id"], ["lead_emails.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["outreach_message_id"], ["outreach_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index_if_missing("ix_outreach_attempts_lead_id", "outreach_attempts", ["lead_id"])
    create_index_if_missing("ix_outreach_attempts_sent_at", "outreach_attempts", ["sent_at"])
    create_index_if_missing(
        "ix_outreach_attempts_category_country", "outreach_attempts", ["category", "country"]
    )
    create_index_if_missing("uq_outreach_attempts_email_id", "outreach_attempts", ["email_id"], unique=True)

    create_table_if_missing(
        "lead_exclusions",
        _id(),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        _created(),
        sa.CheckConstraint(
            "kind IN ('domain', 'email', 'name', 'category')", name="ck_lead_exclusions_kind"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index_if_missing("uq_lead_exclusions_kind_value", "lead_exclusions", ["kind", "value"], unique=True)


def downgrade() -> None:
    op.drop_table("lead_exclusions")
    op.drop_table("outreach_attempts")
    op.drop_table("automation_runs")
