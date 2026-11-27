import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import status_constraint
from app.models.enums import AttemptKind, AttemptOutcome, AutomationRunStatus, ExclusionKind
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AutomationRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One execution of an automation task. The unique run_key stops duplicate runs."""

    __tablename__ = "automation_runs"
    __table_args__ = (
        status_constraint("automation_runs", "status", AutomationRunStatus),
        Index("uq_automation_runs_run_key", "run_key", unique=True),
        Index("ix_automation_runs_kind_created", "kind", "created_at"),
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    run_key: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AutomationRunStatus.RUNNING.value,
        server_default=text("'RUNNING'"),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


class OutreachAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One email we sent, with the facts needed to learn what works."""

    __tablename__ = "outreach_attempts"
    __table_args__ = (
        status_constraint("outreach_attempts", "kind", AttemptKind),
        status_constraint("outreach_attempts", "outcome", AttemptOutcome),
        Index("ix_outreach_attempts_lead_id", "lead_id"),
        Index("ix_outreach_attempts_sent_at", "sent_at"),
        Index("ix_outreach_attempts_category_country", "category", "country"),
        Index("uq_outreach_attempts_email_id", "email_id", unique=True),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    email_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lead_emails.id", ondelete="SET NULL")
    )
    outreach_message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("outreach_messages.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    strategy: Mapped[str | None] = mapped_column(String(32))
    framework: Mapped[str | None] = mapped_column(String(64))
    template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    mockup_included: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    automatic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    category: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AttemptOutcome.NONE.value,
        server_default=text("'none'"),
    )
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeadExclusion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Things you never want contacted or discovered again."""

    __tablename__ = "lead_exclusions"
    __table_args__ = (
        status_constraint("lead_exclusions", "kind", ExclusionKind),
        Index("uq_lead_exclusions_kind_value", "kind", "value", unique=True),
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
