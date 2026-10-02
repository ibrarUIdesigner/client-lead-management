"""Add mockup HTML generation fields.

Revision ID: c9a3f1e82b47
Revises: b2f6a4d37e51
Create Date: 2026-10-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c9a3f1e82b47"
down_revision: str | Sequence[str] | None = "b2f6a4d37e51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("mockups")}
    if "html_content" not in columns:
        op.add_column("mockups", sa.Column("html_content", sa.Text(), nullable=True))
    if "model_name" not in columns:
        op.add_column("mockups", sa.Column("model_name", sa.String(length=64), nullable=True))
    if "goal" not in columns:
        op.add_column("mockups", sa.Column("goal", sa.String(length=32), nullable=True))
    if "asset_refs" not in columns:
        op.add_column(
            "mockups",
            sa.Column("asset_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "source_mockup_id" not in columns:
        op.add_column("mockups", sa.Column("source_mockup_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            "fk_mockups_source_mockup_id",
            "mockups",
            "mockups",
            ["source_mockup_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "screenshot_status" not in columns:
        op.add_column(
            "mockups",
            sa.Column("screenshot_status", sa.String(length=32), nullable=True),
        )
    if "error_code" not in columns:
        op.add_column("mockups", sa.Column("error_code", sa.String(length=64), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("mockups")}
    if "error_code" in columns:
        op.drop_column("mockups", "error_code")
    if "screenshot_status" in columns:
        op.drop_column("mockups", "screenshot_status")
    if "source_mockup_id" in columns:
        op.drop_constraint("fk_mockups_source_mockup_id", "mockups", type_="foreignkey")
        op.drop_column("mockups", "source_mockup_id")
    if "asset_refs" in columns:
        op.drop_column("mockups", "asset_refs")
    if "goal" in columns:
        op.drop_column("mockups", "goal")
    if "model_name" in columns:
        op.drop_column("mockups", "model_name")
    if "html_content" in columns:
        op.drop_column("mockups", "html_content")
