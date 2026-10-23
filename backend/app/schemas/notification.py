from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: UUID
    user_id: str
    type: str
    title: str
    message: str
    priority: str
    lead_id: UUID | None = None
    campaign_id: str | None = None
    email_id: UUID | None = None
    action_url: str | None = None
    metadata: dict[str, Any] | None = None
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class PushPublicKeyResponse(BaseModel):
    public_key: str
    configured: bool


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1)
    keys: dict[str, str] = Field(..., description="Object with p256dh and auth")
    device_name: str | None = None
    user_id: str = "default"


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1)
    user_id: str = "default"


class NotificationPreferencesResponse(BaseModel):
    user_id: str
    browser_push_enabled: bool
    preferences: dict[str, bool]


class NotificationPreferencesUpdateRequest(BaseModel):
    browser_push_enabled: bool | None = None
    preferences: dict[str, bool] | None = None
