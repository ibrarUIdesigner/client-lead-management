from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from py_vapid import Vapid
from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.notification import PushSubscription
from app.services.persistence import flush_or_reject

logger = logging.getLogger(__name__)


class PushService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def get_public_key(self) -> str:
        return self.settings.vapid_public_key

    def save_subscription(
        self,
        *,
        user_id: str = "default",
        endpoint: str,
        p256dh: str,
        auth: str,
        device_name: str | None = None,
        user_agent: str | None = None,
    ) -> PushSubscription:
        existing = self.session.scalar(
            select(PushSubscription).where(
                PushSubscription.user_id == user_id,
                PushSubscription.endpoint == endpoint,
            )
        )
        if existing is not None:
            existing.p256dh = p256dh
            existing.auth = auth
            existing.device_name = device_name or existing.device_name
            existing.user_agent = user_agent or existing.user_agent
            existing.last_used_at = datetime.now(UTC)
            flush_or_reject(self.session)
            logger.info("push_subscription_updated user_id=%s id=%s", user_id, existing.id)
            return existing

        subscription = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            device_name=device_name,
            user_agent=user_agent,
            last_used_at=datetime.now(UTC),
        )
        self.session.add(subscription)
        flush_or_reject(self.session)
        logger.info("push_subscription_created user_id=%s id=%s", user_id, subscription.id)
        return subscription

    def delete_subscription(self, *, user_id: str = "default", endpoint: str) -> bool:
        stmt = delete(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
        result = self.session.execute(stmt)
        flush_or_reject(self.session)
        deleted = (result.rowcount or 0) > 0
        if deleted:
            logger.info("push_subscription_deleted user_id=%s endpoint=%s", user_id, endpoint[:40])
        return deleted

    def send_to_user(self, user_id: str, payload: dict[str, Any]) -> int:
        if not self.settings.vapid_configured:
            logger.warning("push_notification_skipped_vapid_not_configured user_id=%s", user_id)
            return 0

        subscriptions = list(
            self.session.scalars(
                select(PushSubscription).where(PushSubscription.user_id == user_id)
            )
        )
        if not subscriptions:
            logger.debug("push_no_subscriptions user_id=%s", user_id)
            return 0

        success_count = 0
        for sub in subscriptions:
            if self.send_to_subscription(sub, payload):
                success_count += 1

        return success_count

    def send_to_subscription(self, sub: PushSubscription, payload: dict[str, Any]) -> bool:
        try:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth,
                },
            }
            data_str = json.dumps(payload)

            vapid_instance = self._get_vapid()
            if vapid_instance is None:
                logger.warning("vapid_initialization_failed")
                return False

            claims = {
                "sub": self.settings.vapid_claims_email,
            }

            webpush(
                subscription_info=subscription_info,
                data=data_str,
                vapid_private_key=vapid_instance,
                vapid_claims=claims,
                ttl=86400,
            )

            sub.last_used_at = datetime.now(UTC)
            flush_or_reject(self.session)
            logger.info(
                "push_notification_sent sub_id=%s user_id=%s type=%s",
                sub.id,
                sub.user_id,
                payload.get("type"),
            )
            return True

        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
            logger.warning(
                "push_webpush_error sub_id=%s status=%s error=%s",
                sub.id,
                status,
                exc,
            )
            # Remove expired or unregistered subscriptions (HTTP 404 or 410 Gone)
            if status in (404, 410):
                logger.info("removing_expired_push_subscription sub_id=%s", sub.id)
                self.session.delete(sub)
                try:
                    flush_or_reject(self.session)
                except Exception:
                    pass
            return False

        except Exception as exc:
            logger.exception("push_notification_unexpected_error sub_id=%s: %s", sub.id, exc)
            return False

    def _get_vapid(self) -> Vapid | None:
        try:
            priv = self.settings.vapid_private_key.strip()
            if not priv:
                return None
            if "-----BEGIN" in priv:
                return Vapid.from_pem(priv.encode())
            return Vapid.from_string(priv)
        except Exception as exc:
            logger.error("vapid_parse_error: %s", exc)
            return None
