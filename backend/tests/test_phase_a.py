from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_db_engine
from app.models.automation import AutomationRun, LeadExclusion, OutreachAttempt
from app.models.enums import AttemptKind, AttemptOutcome, AutomationRunStatus, LeadStatus
from app.models.followup import Followup
from app.models.gmail import LeadEmail
from app.models.lead import Lead
from app.services.attempts import (
    derive_strategy,
    outcome_for_intent,
    record_attempt,
    record_outcome,
)
from app.services.automation import schedule_followup_sequence
from app.services.automation_config import (
    AutomationConfig,
    ExclusionSet,
    another_tick_running,
    claim_run,
    effective_settings,
    finish_run,
    get_config,
    mark_stale_runs,
    normalize_exclusion,
    save_config,
)


@pytest.fixture
def db():
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


def _lead(session: Session, **overrides: object) -> Lead:
    values: dict[str, object] = {
        "business_name": "Northwind Plumbing",
        "industry": "plumber",
        "country": "United States",
        "city": "Austin",
        "email": "owner@northwind.example",
        "lead_status": LeadStatus.CONTACTED.value,
        "source_key": f"test:phase-a:{uuid4()}",
    }
    values.update(overrides)
    lead = Lead(**values)  # type: ignore[arg-type]
    session.add(lead)
    session.flush()
    return lead


def _email(session: Session, lead: Lead, body: str = "Hello", **overrides: object) -> LeadEmail:
    from app.models.gmail import GmailAccount

    account = session.scalar(select(GmailAccount).limit(1))
    if account is None:
        account = GmailAccount(email="me@example.com", status="ACTIVE")
        session.add(account)
        session.flush()
    values: dict[str, object] = {
        "lead_id": lead.id,
        "gmail_account_id": account.id,
        "direction": "OUTBOUND",
        "classification": "OUTGOING",
        "recipient_email": lead.email,
        "sender_email": "me@example.com",
        "subject": "Hi",
        "body_text": body,
        "gmail_message_id": f"m-{uuid4()}",
        "gmail_thread_id": "t-1",
        "occurred_at": datetime.now(UTC),
    }
    values.update(overrides)
    row = LeadEmail(**values)  # type: ignore[arg-type]
    session.add(row)
    session.flush()
    return row


# ------------------------------------------------------------------------ config


def test_config_defaults_match_the_agreed_limits(db: Session) -> None:
    config = get_config(db)
    assert config.discovery_daily_limit == 50
    assert config.outreach_daily_limit == 10
    assert config.outreach_mode == "approval"
    assert config.followup_intervals == [4, 10, 20]
    assert config.paused is False


def test_config_round_trips_and_mode_drives_the_send_switch(db: Session) -> None:
    from app.services.automation import get_flags

    config = get_config(db)
    config.outreach_mode = "automatic"
    config.target_countries = ["United States", "united states", "Canada"]
    config.min_score = 55
    config.paused = True
    save_config(db, config)
    loaded = get_config(db)
    assert loaded.outreach_mode == "automatic" and loaded.min_score == 55 and loaded.paused
    assert loaded.target_countries == ["United States", "Canada"]
    assert get_flags(db)["auto_send_enabled"] is True
    loaded.outreach_mode = "approval"
    save_config(db, loaded)
    assert get_flags(db)["auto_send_enabled"] is False


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        AutomationConfig(report_time="25:00")
    with pytest.raises(ValueError):
        AutomationConfig(report_timezone="Mars/Base")
    with pytest.raises(ValueError):
        AutomationConfig(report_email="not an email")
    with pytest.raises(ValueError):
        AutomationConfig(discovery_daily_limit=10_000)
    cfg = AutomationConfig(followup_intervals=[20, 4, 4, 0, 500, 10], followup_max_attempts=2)
    assert cfg.followup_intervals == [4, 10, 20]
    assert cfg.sequence_days() == [4, 10]


def test_effective_settings_apply_the_score_threshold(db: Session) -> None:
    config = get_config(db)
    config.min_score = 72
    save_config(db, config)
    settings, loaded = effective_settings(db, get_settings())
    assert settings.pipeline_min_score == 72 and loaded.min_score == 72


# ---------------------------------------------------------------------- exclusions


def test_exclusions_match_domains_emails_names_and_categories() -> None:
    rows = [
        LeadExclusion(kind="domain", value="bigchain.com"),
        LeadExclusion(kind="email", value="boss@acme.example"),
        LeadExclusion(kind="name", value="holiday inn"),
        LeadExclusion(kind="category", value="casino"),
    ]
    ex = ExclusionSet(rows)
    assert ex.match(name="X", website="https://www.shop.bigchain.com/a", email=None, category=None)
    assert ex.match(name="X", website=None, email="hr@bigchain.com", category=None)
    assert ex.match(name="X", website=None, email="BOSS@acme.example", category=None)
    assert ex.match(name="The Holiday Inn Express", website=None, email=None, category=None)
    assert ex.match(name="X", website=None, email=None, category="Casino")
    assert ex.match(name="Fair Co", website="https://fair.example", email="a@fair.example", category="cafe") is None
    assert ex.match(name="X", website="https://notbigchain.com", email=None, category=None) is None


def test_exclusion_values_are_normalised() -> None:
    assert normalize_exclusion("domain", "https://www.BigChain.com/path") == "bigchain.com"
    assert normalize_exclusion("name", "  Holiday   Inn ") == "holiday inn"


# ------------------------------------------------------------------------ run log


def test_a_run_key_can_only_be_claimed_once(db: Session) -> None:
    first = claim_run(db, "report", "report:2026-11-28")
    assert first is not None
    assert claim_run(db, "report", "report:2026-11-28") is None
    finish_run(db, first, AutomationRunStatus.OK, summary={"sent": 1})
    assert first.status == "OK" and first.finished_at is not None


def test_running_ticks_block_overlap_and_stale_runs_are_closed(db: Session) -> None:
    run = claim_run(db, "tick", f"tick:{uuid4()}")
    assert run is not None and another_tick_running(db)
    run.started_at = datetime.now(UTC) - timedelta(minutes=30)
    db.flush()
    assert not another_tick_running(db)
    assert mark_stale_runs(db) >= 1
    assert db.get(AutomationRun, run.id).status == "FAILED"  # type: ignore[union-attr]


# ------------------------------------------------------------- attempts and outcomes


def test_strategy_is_derived_from_verified_facts() -> None:
    no_site = SimpleNamespace(website_url=None, website_status="missing")
    site = SimpleNamespace(website_url="https://x.example", website_status="analyzed")
    assert derive_strategy(no_site, None) == "no_website"  # type: ignore[arg-type]
    assert derive_strategy(site, SimpleNamespace(design_score=30, performance_score=90, mobile_score=90, ux_score=90)) == "outdated"  # type: ignore[arg-type]
    assert derive_strategy(site, SimpleNamespace(design_score=80, performance_score=40, mobile_score=90, ux_score=90)) == "slow"  # type: ignore[arg-type]
    assert derive_strategy(site, SimpleNamespace(design_score=80, performance_score=90, mobile_score=90, ux_score=50)) == "ux"  # type: ignore[arg-type]
    assert derive_strategy(site, None) == "other"  # type: ignore[arg-type]


def test_reply_intents_map_to_outcomes() -> None:
    assert outcome_for_intent("Interested") is AttemptOutcome.INTERESTED
    assert outcome_for_intent("Meeting Request") is AttemptOutcome.MEETING
    assert outcome_for_intent("Not Interested") is AttemptOutcome.NEGATIVE
    assert outcome_for_intent("Unsubscribe") is AttemptOutcome.UNSUBSCRIBE
    assert outcome_for_intent("Out of Office") is None
    assert outcome_for_intent(None) is None


def test_attempt_is_recorded_once_with_market_facts(db: Session) -> None:
    lead = _lead(db, website_url=None, website_status="missing")
    email = _email(db, lead, body="See it here: https://app.example/api/v1/m/abcdef123456")
    first = record_attempt(db, lead, email, kind=AttemptKind.FIRST, automatic=True)
    again = record_attempt(db, lead, email, kind=AttemptKind.FIRST)
    assert first is not None and again is not None and first.id == again.id
    assert first.category == "plumber" and first.country == "United States"
    assert first.strategy == "no_website" and first.automatic is True
    assert first.outcome == "none"


def test_outcomes_only_move_forward_and_negatives_stick(db: Session) -> None:
    lead = _lead(db)
    email = _email(db, lead)
    attempt = record_attempt(db, lead, email, kind=AttemptKind.FIRST)
    assert attempt is not None
    record_outcome(db, lead.id, AttemptOutcome.REPLY)
    assert attempt.outcome == "reply"
    record_outcome(db, lead.id, AttemptOutcome.INTERESTED)
    assert attempt.outcome == "interested"
    record_outcome(db, lead.id, AttemptOutcome.REPLY)  # weaker: ignored
    assert attempt.outcome == "interested"
    record_outcome(db, lead.id, AttemptOutcome.WON)
    record_outcome(db, lead.id, AttemptOutcome.UNSUBSCRIBE)  # a win is never overwritten
    assert attempt.outcome == "won"


def test_bounce_and_unsubscribe_override_a_reply(db: Session) -> None:
    lead = _lead(db)
    attempt = record_attempt(db, lead, _email(db, lead), kind=AttemptKind.FIRST)
    assert attempt is not None
    record_outcome(db, lead.id, AttemptOutcome.REPLY)
    record_outcome(db, lead.id, AttemptOutcome.UNSUBSCRIBE)
    assert attempt.outcome == "unsubscribe"
    record_outcome(db, lead.id, AttemptOutcome.INTERESTED)  # cannot undo a terminal negative
    assert attempt.outcome == "unsubscribe"


def test_outcome_lands_on_the_latest_email(db: Session) -> None:
    lead = _lead(db)
    old = _email(db, lead, occurred_at=datetime.now(UTC) - timedelta(days=4))
    new = _email(db, lead)
    a_old = record_attempt(db, lead, old, kind=AttemptKind.FIRST)
    a_new = record_attempt(db, lead, new, kind=AttemptKind.FOLLOWUP, sequence_step=1)
    record_outcome(db, lead.id, AttemptOutcome.POSITIVE)
    assert a_old is not None and a_new is not None
    assert a_old.outcome == "none" and a_new.outcome == "positive"
    rows = list(db.scalars(select(OutreachAttempt).where(OutreachAttempt.lead_id == lead.id)))
    assert len(rows) == 2


# ----------------------------------------------------------- configurable follow-ups


def test_follow_up_intervals_come_from_the_config(db: Session) -> None:
    lead = _lead(db)
    config = get_config(db)
    config.followup_intervals = [2, 6, 14]
    config.followup_max_attempts = 2
    save_config(db, config)
    start = datetime.now(UTC)
    assert schedule_followup_sequence(db, lead, None, start) == 2
    days = sorted(
        round((r.scheduled_for - start).total_seconds() / 86400)
        for r in db.scalars(select(Followup).where(Followup.lead_id == lead.id))
    )
    assert days == [2, 6]


def test_zero_attempts_means_no_follow_ups(db: Session) -> None:
    lead = _lead(db)
    config = get_config(db)
    config.followup_max_attempts = 0
    save_config(db, config)
    assert schedule_followup_sequence(db, lead, None) == 0
