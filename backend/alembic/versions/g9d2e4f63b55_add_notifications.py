"""Add notifications, push subscriptions, and notification preferences.

Revision ID: g9d2e4f63b55
Revises: f8c1d3e52a44
Create Date: 2026-10-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "g9d2e4f63b55"
down_revision: str | Sequence[str] | None = "f8c1d3e52a44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "notifications" not in existing_tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.String(length=255), server_default=sa.text("'default'"), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("priority", sa.String(length=32), server_default=sa.text("'NORMAL'"), nullable=False),
            sa.Column("lead_id", sa.Uuid(), nullable=True),
            sa.Column("campaign_id", sa.String(length=120), nullable=True),
            sa.Column("email_id", sa.Uuid(), nullable=True),
            sa.Column("action_url", sa.Text(), nullable=True),
            sa.Column("dedup_key", sa.String(length=255), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["email_id"], ["lead_emails.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"], unique=False)
        op.create_index("ix_notifications_user_id_is_read", "notifications", ["user_id", "is_read"], unique=False)
        op.create_index("ix_notifications_lead_id", "notifications", ["lead_id"], unique=False)
        op.create_index("ix_notifications_type", "notifications", ["type"], unique=False)
        op.create_index("uq_notifications_dedup_key", "notifications", ["dedup_key"], unique=True)

    if "push_subscriptions" not in existing_tables:
        op.create_table(
            "push_subscriptions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.String(length=255), server_default=sa.text("'default'"), nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False),
            sa.Column("p256dh", sa.String(length=255), nullable=False),
            sa.Column("auth", sa.String(length=255), nullable=False),
            sa.Column("device_name", sa.String(length=120), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"], unique=False)
        op.create_index("uq_push_subscriptions_user_endpoint", "push_subscriptions", ["user_id", "endpoint"], unique=True)

    if "notification_preferences" not in existing_tables:
        op.create_table(
            "notification_preferences",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.String(length=255), server_default=sa.text("'default'"), nullable=False),
            sa.Column("browser_push_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("uq_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "notification_preferences" in existing_tables:
        op.drop_index("uq_notification_preferences_user_id", table_name="notification_preferences")
        op.drop_table("notification_preferences")

    if "push_subscriptions" in existing_tables:
        op.drop_index("uq_push_subscriptions_user_endpoint", table_name="push_subscriptions")
        op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
        op.drop_table("push_subscriptions")

    if "notifications" in existing_tables:
        op.drop_index("uq_notifications_dedup_key", table_name="notifications")
        op.drop_index("ix_notifications_type", table_name="notifications")
        op.drop_index("ix_notifications_lead_id", table_name="notifications")
        op.drop_index("ix_notifications_user_id_is_read", table_name="notifications")
        op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
        op.drop_table("notifications")
