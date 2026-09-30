from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GmailStatusRead(BaseModel):
    configured: bool
    connected: bool
    email: str | None = None
    status: str | None = None
    last_synced_at: datetime | None = None
    last_error: str | None = None
    sync_enabled: bool = False
    needs_reauth: bool = False


class GmailConnectStart(BaseModel):
    authorization_url: str


class LeadEmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID | None
    gmail_account_id: UUID
    outreach_message_id: UUID | None
    direction: str
    classification: str
    recipient_email: str | None
    sender_email: str | None
    subject: str | None
    body_text: str | None
    body_html: str | None
    gmail_message_id: str
    gmail_thread_id: str
    rfc_message_id: str | None
    occurred_at: datetime
    is_unread: bool
    needs_review: bool
    created_at: datetime


class LeadEmailThreadSummary(BaseModel):
    last_contacted_at: datetime | None = None
    last_replied_at: datetime | None = None
    next_followup_at: datetime | None = None
    email_unread: bool = False
    do_not_contact: bool = False
    email_suppressed: bool = False
    unread_count: int = 0
    items: list[LeadEmailRead] = Field(default_factory=list)


class LeadEmailSendRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    to: str | None = Field(default=None, max_length=320)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1)
    outreach_message_id: UUID | None = None
    attachment_audit_id: UUID | None = None
    attachment_mockup_ids: list[UUID] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, max_length=128)


class LeadEmailReplyRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=1)
    subject: str | None = Field(default=None, max_length=998)
    idempotency_key: str | None = Field(default=None, max_length=128)


class GmailSyncResult(BaseModel):
    processed: int = 0
    matched: int = 0
    skipped: int = 0
    ambiguous: int = 0
    history_reset: bool = False
    account_email: str | None = None
