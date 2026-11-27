"""Add market cells (rotation memory) and discovery rejections.

Revision ID: l4c7d9e18a00
Revises: k3b6c8d07f99
Create Date: 2026-11-28

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.migration_helpers import (
    add_column_if_missing,
    create_index_if_missing,
    create_table_if_missing,
)

revision: str = "l4c7d9e18a00"
down_revision: str | Sequence[str] | None = "k3b6c8d07f99"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _count(name: str) -> sa.Column:
    return sa.Column(name, sa.Integer(), server_default=sa.text("0"), nullable=False)


def upgrade() -> None:
    create_table_if_missing(
        "market_cells",
        _id(),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        _count("searches"),
        _count("found"),
        _count("created"),
        _count("rejected"),
        _count("empty_streak"),
        sa.Column("last_searched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index_if_missing("uq_market_cells_key", "market_cells", ["category", "country", "city"], unique=True)
    create_index_if_missing("ix_market_cells_next_eligible", "market_cells", ["next_eligible_at"])

    create_table_if_missing(
        "discovery_rejections",
        _id(),
        sa.Column("source_key", sa.String(length=300), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
    )
    create_index_if_missing(
        "uq_discovery_rejections_source_key", "discovery_rejections", ["source_key"], unique=True
    )
    create_index_if_missing("ix_discovery_rejections_created_at", "discovery_rejections", ["created_at"])


def downgrade() -> None:
    op.drop_table("discovery_rejections")
    op.drop_table("market_cells")
