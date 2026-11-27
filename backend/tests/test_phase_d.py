import base64
import email as email_lib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import create_db_engine
from app.integrations.gmail import GmailClient
from app.models.activity import Activity
from app.models.automation import AutomationRun, OutreachAttempt
from app.models.gmail import GmailAccount, LeadEmail
from app.models.lead import Lead
from app.services import daily_report
from app.services.automation_config import AutomationConfig
from app.services.daily_report import build_report, headline, maybe_send_daily_report
from app.services.insights import (
    activity,
    build_insights,
    market_table,
    mockup_effect,
    recommendations,
    rollup,
    smoothed,
)

NOW = datetime(2026, 11, 27, 10, 0, tzinfo=UTC)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/x",
        "postgres_url": "",
        "public_base_url": "https://app.example.com",
        "outreach_sender_email": "owner@example.com",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def factory():
    engine = create_db_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()

    def make() -> Session:
        return Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield make
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def db(factory):
    with factory() as session:
        yield session


def _lead(session: Session, **overrides: object) -> Lead:
    values: dict[str, object] = {
        "business_name": f"Biz {uuid4().hex[:6]}",
        "industry": "Plumber",
        "country": "United States",
        "email": "o@biz.example",
        "lead_status": "CONTACTED",
        "source": "openstreetmap",
        "source_key": f"test:d:{uuid4()}",
        "website_status": "missing",
    }
    values.update(overrides)
    lead = Lead(**values)  # type: ignore[arg-type]
    session.add(lead)
    session.flush()
    return lead


def _attempt(
    session: Session,
    lead: Lead,
    *,
    kind: str = "first",
    outcome: str = "none",
    sent_at: datetime = NOW - timedelta(hours=2),
    mockup: bool = False,
    strategy: str = "no_website",
) -> OutreachAttempt:
    account = session.scalar(select(GmailAccount).limit(1))
    if account is None:
        account = GmailAccount(email="me@example.com", status="ACTIVE")
        session.add(account)
        session.flush()
    row = LeadEmail(
        lead_id=lead.id, gmail_account_id=account.id, direction="OUTBOUND", classification="OUTGOING",
        recipient_email="o@biz.example", sender_email="me@example.com", subject="s", body_text="b",
        gmail_message_id=f"m-{uuid4()}", gmail_thread_id="t", occurred_at=sent_at,
    )
    session.add(row)
    session.flush()
    attempt = OutreachAttempt(
        lead_id=lead.id, email_id=row.id, kind=kind, strategy=strategy, mockup_included=mockup,
        category=lead.industry, country=lead.country, sent_at=sent_at, outcome=outcome,
        outcome_at=(sent_at + timedelta(hours=1)) if outcome != "none" else None,
    )
    session.add(attempt)
    session.flush()
    return attempt


# ------------------------------------------------------------------------ activity


def test_activity_counts_the_window_only(db: Session) -> None:
    inside = _lead(db, created_at=NOW - timedelta(hours=3))
    _lead(db, created_at=NOW - timedelta(days=3))
    _attempt(db, inside, outcome="interested")
    _attempt(db, _lead(db), kind="followup", outcome="reply")
    _attempt(db, _lead(db), outcome="bounce")
    _attempt(db, _lead(db), outcome="unsubscribe")
    _attempt(db, _lead(db), sent_at=NOW - timedelta(days=5), outcome="positive")  # outside
    db.add(
        Activity(
            lead_id=inside.id, type="status_changed", title="s",
            details={"from": "REPLIED", "to": "WON"}, created_at=NOW - timedelta(hours=1),
        )
    )
    db.flush()
    day = activity(db, NOW - timedelta(hours=24), NOW + timedelta(seconds=1))
    assert day["leads_discovered"] >= 1
    assert day["first_emails"] == 3 and day["followups_sent"] == 1 and day["emails_sent"] == 4
    assert day["interested"] == 1 and day["positive_replies"] == 1
    assert day["bounces"] == 1 and day["unsubscribes"] == 1
    assert day["delivered_estimate"] == 3  # four sent, one bounced
    assert day["clients_won"] == 1


def test_inbound_human_replies_are_counted(db: Session) -> None:
    lead = _lead(db)
    _attempt(db, lead)
    account = db.scalar(select(GmailAccount).limit(1))
    for classification, hours in (("HUMAN_REPLY", 1), ("OUT_OF_OFFICE", 1), ("HUMAN_REPLY", 72)):
        db.add(
            LeadEmail(
                lead_id=lead.id, gmail_account_id=account.id, direction="INBOUND",
                classification=classification, recipient_email="me@example.com",
                sender_email="o@biz.example", subject="Re", body_text="x",
                gmail_message_id=f"i-{uuid4()}", gmail_thread_id="t",
                occurred_at=NOW - timedelta(hours=hours),
            )
        )
    db.flush()
    assert activity(db, NOW - timedelta(hours=24), NOW)["replies"] == 1


# --------------------------------------------------------------- markets and ranking


def test_smoothing_stops_small_samples_from_winning() -> None:
    overall = 0.05
    assert smoothed(2, 2, overall) < 0.2  # 100% of 2 emails is pulled far below 100%
    assert smoothed(0, 0, overall) == pytest.approx(overall)
    assert smoothed(15, 100, overall) > smoothed(1, 20, overall)


def test_market_table_ranks_by_quality_and_flags_thin_data(db: Session) -> None:
    for i in range(20):  # dentists in Canada: 20 sent, 6 positive
        _attempt(db, _lead(db, industry="Dentist", country="Canada"), outcome="positive" if i < 6 else "none")
    for i in range(20):  # plumbers in the US: 20 sent, 1 positive
        _attempt(db, _lead(db, industry="Plumber", country="United States"), outcome="positive" if i < 1 else "none")
    _attempt(db, _lead(db, industry="Baker", country="Ireland"), outcome="won")  # 1 of 1, thin
    rows = {r["label"]: r for r in market_table(db, "category")}
    assert rows["Dentist"]["positive_rate"] == 30.0 and rows["Dentist"]["enough_data"]
    assert rows["Baker"]["enough_data"] is False
    order = [r["label"] for r in market_table(db, "category")]
    # Judged markets rank first, by quality; the 1-email Baker is last despite a win.
    assert order.index("Dentist") < order.index("Plumber") < order.index("Baker")
    assert {r["label"] for r in market_table(db, "country")} >= {"Canada", "United States", "Ireland"}


def test_revenue_comes_from_won_deal_values(db: Session) -> None:
    _attempt(db, _lead(db, industry="Gym", country="Canada", lead_status="WON", deal_value=1200), outcome="won")
    _attempt(db, _lead(db, industry="Gym", country="Canada", lead_status="WON", deal_value=800), outcome="won")
    _attempt(db, _lead(db, industry="Gym", country="Canada", lead_status="LOST", deal_value=999), outcome="none")
    gym = next(r for r in market_table(db, "category") if r["label"] == "Gym")
    assert gym["revenue"] == 2000.0 and gym["clients"] == 2


def test_mockup_effect_compares_the_two_groups(db: Session) -> None:
    for i in range(16):
        _attempt(db, _lead(db), mockup=True, outcome="positive" if i < 4 else "none")
        _attempt(db, _lead(db), mockup=False, outcome="positive" if i < 1 else "none")
    effect = mockup_effect(db)
    assert effect["with_mockup"]["enough_data"] and effect["without_mockup"]["enough_data"]
    assert effect["with_mockup"]["positive_rate"] > effect["without_mockup"]["positive_rate"]


def test_weekly_and_monthly_rollups_sum_the_days() -> None:
    days = [
        {"date": "2026-11-23", "discovered": 5, "sent": 2, "followups": 0, "replies": 1, "positive": 0, "clients": 0},
        {"date": "2026-11-29", "discovered": 3, "sent": 1, "followups": 1, "replies": 0, "positive": 1, "clients": 0},
        {"date": "2026-11-30", "discovered": 4, "sent": 0, "followups": 0, "replies": 0, "positive": 0, "clients": 1},
    ]
    weeks = rollup(days, "week")
    assert [w["date"] for w in weeks] == ["2026-11-23", "2026-11-30"]
    assert weeks[0]["discovered"] == 8 and weeks[0]["sent"] == 3
    months = rollup(days, "month")
    assert months[0]["date"] == "2026-11-01" and months[0]["discovered"] == 12 and months[0]["clients"] == 1


def test_build_insights_has_every_section_and_a_full_daily_series(db: Session) -> None:
    lead = _lead(db, created_at=NOW - timedelta(hours=2))
    _attempt(db, lead, outcome="interested")
    data = build_insights(db, _settings(), AutomationConfig(), days=30, now=NOW)
    for key in (
        "today", "last_24h", "discovery", "daily", "weekly", "monthly", "funnel", "categories",
        "countries", "strategies", "variants", "mockup_effect", "promising", "waiting", "rates",
        "recommendations",
    ):
        assert key in data, key
    assert len(data["daily"]) == 30
    assert data["daily"][-1]["date"] == "2026-11-27"
    assert data["funnel"]["emailed"] >= 1 and data["funnel"]["positive"] >= 1
    assert any(p["lead_id"] == str(lead.id) and p["outcome"] == "interested" for p in data["promising"])


# --------------------------------------------------------------- recommendations


def _data(**overrides: object) -> dict:
    data = {
        "funnel": {"emailed": 120, "replied": 12, "positive": 6, "clients": 1, "leads": 200},
        "waiting": {"interested": 0, "drafts": 0, "followups_due": 0},
        "discovery": {"total": 50, "rejected_by_reason": {}},
        "categories": [], "countries": [],
        "mockup_effect": {
            "with_mockup": {"enough_data": False, "positive_rate": 0, "sent": 0, "reply_rate": 0},
            "without_mockup": {"enough_data": False, "positive_rate": 0, "sent": 0, "reply_rate": 0},
        },
        "manual_only_leads": 0,
    }
    data.update(overrides)
    return data


def test_recommendations_only_say_what_the_data_supports() -> None:
    config = AutomationConfig()
    assert recommendations(_data(), config) == []
    tips = recommendations(
        _data(
            waiting={"interested": 2, "drafts": 3, "followups_due": 1},
            discovery={"total": 5, "rejected_by_reason": {"chain": 9, "low_score": 2}},
            categories=[
                {"label": "Dentist", "enough_data": True, "positive_rate": 20.0, "positive": 4, "sent": 20},
                {"label": "Cafe", "enough_data": True, "positive_rate": 0.0, "positive": 0, "sent": 40},
            ],
            manual_only_leads=4,
        ),
        config,
    )
    text = " ".join(tips)
    assert "Reply to 2 interested prospects" in text
    assert "3 drafts are waiting" in text
    assert "national chains" in text
    assert "Dentist is your strongest category" in text
    assert "Cafe (category)" in text and "no positive replies" in text
    assert "4 qualified leads are in manual-only countries" in text


def test_no_sends_gets_a_getting_started_tip() -> None:
    tips = recommendations(_data(funnel={"emailed": 0, "replied": 0, "positive": 0, "clients": 0, "leads": 0}), AutomationConfig())
    assert any("No emails have been sent yet" in t for t in tips)


# --------------------------------------------------------------------------- report


def test_report_has_every_requested_section_and_escapes_text(db: Session) -> None:
    lead = _lead(db, business_name="<b>Evil</b> & Sons", created_at=NOW - timedelta(hours=2), lead_status="REPLIED")
    _attempt(db, lead, outcome="interested")
    report = build_report(db, _settings(), AutomationConfig(), NOW)
    text, html = report["text"], report["html"]
    for heading in ("LEAD DISCOVERY", "OUTREACH", "MOST PROMISING RIGHT NOW", "FOR TOMORROW"):
        assert heading in text
    assert "Delivered (estimate" in text
    assert "<b>Evil</b>" not in html and "&lt;b&gt;Evil&lt;/b&gt; &amp; Sons" in html
    assert "https://app.example.com/insights" in html
    assert report["subject"].startswith("Acquisition report Nov 27")
    assert "interested" in report["subject"]


def test_headline_reads_naturally() -> None:
    quiet = {"emails_sent": 0, "leads_discovered": 0, "replies": 0, "interested": 0}
    assert headline(quiet) == "A quiet day. Nothing was found or sent."
    busy = {"emails_sent": 1, "leads_discovered": 12, "replies": 2, "interested": 1}
    assert headline(busy) == "Found 12 new leads, sent 1 email, got 2 replies, 1 interested."


def test_html_message_is_multipart_alternative() -> None:
    client = GmailClient.__new__(GmailClient)
    raw = client._build_raw_message(
        to="a@b.example", subject="Report", body_text="plain", body_html="<p>html</p>",
        from_email="me@example.com", in_reply_to=None, references=None, attachments=[],
    )
    message = email_lib.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    assert message.get_content_type() == "multipart/alternative"
    assert [p.get_content_type() for p in message.get_payload()] == ["text/plain", "text/html"]


# ------------------------------------------------------------------ the schedule


def _config(**overrides: object) -> AutomationConfig:
    values: dict[str, object] = {"report_time": "08:00", "report_timezone": "UTC", "report_email": "me@example.com"}
    values.update(overrides)
    return AutomationConfig(**values)  # type: ignore[arg-type]


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    log: list[dict] = []

    def fake(session, settings, config, now=None):
        log.append({"to": config.report_email})
        return {"to": config.report_email, "subject": "s"}

    monkeypatch.setattr(daily_report, "send_report", fake)
    return log


def test_report_waits_for_its_time(factory, sent) -> None:
    early = datetime(2026, 11, 27, 7, 59, tzinfo=UTC)
    assert maybe_send_daily_report(factory, _settings(), _config(), early) == "not due yet"
    assert sent == []


def test_report_is_sent_once_a_day(factory, sent) -> None:
    due = datetime(2026, 11, 27, 8, 5, tzinfo=UTC)
    assert maybe_send_daily_report(factory, _settings(), _config(), due) == "sent"
    assert maybe_send_daily_report(factory, _settings(), _config(), due + timedelta(minutes=10)) == "already sent"
    assert len(sent) == 1
    next_day = datetime(2026, 11, 28, 8, 5, tzinfo=UTC)
    assert maybe_send_daily_report(factory, _settings(), _config(), next_day) == "sent"
    assert len(sent) == 2


def test_report_timezone_decides_when_it_is_due(factory, sent) -> None:
    config = _config(report_timezone="Asia/Karachi")  # UTC+5: 08:00 local is 03:00 UTC
    assert maybe_send_daily_report(factory, _settings(), config, datetime(2026, 11, 27, 2, 0, tzinfo=UTC)) == "not due yet"
    assert maybe_send_daily_report(factory, _settings(), config, datetime(2026, 11, 27, 3, 5, tzinfo=UTC)) == "sent"


def test_failed_report_retries_later_and_gives_up_after_three(factory, monkeypatch) -> None:
    def broken(*_args, **_kwargs):
        raise AppError(code="GMAIL_NOT_CONNECTED", message="Connect Gmail first.", status_code=409)

    monkeypatch.setattr(daily_report, "send_report", broken)
    start = datetime(2026, 11, 27, 8, 0, tzinfo=UTC)
    assert maybe_send_daily_report(factory, _settings(), _config(), start).startswith("failed")
    assert maybe_send_daily_report(factory, _settings(), _config(), start + timedelta(minutes=10)) == "waiting to retry"
    assert maybe_send_daily_report(factory, _settings(), _config(), start + timedelta(minutes=40)).startswith("failed")
    assert maybe_send_daily_report(factory, _settings(), _config(), start + timedelta(minutes=80)).startswith("failed")
    assert maybe_send_daily_report(factory, _settings(), _config(), start + timedelta(minutes=120)) == "gave up for today"
    with factory() as session:
        runs = list(session.scalars(select(AutomationRun).where(AutomationRun.kind == "report")))
        assert len(runs) == 3 and all(r.status == "FAILED" and "Connect Gmail" in (r.error or "") for r in runs)


def test_report_needs_an_address(db: Session) -> None:
    with pytest.raises(AppError) as caught:
        daily_report.send_report(db, _settings(outreach_sender_email=""), _config(report_email=""), NOW)
    assert caught.value.code == "REPORT_NO_ADDRESS"
