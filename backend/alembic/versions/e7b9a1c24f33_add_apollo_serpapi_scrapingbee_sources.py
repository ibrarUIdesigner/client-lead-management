"""Add Apollo, SerpApi, and ScrapingBee sources to discovery searches.

Revision ID: e7b9a1c24f33
Revises: c9a3f1e82b47
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7b9a1c24f33"
down_revision: str | Sequence[str] | None = "c9a3f1e82b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "use_apollo",
    "use_serpapi",
    "use_scrapingbee",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "discovery_searches" not in set(inspector.get_table_names()):
        return
    existing = {column["name"] for column in inspector.get_columns("discovery_searches")}
    for name in _COLUMNS:
        if name in existing:
            continue
        op.add_column(
            "discovery_searches",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "discovery_searches" not in set(inspector.get_table_names()):
        return
    existing = {column["name"] for column in inspector.get_columns("discovery_searches")}
    for name in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("discovery_searches", name)
