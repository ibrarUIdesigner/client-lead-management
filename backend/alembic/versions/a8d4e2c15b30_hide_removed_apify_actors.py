"""Remember Apify actors removed from this app.

Revision ID: a8d4e2c15b30
Revises: f7b1c0a94e21
Create Date: 2026-10-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

import app.models  # noqa: F401
from alembic import op
from app.db.base import Base

revision: str = "a8d4e2c15b30"
down_revision: str | Sequence[str] | None = "f7b1c0a94e21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "apify_dismissed_actors"


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if _TABLE not in existing:
        Base.metadata.create_all(bind, tables=[Base.metadata.tables[_TABLE]])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if _TABLE in existing:
        op.drop_table(_TABLE)
