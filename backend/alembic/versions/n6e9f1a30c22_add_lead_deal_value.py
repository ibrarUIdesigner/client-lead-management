"""Add the value of a won deal so revenue can be reported.

Revision ID: n6e9f1a30c22
Revises: m5d8e0f29b11
Create Date: 2026-11-28

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "n6e9f1a30c22"
down_revision: str | Sequence[str] | None = "m5d8e0f29b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("deal_value", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "deal_value")
