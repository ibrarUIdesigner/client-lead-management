from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pywebpush import WebPushException

from app.models.enums import NotificationPriority, NotificationType
from app.models.lead import Lead
from app.models.notification import Notification, NotificationPreference, PushSubscription
from app.services.notifications import NotificationService, notify_user
from app.services.push import PushService


def test_create_and_read_notification():
    session = MagicMock()
    lead_id = uuid4()
    session.scalar.return_value = None  # No duplicate found

    service = NotificationService(session)
    # Mock push service so network is not touched
    service.push_service.send_to_user = MagicMock(return_value=1)

    notif = service.create_notification(
        user_id="user1",
        type=NotificationType.NEW_EMAIL_REPLY,
        title="💬 New reply from Acme",
        message="I would like to see the mockup.",
        priority=NotificationPriority.HIGH,
        lead_id=lead_id,
        action_url=f"/leads/{lead_id}?tab=outreach",
        dedup_key="gmail:msg123",
    )

    assert notif is not None
    assert notif.user_id == "user1"
    assert notif.type == NotificationType.NEW_EMAIL_REPLY.value
    assert notif.priority == NotificationPriority.HIGH.value
    assert notif.lead_id == lead_id
    assert notif.dedup_key == "gmail:msg123"
    assert notif.is_read is False

    session.add.assert_called_once()
    service.push_service.send_to_user.assert_called_once()


def test_idempotent_duplicate_prevention():
    session = MagicMock()
    existing_notif = Notification(
        id=uuid4(),
        user_id="user1",
        type="NEW_EMAIL_REPLY",
        title="Existing",
        message="Message",
        dedup_key="gmail:msg_duplicate_999",
    )
    session.scalar.return_value = existing_notif

    service = NotificationService(session)
    service.push_service.send_to_user = MagicMock()

    notif = service.create_notification(
        user_id="user1",
        type=NotificationType.NEW_EMAIL_REPLY,
        title="Duplicate title",
        message="Duplicate msg",
        dedup_key="gmail:msg_duplicate_999",
    )

    assert notif.id == existing_notif.id
    # Ensure no new notification was added and no duplicate push was sent
    session.add.assert_not_called()
    service.push_service.send_to_user.assert_not_called()


def test_user_preferences_suppression():
    session = MagicMock()
    # Mocking get_preferences response by returning disabled preference
    session.scalar.return_value = NotificationPreference(
        user_id="user1",
        browser_push_enabled=True,
        preferences={"email_replies": False},
    )

    service = NotificationService(session)
    service.push_service.send_to_user = MagicMock()

    notif = service.create_notification(
        user_id="user1",
        type=NotificationType.NEW_EMAIL_REPLY,
        title="New reply",
        message="Should be skipped",
    )

    assert notif is None
    session.add.assert_not_called()
    service.push_service.send_to_user.assert_not_called()


def test_intelligent_reply_notification_formatting():
    session = MagicMock()
    session.scalar.return_value = None

    service = NotificationService(session)
    service.push_service.send_to_user = MagicMock(return_value=1)

    lead = Lead(id=uuid4(), business_name="Sunshine Bakery")
    parsed = MagicMock(
        gmail_message_id="mid_100",
        gmail_thread_id="th_100",
        sender_email="owner@sunshine.test",
        subject="Re: Web concept",
        snippet="Looks great!",
    )

    class MockAnalysis:
        intent = "Interested"
        summary = "Prospect is eager to view redesign concept."
        sentiment = "positive"
        confidence = 0.95

    notif = service.create_reply_notification(lead, parsed, MockAnalysis())

    assert notif is not None
    assert "Interested" in notif.title
    assert "Sunshine Bakery" in notif.title
    assert notif.priority == NotificationPriority.HIGH.value
    assert notif.type == NotificationType.POSITIVE_REPLY.value
    assert notif.dedup_key == "gmail:mid_100"


def test_meeting_request_formatting():
    session = MagicMock()
    session.scalar.return_value = None

    service = NotificationService(session)
    service.push_service.send_to_user = MagicMock(return_value=1)

    lead = Lead(id=uuid4(), business_name="City Law Firm")
    parsed = MagicMock(
        gmail_message_id="mid_200",
        gmail_thread_id="th_200",
        sender_email="lawyer@citylaw.test",
        subject="Re: Consult",
        snippet="Can we talk on Friday?",
    )

    class MockMeetingAnalysis:
        intent = "Meeting Request"
        summary = "Prospect asked to schedule a Zoom call this Friday."
        sentiment = "positive"
        confidence = 0.98

    notif = service.create_reply_notification(lead, parsed, MockMeetingAnalysis())

    assert notif is not None
    assert "Meeting request" in notif.title
    assert notif.priority == NotificationPriority.URGENT.value
    assert notif.type == NotificationType.MEETING_REQUEST.value


def test_push_service_cleans_expired_subscription():
    session = MagicMock()
    sub = PushSubscription(
        id=uuid4(),
        user_id="user1",
        endpoint="https://push.example.com/expired",
        p256dh="key",
        auth="auth",
    )

    push_svc = PushService(session)

    # Mock webpush raising WebPushException with 410 Gone response
    mock_resp = MagicMock(status_code=410)
    mock_exc = WebPushException("Subscription has expired", response=mock_resp)

    with patch("app.services.push.webpush", side_effect=mock_exc):
        with patch.object(push_svc, "_get_vapid", return_value=MagicMock()):
            success = push_svc.send_to_subscription(sub, {"title": "Test"})
            assert success is False
            # Verify expired subscription is deleted
            session.delete.assert_called_once_with(sub)


def test_push_failure_does_not_break_notification_creation():
    session = MagicMock()
    session.scalar.return_value = None

    service = NotificationService(session)
    # Push service raises exception
    service.push_service.send_to_user = MagicMock(side_effect=RuntimeError("Push network timeout"))

    notif = service.create_notification(
        user_id="user1",
        type=NotificationType.NEW_EMAIL_REPLY,
        title="New reply",
        message="Important content",
        send_push=True,
    )

    # Notification must still be created and persisted in DB
    assert notif is not None
    assert notif.title == "New reply"
    session.add.assert_called_once()
