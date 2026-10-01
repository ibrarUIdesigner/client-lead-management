"""Add Apify connector, run, dataset, and import tables.

Revision ID: f7b1c0a94e21
Revises: e6f0a4c93d12
Create Date: 2026-10-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

import app.models  # noqa: F401
from alembic import op
from app.db.base import Base

revision: str = "f7b1c0a94e21"
down_revision: str | Sequence[str] | None = "e6f0a4c93d12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "apify_connectors",
    "apify_runs",
    "apify_dataset_items",
    "apify_imports",
)


def upgrade() -> None:
    # A fresh database already creates these tables from the current models.
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    missing = [Base.metadata.tables[name] for name in _TABLES if name not in existing]
    if missing:
        Base.metadata.create_all(bind, tables=missing)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(_TABLES):
        if name in existing:
            op.drop_table(name)
