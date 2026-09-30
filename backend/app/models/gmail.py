import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.constraints import email_constraint, status_constraint
from app.models.enums import EmailClassification, EmailDirection, GmailAccountStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.outreach import OutreachMessage


class GmailAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gmail_accounts"
    __table_args__ = (
        status_constraint("gmail_accounts", "status", GmailAccountStatus),
        email_constraint("gmail_accounts", "email"),
        Index("ix_gmail_accounts_status", "status"),
        Index("uq_gmail_accounts_email_active", "email", unique=True),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=GmailAccountStatus.ACTIVE.value,
        server_default=text("'ACTIVE'"),
    )
    encrypted_access_token: Mapped[str | None] = mapped_column(Text)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(Text)
    history_id: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    sync_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    messages: Mapped[list["LeadEmail"]] = relationship(back_populates="gmail_account")


class GmailOAuthState(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "gmail_oauth_states"
    __table_args__ = (Index("ix_gmail_oauth_states_expires_at", "expires_at"),)

    state: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeadEmail(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_emails"
    __table_args__ = (
        status_constraint("lead_emails", "direction", EmailDirection),
        status_constraint("lead_emails", "classification", EmailClassification),
        email_constraint("lead_emails", "recipient_email"),
        email_constraint("lead_emails", "sender_email"),
        UniqueConstraint(
            "gmail_account_id",
            "gmail_message_id",
            name="uq_lead_emails_account_gmail_message",
        ),
        UniqueConstraint("idempotency_key", name="uq_lead_emails_idempotency_key"),
        Index("ix_lead_emails_lead_id", "lead_id"),
        Index("ix_lead_emails_gmail_thread_id", "gmail_thread_id"),
        Index("ix_lead_emails_rfc_message_id", "rfc_message_id"),
        Index("ix_lead_emails_occurred_at", "occurred_at"),
        Index("ix_lead_emails_needs_review", "needs_review"),
    )

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
    )
    gmail_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("gmail_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    outreach_message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("outreach_messages.id", ondelete="SET NULL"),
    )
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EmailClassification.OTHER.value,
        server_default=text("'OTHER'"),
    )
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    sender_email: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    gmail_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rfc_message_id: Mapped[str | None] = mapped_column(String(512))
    in_reply_to: Mapped[str | None] = mapped_column(Text)
    references_header: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_unread: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))

    lead: Mapped["Lead | None"] = relationship(back_populates="emails")
    gmail_account: Mapped[GmailAccount] = relationship(back_populates="messages")
    outreach_message: Mapped["OutreachMessage | None"] = relationship()
