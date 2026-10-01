"""Add design guides and mockup guide snapshots.

Revision ID: b2f6a4d37e51
Revises: a8d4e2c15b30
Create Date: 2026-10-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

import app.models  # noqa: F401
from alembic import op
from app.db.base import Base

revision: str = "b2f6a4d37e51"
down_revision: str | Sequence[str] | None = "a8d4e2c15b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "design_guides" not in tables:
        Base.metadata.create_all(bind, tables=[Base.metadata.tables["design_guides"]])
    columns = {column["name"] for column in sa.inspect(bind).get_columns("mockups")}
    if "design_guide_id" not in columns:
        op.add_column("mockups", sa.Column("design_guide_id", sa.Uuid(), nullable=True))
        op.add_column(
            "mockups",
            sa.Column("design_guide_name", sa.String(length=120), nullable=True),
        )
        op.add_column("mockups", sa.Column("design_guide_snapshot", sa.Text(), nullable=True))
        op.create_foreign_key(
            "fk_mockups_design_guide_id",
            "mockups",
            "design_guides",
            ["design_guide_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_mockups_design_guide_id", "mockups", ["design_guide_id"])


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("mockups")}
    if "design_guide_id" in columns:
        op.drop_index("ix_mockups_design_guide_id", table_name="mockups")
        op.drop_constraint("fk_mockups_design_guide_id", "mockups", type_="foreignkey")
        op.drop_column("mockups", "design_guide_snapshot")
        op.drop_column("mockups", "design_guide_name")
        op.drop_column("mockups", "design_guide_id")
    tables = set(sa.inspect(bind).get_table_names())
    if "design_guides" in tables:
        op.drop_table("design_guides")
