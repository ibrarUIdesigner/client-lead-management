"""Add Yelp, Yell, BusinessList, and ePages to discovery searches.

Revision ID: d5e9f3b82c01
Revises: c4d8e2a71b90
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e9f3b82c01"
down_revision: str | Sequence[str] | None = "c4d8e2a71b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "use_yelp",
    "use_yell",
    "use_businesslist",
    "use_epages",
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
