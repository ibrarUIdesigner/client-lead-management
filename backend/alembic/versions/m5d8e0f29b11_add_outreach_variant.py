"""Record which writing variant each outreach message used.

Revision ID: m5d8e0f29b11
Revises: l4c7d9e18a00
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

revision: str = "m5d8e0f29b11"
down_revision: str | Sequence[str] | None = "l4c7d9e18a00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    add_column_if_missing("outreach_messages", sa.Column("variant", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("outreach_messages", "variant")
