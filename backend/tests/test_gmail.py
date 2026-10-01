from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.errors import AppError
from app.integrations.gmail import (
    GmailClient,
    OAuthTokens,
    ParsedGmailMessage,
    sanitize_email_html,
)
from app.models.enums import (
    EmailClassification,
    EmailDirection,
    FollowupStatus,
    GmailAccountStatus,
    LeadStatus,
    OutreachStatus,
)
from app.models.followup import Followup
from app.models.gmail import GmailAccount, GmailOAuthState, LeadEmail
from app.models.lead import Lead
from app.models.outreach import OutreachMessage
from app.schemas.gmail import LeadEmailSendRequest
from app.services.gmail_accounts import GmailAccountService
from app.services.gmail_classify import classify_inbound_message
from app.services.gmail_mail import GmailMailService
from app.services.gmail_sync import GmailSyncService


def _settings(**overrides: object) -> Settings:
    values = {
        "app_env": "test",
        "google_oauth_client_id": "client-id",
        "google_oauth_client_secret": "client-secret",
        "token_encryption_key": "dev-secret-for-tests-not-for-prod",
        "gmail_api_max_retries": 2,
    }
    values.update(overrides)
    return Settings(**values)


def test_encrypt_roundtrip() -> None:
    settings = _settings()
    token = "ya29.access-token-value"
    encrypted = encrypt_secret(token, settings)
    assert encrypted != token
    assert decrypt_secret(encrypted, settings) == token


def test_sanitize_email_html_strips_scripts_and_handlers() -> None:
    dirty = (
        '<p onclick="alert(1)">Hello</p><script>evil()</script>'
        '<a href="javascript:alert(1)">x</a><style>body{}</style>'
    )
    cleaned = sanitize_email_html(dirty)
    assert cleaned is not None
    assert "script" not in cleaned.lower()
    assert "onclick" not in cleaned.lower()
    assert "javascript:" not in cleaned.lower()
    assert "Hello" in cleaned


@pytest.mark.parametrize(
    ("subject", "body", "sender", "expected"),
    [
        ("Out of Office", "I am away", "lead@example.com", EmailClassification.OUT_OF_OFFICE),
        (
            "Delivery Status Notification",
            "failed",
            "mailer-daemon@google.com",
            EmailClassification.BOUNCE,
        ),
        ("Re: hello", "Please unsubscribe me", "lead@example.com", EmailClassification.OPT_OUT),
        (
            "Re: hello",
            "Thanks, let's chat next week",
            "lead@example.com",
            EmailClassification.HUMAN_REPLY,
        ),
    ],
)
def test_classify_inbound_message(
    subject: str,
    body: str,
    sender: str,
    expected: EmailClassification,
) -> None:
    result = classify_inbound_message(subject=subject, body_text=body, sender_email=sender)
    assert result.classification == expected


def test_oauth_state_validation_rejects_unknown_state() -> None:
    session = MagicMock()
    session.scalar.return_value = None
    service = GmailAccountService(session, _settings(), client=MagicMock())
    url = service.complete_oauth(code="abc", state="missing", error=None)
    assert "invalid_state" in url


def test_oauth_state_validation_accepts_valid_state() -> None:
    session = MagicMock()
    state = GmailOAuthState(
        state="valid-state",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    session.scalar.side_effect = [state, None]
    client = MagicMock()
    client.exchange_code.return_value = OAuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes="scope",
    )
    client.fetch_profile_email.return_value = "me@example.com"
    client.get_profile.return_value = {"historyId": "100"}
    service = GmailAccountService(session, _settings(), client=client)
    url = service.complete_oauth(code="abc", state="valid-state", error=None)
    assert "gmail=connected" in url
    session.add.assert_called()
    session.delete.assert_called_with(state)


def test_disconnect_clears_credentials_and_stops_sync() -> None:
    session = MagicMock()
    account = GmailAccount(
        email="me@example.com",
        status=GmailAccountStatus.ACTIVE.value,
        encrypted_access_token="enc-a",
        encrypted_refresh_token="enc-r",
        history_id="123",
        sync_enabled=True,
    )
    account.id = uuid4()
    session.scalar.return_value = account
    service = GmailAccountService(session, _settings(), client=MagicMock())
    status = service.disconnect()
    assert account.status == GmailAccountStatus.DISCONNECTED.value
    assert account.encrypted_access_token is None
    assert account.encrypted_refresh_token is None
    assert account.history_id is None
    assert account.sync_enabled is False
    assert status.connected is False


def test_send_is_idempotent_for_same_key() -> None:
    session = MagicMock()
    lead = Lead(business_name="Cafe", email="lead@example.com", lead_status=LeadStatus.NEW.value)
    lead.id = uuid4()
    existing = LeadEmail(
        lead_id=lead.id,
        gmail_account_id=uuid4(),
        direction=EmailDirection.OUTBOUND.value,
        classification=EmailClassification.OUTGOING.value,
        recipient_email="lead@example.com",
        gmail_message_id="m1",
        gmail_thread_id="t1",
        occurred_at=datetime.now(UTC),
        idempotency_key="same-key",
        is_unread=False,
        needs_review=False,
    )
    existing.id = uuid4()
    existing.created_at = datetime.now(UTC)

    service = GmailMailService(session, _settings(), client=MagicMock())
    service.leads.get = MagicMock(return_value=lead)  # type: ignore[method-assign]
    session.scalar.return_value = existing

    result = service.send(
        lead.id,
        LeadEmailSendRequest(subject="Hi", body="Body", idempotency_key="same-key"),
        idempotency_key="same-key",
    )
    assert result.id == existing.id


def test_send_blocks_do_not_contact() -> None:
    session = MagicMock()
    lead = Lead(
        business_name="Cafe",
        email="lead@example.com",
        lead_status=LeadStatus.DO_NOT_CONTACT.value,
        do_not_contact=True,
    )
    lead.id = uuid4()
    service = GmailMailService(session, _settings(), client=MagicMock())
    service.leads.get = MagicMock(return_value=lead)  # type: ignore[method-assign]
    with pytest.raises(AppError) as exc:
        service.send(lead.id, LeadEmailSendRequest(subject="Hi", body="Body"))
    assert exc.value.code == "DO_NOT_CONTACT"


def test_send_marks_contacted_and_stores_ids() -> None:
    session = MagicMock()
    settings = _settings()
    lead = Lead(business_name="Cafe", email="lead@example.com", lead_status=LeadStatus.NEW.value)
    lead.id = uuid4()
    account = GmailAccount(
        email="me@example.com",
        status=GmailAccountStatus.ACTIVE.value,
        encrypted_access_token=encrypt_secret("access", settings),
        encrypted_refresh_token=encrypt_secret("refresh", settings),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        sync_enabled=True,
    )
    account.id = uuid4()

    client = MagicMock()
    client.send_message.return_value = {"id": "msg-1", "threadId": "thr-1"}
    client.get_message.return_value = ParsedGmailMessage(
        gmail_message_id="msg-1",
        gmail_thread_id="thr-1",
        rfc_message_id="<rfc-1@mail.gmail.com>",
        in_reply_to=None,
        references=None,
        subject="Hi",
        sender_email="me@example.com",
        recipient_email="lead@example.com",
        body_text="Body",
        body_html=None,
        label_ids=("SENT",),
        internal_date=datetime.now(UTC),
        snippet=None,
    )

    service = GmailMailService(session, settings, client=client)
    service.leads.get = MagicMock(return_value=lead)  # type: ignore[method-assign]
    service.accounts.get_active_account = MagicMock(return_value=account)  # type: ignore[method-assign]
    service.accounts.require_active_account = MagicMock(return_value=account)  # type: ignore[method-assign]
    session.scalar.return_value = None

    added: list[object] = []

    def add(obj: object) -> None:
        if isinstance(obj, LeadEmail):
            obj.id = uuid4()
            obj.created_at = datetime.now(UTC)
            obj.is_unread = False
            obj.needs_review = False
        added.append(obj)

    session.add.side_effect = add

    result = service.send(
        lead.id,
        LeadEmailSendRequest(subject="Hi", body="Body", idempotency_key="send-1"),
    )
    assert lead.lead_status == LeadStatus.CONTACTED.value
    assert lead.last_contacted_at is not None
    assert any(isinstance(item, LeadEmail) for item in added)
    stored = next(item for item in added if isinstance(item, LeadEmail))
    assert stored.gmail_message_id == "msg-1"
    assert stored.gmail_thread_id == "thr-1"
    assert stored.rfc_message_id == "<rfc-1@mail.gmail.com>"
    assert result.gmail_message_id == "msg-1"


def test_human_reply_updates_lead_and_cancels_followups() -> None:
    session = MagicMock()
    settings = _settings()
    service = GmailSyncService(session, settings, client=MagicMock())
    lead = Lead(
        business_name="Cafe",
        email="lead@example.com",
        lead_status=LeadStatus.CONTACTED.value,
    )
    lead.id = uuid4()
    followup = Followup(
        lead_id=lead.id,
        scheduled_for=datetime.now(UTC) + timedelta(days=2),
        status=FollowupStatus.SCHEDULED.value,
    )
    session.get.return_value = lead

    class _Result:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def first(self):
            return self._rows[0] if self._rows else None

    def scalars_for(statement=None, *args, **kwargs):  # noqa: ANN001
        sql = str(statement)
        if "followups" in sql.lower() or "Followup" in sql:
            return _Result([followup])
        return _Result([])

    session.scalars.side_effect = scalars_for

    service._apply_lead_effects(
        lead.id,
        EmailClassification.HUMAN_REPLY,
        ParsedGmailMessage(
            gmail_message_id="in-1",
            gmail_thread_id="thr-9",
            rfc_message_id="<in@mail.gmail.com>",
            in_reply_to="<out@mail.gmail.com>",
            references="<out@mail.gmail.com>",
            subject="Re: Hi",
            sender_email="lead@example.com",
            recipient_email="me@example.com",
            body_text="Thanks, interested to talk.",
            body_html=None,
            label_ids=("INBOX",),
            internal_date=datetime.now(UTC),
            snippet="Thanks",
        ),
    )
    assert lead.lead_status == LeadStatus.REPLIED.value
    assert lead.email_unread is True
    assert lead.last_replied_at is not None
    assert followup.status == FollowupStatus.CANCELLED.value
    assert lead.next_followup_at is None


def test_sync_skips_duplicate_gmail_message() -> None:
    session = MagicMock()
    settings = _settings()
    account = GmailAccount(
        email="me@example.com",
        status=GmailAccountStatus.ACTIVE.value,
        encrypted_access_token=encrypt_secret("access", settings),
        history_id="10",
        sync_enabled=True,
    )
    account.id = uuid4()
    existing = LeadEmail(
        lead_id=uuid4(),
        gmail_account_id=account.id,
        direction=EmailDirection.INBOUND.value,
        classification=EmailClassification.HUMAN_REPLY.value,
        gmail_message_id="in-1",
        gmail_thread_id="thr-9",
        occurred_at=datetime.now(UTC),
    )
    client = MagicMock()
    service = GmailSyncService(session, settings, client=client)
    service.accounts.access_token_for = MagicMock(return_value="access")  # type: ignore[method-assign]
    with patch.object(service, "_history_message_ids", return_value=(["in-1"], "11")):
        session.scalar.return_value = existing
        result = service.sync_account(account)
    assert result.processed == 0
    assert result.skipped == 1
    client.get_message.assert_not_called()


def test_sync_recovers_when_history_cursor_expires() -> None:
    session = MagicMock()
    settings = _settings()
    account = GmailAccount(
        email="me@example.com",
        status=GmailAccountStatus.ACTIVE.value,
        encrypted_access_token=encrypt_secret("access", settings),
        history_id="stale",
        sync_enabled=True,
    )
    account.id = uuid4()
    client = MagicMock()
    client.list_history.side_effect = __import__(
        "app.integrations.gmail", fromlist=["GmailApiError"]
    ).GmailApiError("gone", status_code=404, code="GMAIL_NOT_FOUND")
    client.list_messages.return_value = {"messages": []}
    client.get_profile.return_value = {"historyId": "999"}
    service = GmailSyncService(session, settings, client=client)
    service.accounts.access_token_for = MagicMock(return_value="access")  # type: ignore[method-assign]
    result = service.sync_account(account)
    assert result.history_reset is True
    assert account.history_id == "999"


def test_token_refresh_on_expired_access() -> None:
    session = MagicMock()
    settings = _settings()
    account = GmailAccount(
        email="me@example.com",
        status=GmailAccountStatus.ACTIVE.value,
        encrypted_access_token=encrypt_secret("old-access", settings),
        encrypted_refresh_token=encrypt_secret("refresh", settings),
        token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
        sync_enabled=True,
    )
    account.id = uuid4()
    client = MagicMock()
    client.refresh_access_token.return_value = OAuthTokens(
        access_token="new-access",
        refresh_token="refresh",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes="scope",
    )
    service = GmailAccountService(session, settings, client=client)
    token = service.access_token_for(account)
    assert token == "new-access"
    assert decrypt_secret(account.encrypted_access_token or "", settings) == "new-access"


def test_bounce_suppresses_address_and_opt_out_cancels_followups() -> None:
    session = MagicMock()
    settings = _settings()
    service = GmailSyncService(session, settings, client=MagicMock())
    lead = Lead(
        business_name="Cafe",
        email="lead@example.com",
        lead_status=LeadStatus.CONTACTED.value,
    )
    lead.id = uuid4()
    followup = Followup(
        lead_id=lead.id,
        scheduled_for=datetime.now(UTC) + timedelta(days=1),
        status=FollowupStatus.SCHEDULED.value,
    )
    session.get.return_value = lead

    # Make list(session.scalars(...)) work for followups, and .first() for outreach.
    class _Result:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def first(self):
            return self._rows[0] if self._rows else None

    session.scalars.side_effect = lambda *a, **k: _Result([followup])

    service._apply_lead_effects(
        lead.id,
        EmailClassification.BOUNCE,
        ParsedGmailMessage(
            gmail_message_id="b1",
            gmail_thread_id="t1",
            rfc_message_id=None,
            in_reply_to=None,
            references=None,
            subject="Delivery Status Notification",
            sender_email="mailer-daemon@google.com",
            recipient_email="lead@example.com",
            body_text="failed",
            body_html=None,
            label_ids=("INBOX",),
            internal_date=datetime.now(UTC),
            snippet=None,
        ),
    )
    assert lead.email_suppressed is True
    assert lead.suppressed_email == "lead@example.com"

    session.scalars.side_effect = lambda *a, **k: _Result([followup])
    service._apply_lead_effects(
        lead.id,
        EmailClassification.OPT_OUT,
        ParsedGmailMessage(
            gmail_message_id="o1",
            gmail_thread_id="t1",
            rfc_message_id=None,
            in_reply_to=None,
            references=None,
            subject="Re: Hi",
            sender_email="lead@example.com",
            recipient_email="me@example.com",
            body_text="Please do not contact me again",
            body_html=None,
            label_ids=("INBOX",),
            internal_date=datetime.now(UTC),
            snippet=None,
        ),
    )
    assert lead.do_not_contact is True
    assert lead.lead_status == LeadStatus.DO_NOT_CONTACT.value
    assert followup.status == FollowupStatus.CANCELLED.value


def test_ambiguous_match_flags_for_review() -> None:
    session = MagicMock()
    settings = _settings()
    account = GmailAccount(email="me@example.com", status=GmailAccountStatus.ACTIVE.value)
    account.id = uuid4()
    service = GmailSyncService(session, settings, client=MagicMock())
    service._match_leads = MagicMock(return_value=[uuid4(), uuid4()])  # type: ignore[method-assign]
    added: list[object] = []
    session.add.side_effect = added.append
    outcome = service._process_message(
        account,
        ParsedGmailMessage(
            gmail_message_id="in-2",
            gmail_thread_id="thr-2",
            rfc_message_id="<in2@mail.gmail.com>",
            in_reply_to=None,
            references=None,
            subject="Re: Hi",
            sender_email="lead@example.com",
            recipient_email="me@example.com",
            body_text="Hello",
            body_html=None,
            label_ids=("INBOX",),
            internal_date=datetime.now(UTC),
            snippet="Hello",
        ),
    )
    assert outcome == "ambiguous"
    stored = next(item for item in added if isinstance(item, LeadEmail))
    assert stored.needs_review is True
    assert stored.classification == EmailClassification.AMBIGUOUS.value


def test_self_reply_on_connected_address_is_a_human_reply() -> None:
    session = MagicMock()
    settings = _settings()
    account = GmailAccount(email="me@example.com", status=GmailAccountStatus.ACTIVE.value)
    account.id = uuid4()
    lead = Lead(
        business_name="Cafe",
        email="me@example.com",
        lead_status=LeadStatus.CONTACTED.value,
    )
    lead.id = uuid4()
    outreach = OutreachMessage(
        lead_id=lead.id,
        subject="Hi",
        message="Hello",
        status=OutreachStatus.SENT.value,
    )
    service = GmailSyncService(session, settings, client=MagicMock())
    service._match_leads = MagicMock(return_value=[lead.id])  # type: ignore[method-assign]
    session.get.return_value = lead

    class _Result:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def first(self):
            return self._rows[0] if self._rows else None

    def scalars_for(statement=None, *args, **kwargs):  # noqa: ANN001
        sql = str(statement)
        if "OutreachMessage" in sql or "outreach_messages" in sql:
            return _Result([outreach])
        return _Result([])

    session.scalars.side_effect = scalars_for
    added: list[object] = []
    session.add.side_effect = added.append
    outcome = service._process_message(
        account,
        ParsedGmailMessage(
            gmail_message_id="reply-1",
            gmail_thread_id="thr-1",
            rfc_message_id="<reply@mail.gmail.com>",
            in_reply_to="<out@mail.gmail.com>",
            references="<out@mail.gmail.com>",
            subject="Re: Hi",
            sender_email="me@example.com",
            recipient_email="me@example.com",
            body_text="Yes, let's talk.",
            body_html=None,
            label_ids=("SENT", "INBOX"),
            internal_date=datetime.now(UTC),
            snippet="Yes",
        ),
    )
    assert outcome == "matched"
    stored = next(item for item in added if isinstance(item, LeadEmail))
    assert stored.direction == EmailDirection.INBOUND.value
    assert stored.classification == EmailClassification.HUMAN_REPLY.value
    assert lead.lead_status == LeadStatus.REPLIED.value
    assert outreach.status == OutreachStatus.REPLIED.value


def test_follow_up_sent_from_connected_account_stays_outbound() -> None:
    session = MagicMock()
    settings = _settings()
    account = GmailAccount(email="me@example.com", status=GmailAccountStatus.ACTIVE.value)
    account.id = uuid4()
    lead = Lead(
        business_name="Cafe",
        email="lead@example.com",
        lead_status=LeadStatus.CONTACTED.value,
    )
    lead.id = uuid4()
    service = GmailSyncService(session, settings, client=MagicMock())
    service._match_leads = MagicMock(return_value=[lead.id])  # type: ignore[method-assign]
    session.get.return_value = lead
    added: list[object] = []
    session.add.side_effect = added.append
    outcome = service._process_message(
        account,
        ParsedGmailMessage(
            gmail_message_id="follow-1",
            gmail_thread_id="thr-1",
            rfc_message_id="<follow@mail.gmail.com>",
            in_reply_to="<out@mail.gmail.com>",
            references="<out@mail.gmail.com>",
            subject="Re: Hi",
            sender_email="me@example.com",
            recipient_email="lead@example.com",
            body_text="Checking in.",
            body_html=None,
            label_ids=("SENT",),
            internal_date=datetime.now(UTC),
            snippet="Checking",
        ),
    )
    assert outcome == "matched"
    stored = next(item for item in added if isinstance(item, LeadEmail))
    assert stored.direction == EmailDirection.OUTBOUND.value
    assert lead.lead_status == LeadStatus.CONTACTED.value


def test_repair_reclassifies_self_reply_stored_as_outgoing() -> None:
    session = MagicMock()
    settings = _settings()
    account = GmailAccount(email="me@example.com", status=GmailAccountStatus.ACTIVE.value)
    account.id = uuid4()
    lead = Lead(
        business_name="Cafe",
        email="me@example.com",
        lead_status=LeadStatus.CONTACTED.value,
    )
    lead.id = uuid4()
    existing = LeadEmail(
        lead_id=lead.id,
        gmail_account_id=account.id,
        direction=EmailDirection.OUTBOUND.value,
        classification=EmailClassification.OUTGOING.value,
        sender_email="me@example.com",
        recipient_email="me@example.com",
        subject="Re: Hi",
        body_text="Yes, let's talk.",
        gmail_message_id="reply-1",
        gmail_thread_id="thr-1",
        rfc_message_id="<reply@mail.gmail.com>",
        in_reply_to="<out@mail.gmail.com>",
        occurred_at=datetime.now(UTC),
    )
    outreach = OutreachMessage(
        lead_id=lead.id,
        subject="Hi",
        message="Hello",
        status=OutreachStatus.SENT.value,
    )
    service = GmailSyncService(session, settings, client=MagicMock())
    session.get.return_value = lead

    class _Result:
        def __init__(self, rows: list[object]) -> None:
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def first(self):
            return self._rows[0] if self._rows else None

    def scalars_for(statement=None, *args, **kwargs):  # noqa: ANN001
        sql = str(statement)
        if "OutreachMessage" in sql or "outreach_messages" in sql:
            return _Result([outreach])
        return _Result([])

    session.scalars.side_effect = scalars_for
    repaired = service._repair_stored_self_reply(account, existing)
    assert repaired is True
    assert existing.direction == EmailDirection.INBOUND.value
    assert existing.classification == EmailClassification.HUMAN_REPLY.value
    assert existing.is_unread is True
    assert outreach.status == OutreachStatus.REPLIED.value
    assert lead.lead_status == LeadStatus.REPLIED.value


def test_authorization_url_uses_minimum_scopes() -> None:
    client = GmailClient(_settings())
    url = client.authorization_url("state-1")
    assert "gmail.send" in url
    assert "gmail.readonly" in url
    assert "mail.google.com" not in url
    assert "access_type=offline" in url
