from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

OutreachTone = Literal["professional", "warm", "direct", "brief"]


class OutreachGenerate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: UUID | None = None
    offer: str | None = Field(default=None, max_length=800)
    tone: OutreachTone = "professional"
    sender_name: str | None = Field(default=None, max_length=120)
    use_ai: bool = True


class OutreachCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    lead_id: UUID
    template_id: UUID | None = None
    channel: str | None = Field(default="email", max_length=32)
    subject: str | None = Field(default=None, max_length=500)
    message: str | None = Field(default=None, max_length=20000)


class OutreachUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str | None = Field(default=None, max_length=500)
    message: str | None = Field(default=None, max_length=20000)


class FollowupCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    lead_id: UUID
    outreach_id: UUID | None = None
    scheduled_for: datetime
    type: str | None = Field(default="email", max_length=64)
    notes: str | None = Field(default=None, max_length=5000)


class FollowupUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    scheduled_for: datetime | None = None
    type: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=5000)
