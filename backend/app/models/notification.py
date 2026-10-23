from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import NotificationPriority
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.gmail import LeadEmail
    from app.models.lead import Lead


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        Index("ix_notifications_user_id_is_read", "user_id", "is_read"),
        Index("ix_notifications_lead_id", "lead_id"),
        Index("ix_notifications_type", "type"),
        Index("uq_notifications_dedup_key", "dedup_key", unique=True),
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="default",
        server_default=text("'default'"),
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=NotificationPriority.NORMAL.value,
        server_default=text("'NORMAL'"),
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
    )
    campaign_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lead_emails.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict[str, object] | None] = mapped_column(
        "metadata",
        JSONB,
        key="details",
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lead: Mapped[Lead | None] = relationship(lazy="joined")
    email: Mapped[LeadEmail | None] = relationship(lazy="joined")


class PushSubscription(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        Index("ix_push_subscriptions_user_id", "user_id"),
        Index("uq_push_subscriptions_user_endpoint", "user_id", "endpoint", unique=True),
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="default",
        server_default=text("'default'"),
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("uq_notification_preferences_user_id", "user_id", unique=True),
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        default="default",
        server_default=text("'default'"),
    )
    browser_push_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    preferences: Mapped[dict[str, bool]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
