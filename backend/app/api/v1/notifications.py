from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.api.deps import SessionDep
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    NotificationResponse,
    PushPublicKeyResponse,
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    UnreadCountResponse,
)
from app.services.notifications import NotificationService
from app.services.push import PushService

router = APIRouter(tags=["notifications"])


def _to_response(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        user_id=n.user_id,
        type=n.type,
        title=n.title,
        message=n.message,
        priority=n.priority,
        lead_id=n.lead_id,
        campaign_id=n.campaign_id,
        email_id=n.email_id,
        action_url=n.action_url,
        metadata=n.details,
        is_read=n.is_read,
        created_at=n.created_at,
        read_at=n.read_at,
    )


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    session: SessionDep,
    request: Request,
    is_read: Annotated[bool | None, Query()] = None,
    type_: Annotated[str | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user_id: Annotated[str, Query()] = "default",
) -> NotificationListResponse:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    items, total = service.get_notifications(
        user_id=user_id,
        is_read=is_read,
        type_=type_,
        limit=limit,
        offset=offset,
    )
    unread = service.get_unread_count(user_id=user_id)
    return NotificationListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        unread_count=unread,
    )


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    session: SessionDep,
    request: Request,
    user_id: Annotated[str, Query()] = "default",
) -> UnreadCountResponse:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    return UnreadCountResponse(unread_count=service.get_unread_count(user_id=user_id))


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    session: SessionDep,
    request: Request,
    user_id: Annotated[str, Query()] = "default",
) -> NotificationResponse:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    item = service.mark_as_read(notification_id, user_id=user_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _to_response(item)


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    session: SessionDep,
    request: Request,
    user_id: Annotated[str, Query()] = "default",
) -> dict[str, int]:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    updated = service.mark_all_as_read(user_id=user_id)
    return {"updated": updated}


@router.delete("/notifications/{notification_id}", status_code=204)
def delete_notification(
    notification_id: UUID,
    session: SessionDep,
    request: Request,
    user_id: Annotated[str, Query()] = "default",
) -> Response:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    deleted = service.delete_notification(notification_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")
    return Response(status_code=204)


@router.get("/notifications/preferences", response_model=NotificationPreferencesResponse)
def get_preferences(
    session: SessionDep,
    request: Request,
    user_id: Annotated[str, Query()] = "default",
) -> NotificationPreferencesResponse:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    prefs = service.get_preferences(user_id=user_id)
    return NotificationPreferencesResponse(**prefs)


@router.put("/notifications/preferences", response_model=NotificationPreferencesResponse)
def update_preferences(
    data: NotificationPreferencesUpdateRequest,
    session: SessionDep,
    request: Request,
    user_id: Annotated[str, Query()] = "default",
) -> NotificationPreferencesResponse:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    updated = service.update_preferences(
        user_id=user_id,
        browser_push_enabled=data.browser_push_enabled,
        preferences=data.preferences,
    )
    return NotificationPreferencesResponse(**updated)


# --- Web Push Endpoints ---


@router.get("/push/public-key", response_model=PushPublicKeyResponse)
def get_push_public_key(request: Request) -> PushPublicKeyResponse:
    settings = request.app.state.settings
    key = settings.vapid_public_key.strip()
    return PushPublicKeyResponse(
        public_key=key,
        configured=bool(key and settings.vapid_private_key.strip()),
    )


@router.post("/push/subscribe", status_code=201)
def subscribe_push(
    data: PushSubscribeRequest,
    session: SessionDep,
    request: Request,
) -> dict[str, str]:
    settings = request.app.state.settings
    push_service = PushService(session, settings=settings)

    p256dh = data.keys.get("p256dh", "")
    auth = data.keys.get("auth", "")
    if not p256dh or not auth:
        raise HTTPException(status_code=422, detail="Missing p256dh or auth in push keys")

    user_agent = request.headers.get("user-agent")
    push_service.save_subscription(
        user_id=data.user_id,
        endpoint=data.endpoint,
        p256dh=p256dh,
        auth=auth,
        device_name=data.device_name,
        user_agent=user_agent,
    )
    return {"status": "subscribed"}


@router.delete("/push/subscribe")
def unsubscribe_push(
    data: PushUnsubscribeRequest,
    session: SessionDep,
    request: Request,
) -> dict[str, str]:
    settings = request.app.state.settings
    push_service = PushService(session, settings=settings)
    push_service.delete_subscription(
        user_id=data.user_id,
        endpoint=data.endpoint,
    )
    return {"status": "unsubscribed"}


@router.post("/push/test")
def send_test_push(
    session: SessionDep,
    request: Request,
    user_id: Annotated[str, Query()] = "default",
) -> dict[str, Any]:
    settings = request.app.state.settings
    service = NotificationService(session, settings=settings)
    notification = service.create_notification(
        user_id=user_id,
        type="NEW_EMAIL_REPLY",
        title="🔔 Test Notification",
        message="This is a test notification from Client Acquisition Tool.",
        priority="HIGH",
        action_url="/notifications",
        send_push=True,
    )
    return {
        "status": "sent",
        "notification_id": str(notification.id) if notification else None,
    }
