from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MockupRead(BaseModel):
    id: UUID
    lead_id: UUID
    business_name: str
    city: str | None
    title: str | None
    status: str
    version: int
    notes: str | None
    prompt: str | None
    primary_color: str | None
    completed_at: datetime | None
    created_at: datetime


class OutreachMessageRead(BaseModel):
    id: UUID
    lead_id: UUID
    business_name: str
    channel: str | None
    recipient_email: str | None
    subject: str | None
    message: str | None
    status: str
    sent_at: datetime | None
    opened_at: datetime | None
    replied_at: datetime | None
    created_at: datetime


class OutreachTemplateRead(BaseModel):
    id: UUID
    name: str
    channel: str | None
    subject: str | None
    body: str | None
    template_type: str | None
    is_active: bool


class FollowupRead(BaseModel):
    id: UUID
    lead_id: UUID
    business_name: str
    city: str | None
    scheduled_for: datetime
    type: str | None
    status: str
    notes: str | None
    completed_at: datetime | None


class StatusCount(BaseModel):
    status: str
    count: int


class LabelCount(BaseModel):
    label: str
    count: int


class AnalyticsRead(BaseModel):
    leads: int
    audits_completed: int
    mockups_ready: int
    contacted: int
    replies: int
    meetings: int
    proposals: int
    wins: int
    losses: int
    by_status: list[StatusCount]
    by_industry: list[LabelCount]
    by_city: list[LabelCount]
    by_source: list[LabelCount]
    high_scores: int
    websites_missing: int
