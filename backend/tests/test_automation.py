from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import create_db_engine
from app.models.enums import FollowupStatus, LeadStatus
from app.models.followup import Followup
from app.models.lead import Lead
from app.models.outreach import OutreachMessage
from app.services import automation
from app.services.automation import (
    check_draft_quality,
    get_flags,
    in_send_window,
    process_due_followups,
    schedule_followup_sequence,
    set_flags,
)
from app.services.pipeline import PipelineService, RetryLater


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/x",
        "postgres_url": "",
        "outreach_postal_address": "1 Main St, Austin, TX",
        "outreach_timezone": "UTC",
        "outreach_send_start_hour": 9,
        "outreach_send_end_hour": 17,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _lead(**overrides: object) -> Lead:
    values: dict[str, object] = {
        "business_name": "Northwind Plumbing",
        "country": "United States",
        "email": "owner@northwind.example",
        "lead_status": LeadStatus.QUALIFIED.value,
        "lead_score": 80,
        "do_not_contact": False,
        "email_suppressed": False,
        "pipeline_paused": False,
    }
    values.update(overrides)
    return Lead(**values)  # type: ignore[arg-type]


GOOD_BODY = (
    "Hi there,\n\nI looked at Northwind Plumbing online and noticed customers cannot request "
    "a quote from their phone. I put together a short homepage concept that fixes that.\n\nBest,\nIbrar"
)


def test_send_window_is_weekdays_during_business_hours() -> None:
    settings = _settings()
    assert in_send_window(settings, datetime(2026, 11, 30, 10, 0, tzinfo=UTC))  # Monday
    assert not in_send_window(settings, datetime(2026, 11, 30, 18, 0, tzinfo=UTC))
    assert not in_send_window(settings, datetime(2026, 11, 30, 8, 59, tzinfo=UTC))
    assert not in_send_window(settings, datetime(2026, 11, 28, 10, 0, tzinfo=UTC))  # Saturday


def test_send_window_uses_the_configured_timezone() -> None:
    settings = _settings(outreach_timezone="America/Chicago")
    # 15:00 UTC is 09:00 in Chicago (CST, UTC-6) on a Monday.
    assert in_send_window(settings, datetime(2026, 11, 30, 15, 0, tzinfo=UTC))
    assert not in_send_window(settings, datetime(2026, 11, 30, 10, 0, tzinfo=UTC))


def test_good_draft_passes_the_quality_gate() -> None:
    assert check_draft_quality("Homepage idea for Northwind", GOOD_BODY, "Northwind Plumbing") == []


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("", GOOD_BODY, "missing subject"),
        ("Hi", "Too short", "message is too short"),
        ("Hi", GOOD_BODY + " {{first_name}}", "unfilled placeholder"),
        ("Hi", GOOD_BODY.replace("Hi there", "Hi [Name]"), "unfilled placeholder"),
        ("Hi", "x" * 3000, "message is too long"),
        ("Hi", "A perfectly fine message about websites for local shops. " * 3, "business"),
    ],
)
def test_bad_drafts_are_held_for_review(subject: str, body: str, expected: str) -> None:
    problems = check_draft_quality(subject, body, "Northwind Plumbing")
    assert any(expected in problem for problem in problems), problems


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> PipelineService:
    svc = PipelineService(session=Mock(), settings=_settings())
    monkeypatch.setattr(svc, "_notify", lambda *a, **k: None)
    monkeypatch.setattr(svc, "_auto_send_enabled", lambda: True)
    import app.services.automation_config as config_module
    import app.services.outreach_policy as policy_module

    monkeypatch.setattr(config_module.ExclusionSet, "load", classmethod(lambda cls, _s: cls([])))
    monkeypatch.setattr(config_module, "get_config", lambda _s: config_module.AutomationConfig())
    monkeypatch.setattr(policy_module, "first_emails_sent_today", lambda _s: 0)
    monkeypatch.setattr(automation, "recent_outreach_bodies", lambda *_a, **_k: [])
    return svc


def _draft(**overrides: object) -> OutreachMessage:
    values: dict[str, object] = {
        "id": uuid4(),
        "subject": "A homepage idea for Northwind Plumbing",
        "message": GOOD_BODY,
        "status": "DRAFT",
    }
    values.update(overrides)
    return SimpleNamespace(**values)  # type: ignore[return-value]


def test_send_step_holds_poor_drafts_for_review(service: PipelineService) -> None:
    service.session.scalar.return_value = _draft(message="Too short")
    outcome, detail = service._step_send(_lead())
    assert outcome == "SKIPPED" and "Needs review" in detail


def test_send_step_leaves_strict_countries_to_you(service: PipelineService) -> None:
    service.session.scalar.return_value = _draft()
    outcome, detail = service._step_send(_lead(country="Germany"))
    assert outcome == "SKIPPED" and "manually" in detail


def test_send_step_waits_outside_the_window(
    service: PipelineService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.session.scalar.return_value = _draft()
    monkeypatch.setattr(automation, "in_send_window", lambda *_a, **_k: False)
    with pytest.raises(RetryLater):
        service._step_send(_lead())


def test_send_step_waits_when_the_daily_cap_is_reached(
    service: PipelineService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.session.scalar.return_value = _draft()
    monkeypatch.setattr(automation, "in_send_window", lambda *_a, **_k: True)
    import app.services.outreach_policy as policy

    monkeypatch.setattr(policy, "sent_today", lambda _s: 999)
    with pytest.raises(RetryLater):
        service._step_send(_lead())


def test_send_step_sends_and_schedules_the_follow_up_sequence(
    service: PipelineService, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.gmail_mail as gmail_mail
    import app.services.outreach_policy as policy

    draft = _draft()
    service.session.scalar.return_value = draft
    monkeypatch.setattr(automation, "in_send_window", lambda *_a, **_k: True)
    monkeypatch.setattr(policy, "sent_today", lambda _s: 0)
    captured: dict[str, object] = {}

    def fake_send(self, lead_id, data, **_kwargs):
        captured["request"] = data
        return SimpleNamespace(occurred_at=datetime.now(UTC))

    monkeypatch.setattr(gmail_mail.GmailMailService, "send", fake_send)
    scheduled: list[object] = []
    monkeypatch.setattr(
        automation, "schedule_followup_sequence", lambda *a, **k: scheduled.append(a) or 3
    )
    outcome, detail = service._step_send(_lead())
    assert outcome == "DONE" and "Follow-ups scheduled" in detail
    assert captured["request"].idempotency_key == f"auto-send:{draft.id}"  # type: ignore[attr-defined]
    assert len(scheduled) == 1


def test_send_is_only_planned_when_switched_on(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = PipelineService(session=None, settings=_settings())  # type: ignore[arg-type]
    monkeypatch.setattr(svc, "_has_ready_mockup", lambda _id: False)
    monkeypatch.setattr(svc, "_has_outreach", lambda _id: True)
    monkeypatch.setattr(svc, "_has_unsent_draft", lambda _id: True)
    done = [
        SimpleNamespace(step=s, status="DONE", attempts=1, max_attempts=3)
        for s in ("audit", "mockup", "draft")
    ]
    lead = _lead()
    assert svc.decide_next_step(lead, done) is None  # switch is off
    monkeypatch.setattr(svc, "_auto_send_enabled", lambda: True)
    assert svc.decide_next_step(lead, done) == "send"


@pytest.fixture
def db_session():
    engine = create_db_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_flags_default_off_and_persist(db_session: Session) -> None:
    assert get_flags(db_session) == {
        "auto_send_enabled": False,
        "followups_auto_send": False,
        "breakup_auto_send": False,
    }
    set_flags(db_session, {"auto_send_enabled": True, "unknown": True})  # type: ignore[dict-item]
    flags = get_flags(db_session)
    assert flags["auto_send_enabled"] is True and flags["followups_auto_send"] is False


def test_follow_up_sequence_is_created_once(db_session: Session) -> None:
    lead = _lead(source_key="test:auto:1", lead_status=LeadStatus.CONTACTED.value)
    db_session.add(lead)
    db_session.flush()
    start = datetime.now(UTC)
    assert schedule_followup_sequence(db_session, lead, None, start) == 3
    assert schedule_followup_sequence(db_session, lead, None, start) == 0
    rows = list(
        db_session.scalars(
            select(Followup).where(Followup.lead_id == lead.id).order_by(Followup.scheduled_for)
        )
    )
    days = [round((row.scheduled_for - start).total_seconds() / 86400) for row in rows]
    assert days == [4, 10, 20]
    assert lead.next_followup_at == rows[0].scheduled_for


def _due_followup(session: Session, **lead_overrides: object) -> tuple[Lead, Followup]:
    lead = _lead(
        source_key=f"test:auto:{uuid4()}",
        lead_status=LeadStatus.CONTACTED.value,
        **lead_overrides,
    )
    session.add(lead)
    session.flush()
    followup = Followup(
        lead_id=lead.id,
        scheduled_for=datetime.now(UTC) - timedelta(hours=1),
        type="email",
        status=FollowupStatus.DUE.value,
    )
    session.add(followup)
    session.flush()
    return lead, followup


def _patch_engine(monkeypatch: pytest.MonkeyPatch, sent: list[object]) -> None:
    import app.services.gmail_mail as gmail_mail

    monkeypatch.setattr(automation, "in_send_window", lambda *_a, **_k: True)
    monkeypatch.setattr(automation, "latest_outbound", lambda *_a, **_k: SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(automation, "enforce_daily_cap", lambda *_a, **_k: None)
    monkeypatch.setattr(
        gmail_mail.GmailMailService,
        "reply",
        lambda self, lead_id, email_id, data, **_k: (sent.append(data), SimpleNamespace(id=uuid4()))[1],
    )


def test_follow_ups_do_nothing_while_the_switch_is_off(db_session: Session) -> None:
    _due_followup(db_session)
    assert process_due_followups(db_session, _settings()) == {"sent": 0, "waiting": 0, "skipped": 0}


def test_due_follow_up_is_sent_as_a_threaded_reply_and_completed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    lead, followup = _due_followup(db_session)
    set_flags(db_session, {"followups_auto_send": True})
    sent: list[object] = []
    _patch_engine(monkeypatch, sent)

    result = process_due_followups(db_session, _settings())

    assert result["sent"] == 1
    assert len(sent) == 1
    body = sent[0].body  # type: ignore[attr-defined]
    assert 'reply "unsubscribe"' in body and "1 Main St" in body
    assert sent[0].idempotency_key == f"followup:{followup.id}"  # type: ignore[attr-defined]
    db_session.refresh(followup)
    db_session.refresh(lead)
    assert followup.status == FollowupStatus.COMPLETED.value
    assert lead.lead_status == LeadStatus.FOLLOW_UP.value


def test_follow_ups_skip_leads_that_replied_or_opted_out(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_flags(db_session, {"followups_auto_send": True})
    sent: list[object] = []
    _patch_engine(monkeypatch, sent)
    _due_followup(db_session)  # eligible
    replied, _ = _due_followup(db_session)
    replied.lead_status = LeadStatus.REPLIED.value
    opted_out, _ = _due_followup(db_session)
    opted_out.do_not_contact = True
    germany, _ = _due_followup(db_session)
    germany.country = "Germany"
    db_session.flush()

    result = process_due_followups(db_session, _settings())
    assert result["sent"] == 1 and result["skipped"] == 3


def test_closing_note_needs_its_own_switch(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    lead, followup = _due_followup(db_session)
    for _ in range(2):  # two follow-ups already completed: this is step 3
        db_session.add(
            Followup(
                lead_id=lead.id,
                scheduled_for=datetime.now(UTC) - timedelta(days=1),
                type="email",
                status=FollowupStatus.COMPLETED.value,
            )
        )
    db_session.flush()
    set_flags(db_session, {"followups_auto_send": True})
    sent: list[object] = []
    _patch_engine(monkeypatch, sent)

    assert process_due_followups(db_session, _settings())["sent"] == 0
    set_flags(db_session, {"breakup_auto_send": True})
    assert process_due_followups(db_session, _settings())["sent"] == 1
