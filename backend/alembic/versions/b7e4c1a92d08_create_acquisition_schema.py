"""Create the acquisition schema.

Revision ID: b7e4c1a92d08
Revises:
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import app.models  # noqa: F401
from alembic import op
from app.db.base import Base

revision: str = "b7e4c1a92d08"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
