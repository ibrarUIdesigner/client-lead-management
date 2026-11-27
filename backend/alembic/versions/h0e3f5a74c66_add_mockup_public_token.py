"""Add a public token to mockups so prospects can open a login-free link.

Revision ID: h0e3f5a74c66
Revises: g9d2e4f63b55
Create Date: 2026-11-27

"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.migration_helpers import (
    add_column_if_missing,
    create_index_if_missing,
    create_table_if_missing,
)

revision: str = "h0e3f5a74c66"
down_revision: str | Sequence[str] | None = "g9d2e4f63b55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    add_column_if_missing("mockups", sa.Column("public_token", sa.String(length=64), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM mockups WHERE public_token IS NULL")).fetchall()
    for (mockup_id,) in rows:
        bind.execute(
            sa.text("UPDATE mockups SET public_token = :token WHERE id = :id"),
            {"token": secrets.token_urlsafe(24), "id": mockup_id},
        )
    create_index_if_missing("uq_mockups_public_token", "mockups", ["public_token"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_mockups_public_token", table_name="mockups")
    op.drop_column("mockups", "public_token")
