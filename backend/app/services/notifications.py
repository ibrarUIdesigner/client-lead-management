from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.enums import NotificationPriority, NotificationType
from app.models.notification import Notification, NotificationPreference
from app.services.persistence import flush_or_reject
from app.services.push import PushService

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES: dict[str, bool] = {
    "email_replies": True,
    "interested_replies": True,
    "meeting_requests": True,
    "objections": True,
    "followups_due": True,
    "mockups_ready": True,
    "research_complete": False,
    "audit_complete": False,
    "apify_complete": False,
    "email_draft_ready": True,
    "email_send_failed": True,
    "lead_qualified": True,
    "high_opportunity_lead": True,
}

NOTIFICATION_TYPE_TO_PREF_KEY: dict[str, str] = {
    NotificationType.NEW_EMAIL_REPLY.value: "email_replies",
    NotificationType.POSITIVE_REPLY.value: "interested_replies",
    NotificationType.OBJECTION_REPLY.value: "objections",
    NotificationType.MEETING_REQUEST.value: "meeting_requests",
    NotificationType.FOLLOWUP_DUE.value: "followups_due",
    NotificationType.MOCKUP_READY.value: "mockups_ready",
    NotificationType.RESEARCH_COMPLETE.value: "research_complete",
    NotificationType.AUDIT_COMPLETE.value: "audit_complete",
    NotificationType.APIFY_JOB_COMPLETE.value: "apify_complete",
    NotificationType.EMAIL_DRAFT_READY.value: "email_draft_ready",
    NotificationType.EMAIL_SEND_FAILED.value: "email_send_failed",
    NotificationType.LEAD_QUALIFIED.value: "lead_qualified",
    NotificationType.HIGH_OPPORTUNITY_LEAD.value: "high_opportunity_lead",
}


class NotificationService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        push_service: PushService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.push_service = push_service or PushService(session, self.settings)

    def create_notification(
        self,
        *,
        user_id: str = "default",
        type: str | NotificationType,
        title: str,
        message: str,
        priority: str | NotificationPriority = NotificationPriority.NORMAL.value,
        lead_id: UUID | None = None,
        campaign_id: str | None = None,
        email_id: UUID | None = None,
        action_url: str | None = None,
        dedup_key: str | None = None,
        details: dict[str, Any] | None = None,
        send_push: bool = True,
    ) -> Notification | None:
        type_str = type.value if isinstance(type, NotificationType) else str(type)
        priority_str = priority.value if isinstance(priority, NotificationPriority) else str(priority)

        # 1. Idempotency / Duplicate Prevention
        if dedup_key:
            existing = self.session.scalar(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.dedup_key == dedup_key,
                )
            )
            if existing is not None:
                logger.info(
                    "duplicate_notification_skipped dedup_key=%s id=%s type=%s",
                    dedup_key,
                    existing.id,
                    type_str,
                )
                return existing

        # 2. Preferences Check
        user_prefs = self.get_preferences(user_id)
        pref_key = NOTIFICATION_TYPE_TO_PREF_KEY.get(type_str)
        is_type_enabled = True
        if pref_key:
            is_type_enabled = user_prefs.get("preferences", {}).get(pref_key, True)

        # If user disabled this category entirely, skip creating notification
        if not is_type_enabled:
            logger.info(
                "notification_suppressed_by_preference user_id=%s type=%s pref_key=%s",
                user_id,
                type_str,
                pref_key,
            )
            return None

        # 3. Destination URL fallback
        resolved_action_url = action_url
        if not resolved_action_url and lead_id:
            resolved_action_url = f"/leads/{lead_id}?tab=outreach"

        # 4. Persist Notification in DB
        notification = Notification(
            user_id=user_id,
            type=type_str,
            title=title,
            message=message,
            priority=priority_str,
            lead_id=lead_id,
            campaign_id=campaign_id,
            email_id=email_id,
            action_url=resolved_action_url,
            dedup_key=dedup_key,
            details=details,
            is_read=False,
        )
        self.session.add(notification)
        flush_or_reject(self.session)

        logger.info(
            "notification_created id=%s user_id=%s type=%s priority=%s lead_id=%s",
            notification.id,
            user_id,
            type_str,
            priority_str,
            lead_id,
        )

        # 5. Browser Push Delivery
        browser_push_allowed = user_prefs.get("browser_push_enabled", True)
        if send_push and browser_push_allowed:
            try:
                created_iso = (
                    notification.created_at.isoformat()
                    if notification.created_at
                    else datetime.now(UTC).isoformat()
                )
                push_payload = {
                    "id": str(notification.id) if notification.id else None,
                    "type": notification.type,
                    "title": notification.title,
                    "body": notification.message,
                    "priority": notification.priority,
                    "leadId": str(lead_id) if lead_id else None,
                    "url": resolved_action_url or "/notifications",
                    "createdAt": created_iso,
                }
                self.push_service.send_to_user(user_id, push_payload)
            except Exception as exc:
                # Critical: Push failure must NEVER break notification or parent business logic
                logger.warning("push_delivery_failed notification_id=%s error=%s", notification.id, exc)

        return notification

    def get_notifications(
        self,
        *,
        user_id: str = "default",
        is_read: bool | None = None,
        type_: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        count_stmt = select(func.count(Notification.id)).where(Notification.user_id == user_id)

        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
            count_stmt = count_stmt.where(Notification.is_read == is_read)

        if type_ is not None:
            stmt = stmt.where(Notification.type == type_)
            count_stmt = count_stmt.where(Notification.type == type_)

        total = self.session.scalar(count_stmt) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
            )
        )
        return items, total

    def get_unread_count(self, *, user_id: str = "default") -> int:
        stmt = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        return self.session.scalar(stmt) or 0

    def mark_as_read(
        self,
        notification_id: UUID,
        *,
        user_id: str = "default",
    ) -> Notification | None:
        notification = self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        if notification is None:
            return None

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            flush_or_reject(self.session)
            logger.info("notification_marked_read id=%s", notification_id)

        return notification

    def mark_all_as_read(self, *, user_id: str = "default") -> int:
        now = datetime.now(UTC)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=now)
        )
        result = self.session.execute(stmt)
        flush_or_reject(self.session)
        updated = result.rowcount or 0
        logger.info("all_notifications_marked_read user_id=%s count=%s", user_id, updated)
        return updated

    def delete_notification(
        self,
        notification_id: UUID,
        *,
        user_id: str = "default",
    ) -> bool:
        stmt = delete(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = self.session.execute(stmt)
        flush_or_reject(self.session)
        deleted = (result.rowcount or 0) > 0
        if deleted:
            logger.info("notification_deleted id=%s", notification_id)
        return deleted

    def get_preferences(self, user_id: str = "default") -> dict[str, Any]:
        pref_row = self.session.scalar(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        if pref_row is None:
            return {
                "user_id": user_id,
                "browser_push_enabled": True,
                "preferences": dict(DEFAULT_PREFERENCES),
            }

        # Merge with defaults in case new keys were added
        merged_prefs = dict(DEFAULT_PREFERENCES)
        if isinstance(pref_row.preferences, dict):
            merged_prefs.update(pref_row.preferences)

        return {
            "user_id": pref_row.user_id,
            "browser_push_enabled": pref_row.browser_push_enabled,
            "preferences": merged_prefs,
        }

    def update_preferences(
        self,
        *,
        user_id: str = "default",
        browser_push_enabled: bool | None = None,
        preferences: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        pref_row = self.session.scalar(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        if pref_row is None:
            current_prefs = dict(DEFAULT_PREFERENCES)
            if preferences:
                current_prefs.update(preferences)
            pref_row = NotificationPreference(
                user_id=user_id,
                browser_push_enabled=browser_push_enabled if browser_push_enabled is not None else True,
                preferences=current_prefs,
            )
            self.session.add(pref_row)
        else:
            if browser_push_enabled is not None:
                pref_row.browser_push_enabled = browser_push_enabled
            if preferences is not None:
                updated = dict(pref_row.preferences or DEFAULT_PREFERENCES)
                updated.update(preferences)
                pref_row.preferences = updated

        flush_or_reject(self.session)
        logger.info("notification_preferences_updated user_id=%s", user_id)
        return self.get_preferences(user_id)

    def create_reply_notification(
        self,
        lead: Any,
        parsed: Any,
        analysis: Any | None = None,
        email_id: UUID | None = None,
        user_id: str = "default",
    ) -> Notification | None:
        intent = getattr(analysis, "intent", None) or "Other"
        summary = (
            getattr(analysis, "summary", None)
            or getattr(parsed, "snippet", None)
            or getattr(parsed, "subject", None)
            or "Inbound reply received."
        )

        biz_name = getattr(lead, "business_name", "Lead")

        if intent in ("Interested", "Positive"):
            notif_type = NotificationType.POSITIVE_REPLY.value
            title = f"🔥 Interested reply — {biz_name}"
            priority = NotificationPriority.HIGH.value
        elif intent == "Meeting Request":
            notif_type = NotificationType.MEETING_REQUEST.value
            title = f"📅 Meeting request — {biz_name}"
            priority = NotificationPriority.URGENT.value
        elif intent == "Objection":
            notif_type = NotificationType.OBJECTION_REPLY.value
            title = f"⚠️ Objection from {biz_name}"
            priority = NotificationPriority.NORMAL.value
        elif intent == "Pricing":
            notif_type = NotificationType.OBJECTION_REPLY.value
            title = f"💰 Pricing question — {biz_name}"
            priority = NotificationPriority.HIGH.value
        elif intent == "Unsubscribe":
            notif_type = NotificationType.NEW_EMAIL_REPLY.value
            title = f"🛑 Unsubscribe request — {biz_name}"
            priority = NotificationPriority.HIGH.value
        elif intent == "Out of Office":
            notif_type = NotificationType.NEW_EMAIL_REPLY.value
            title = f"💤 Out of Office — {biz_name}"
            priority = NotificationPriority.LOW.value
        else:
            notif_type = NotificationType.NEW_EMAIL_REPLY.value
            title = f"💬 New reply from {biz_name}"
            priority = NotificationPriority.NORMAL.value

        mid = getattr(parsed, "gmail_message_id", None)
        dedup_key = f"gmail:{mid}" if mid else None
        lead_id = getattr(lead, "id", None)

        return self.create_notification(
            user_id=user_id,
            type=notif_type,
            title=title,
            message=summary,
            priority=priority,
            lead_id=lead_id,
            email_id=email_id,
            action_url=f"/leads/{lead_id}?tab=outreach" if lead_id else "/notifications",
            dedup_key=dedup_key,
            details={
                "intent": intent,
                "sentiment": getattr(analysis, "sentiment", "neutral"),
                "confidence": getattr(analysis, "confidence", None),
                "gmail_message_id": mid,
                "gmail_thread_id": getattr(parsed, "gmail_thread_id", None),
                "sender_email": getattr(parsed, "sender_email", None),
                "subject": getattr(parsed, "subject", None),
            },
            send_push=True,
        )


def notify_user(
    session: Session,
    *,
    user_id: str = "default",
    type: str | NotificationType,
    title: str,
    message: str,
    priority: str | NotificationPriority = NotificationPriority.NORMAL.value,
    lead_id: UUID | None = None,
    campaign_id: str | None = None,
    email_id: UUID | None = None,
    action_url: str | None = None,
    dedup_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    send_push: bool = True,
    settings: Settings | None = None,
) -> Notification | None:
    service = NotificationService(session, settings=settings)
    return service.create_notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        priority=priority,
        lead_id=lead_id,
        campaign_id=campaign_id,
        email_id=email_id,
        action_url=action_url,
        dedup_key=dedup_key,
        details=metadata,
        send_push=send_push,
    )
