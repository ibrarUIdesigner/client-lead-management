"""Add daily lead discovery.

Revision ID: c4d8e2a71b90
Revises: b7e4c1a92d08
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d8e2a71b90"
down_revision: str | Sequence[str] | None = "b7e4c1a92d08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "leads" in tables:
        lead_columns = {column["name"] for column in inspector.get_columns("leads")}
        lead_indexes = {index["name"] for index in inspector.get_indexes("leads")}
        if "source_key" not in lead_columns:
            op.add_column("leads", sa.Column("source_key", sa.String(length=300), nullable=True))
        if "uq_leads_source_key" not in lead_indexes:
            op.create_index("uq_leads_source_key", "leads", ["source_key"], unique=True)

    if "discovery_searches" not in tables:
        op.create_table(
            "discovery_searches",
            sa.Column(
                "id",
                sa.Uuid(),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("category", sa.String(length=80), nullable=False),
            sa.Column("city", sa.String(length=120), nullable=False),
            sa.Column("country", sa.String(length=120), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "use_openstreetmap",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("use_google", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    if "discovery_runs" not in tables:
        op.create_table(
            "discovery_runs",
            sa.Column(
                "id",
                sa.Uuid(),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("search_id", sa.Uuid(), nullable=False),
            sa.Column("run_trigger", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("found_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["search_id"],
                ["discovery_searches.id"],
                ondelete="CASCADE",
            ),
            sa.CheckConstraint(
                "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
                name="ck_discovery_runs_status",
            ),
            sa.CheckConstraint(
                "run_trigger IN ('daily', 'manual')",
                name="ck_discovery_runs_run_trigger",
            ),
        )
        op.create_index(
            "ix_discovery_runs_search_id_started_at",
            "discovery_runs",
            ["search_id", "started_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "discovery_runs" in tables:
        op.drop_index("ix_discovery_runs_search_id_started_at", table_name="discovery_runs")
        op.drop_table("discovery_runs")
    if "discovery_searches" in tables:
        op.drop_table("discovery_searches")
    if "leads" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("leads")}
        if "uq_leads_source_key" in indexes:
            op.drop_index("uq_leads_source_key", table_name="leads")
        columns = {column["name"] for column in inspector.get_columns("leads")}
        if "source_key" in columns:
            op.drop_column("leads", "source_key")
