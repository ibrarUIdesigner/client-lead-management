from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import create_db_engine
from app.integrations.gmail import GmailClient
from app.models.automation import OutreachAttempt
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.outreach import OutreachMessage
from app.models.pipeline_job import PipelineJob
from app.services.automation import check_draft_quality, recent_outreach_bodies
from app.services.automation_config import get_config, save_config
from app.services.draft_similarity import SIMILAR_AT, most_similar, similarity, strip_signature
from app.services.outreach_ai import _instructions
from app.services.outreach_priority import (
    MarketPerformance,
    rank_leads,
    score_lead,
)
from app.services.outreach_variants import STRATEGY_GUIDANCE, STYLE_HINTS, pick_variant
from app.services.pipeline import PipelineService


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/x",
        "postgres_url": "",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _lead(**overrides: object) -> Lead:
    values: dict[str, object] = {
        "business_name": "Northwind Plumbing",
        "industry": "Plumber",
        "country": "United States",
        "city": "Austin",
        "email": "owner@northwind.example",
        "lead_status": LeadStatus.QUALIFIED.value,
        "lead_score": 80,
        "website_url": None,
        "website_status": "missing",
        "do_not_contact": False,
        "email_suppressed": False,
    }
    values.update(overrides)
    return Lead(**values)  # type: ignore[arg-type]


def _score(lead: Lead, **kwargs: object):
    base: dict[str, object] = {
        "audit": None,
        "has_mockup": False,
        "has_research": False,
        "has_named_contact": False,
        "settings": _settings(),
    }
    base.update(kwargs)
    return score_lead(lead, **base)  # type: ignore[arg-type]


# --------------------------------------------------------------------- priority


def test_no_website_with_mockup_outranks_a_plain_lead() -> None:
    plain = _score(_lead(lead_score=48, website_url="https://x.example", website_status="analyzed"))
    strong = _score(_lead(), has_mockup=True, has_research=True, has_named_contact=True)
    assert strong.strategy == "no_website" and strong.score > plain.score + 40
    assert any("Mockup ready" in reason for reason in strong.reasons)


def test_strategy_points_follow_the_audit() -> None:
    site = _lead(website_url="https://x.example", website_status="analyzed", lead_score=48)

    def with_audit(**scores: int):
        audit = SimpleNamespace(design_score=80, performance_score=90, mobile_score=90, ux_score=90)
        for key, value in scores.items():
            setattr(audit, key, value)
        return _score(site, audit=audit)

    assert with_audit(design_score=30).strategy == "outdated"
    assert with_audit(performance_score=30).strategy == "slow"
    assert with_audit(ux_score=40).strategy == "ux"
    assert with_audit(design_score=30).score > with_audit(performance_score=30).score
    assert with_audit(performance_score=30).score > with_audit(ux_score=40).score


def test_country_policy_changes_priority() -> None:
    allowed = _score(_lead(country="United States"))
    manual = _score(_lead(country="Germany"))
    blocked = _score(_lead(country="Germany"), settings=_settings(outreach_country_policy='{"DE": "block"}'))
    assert allowed.score - manual.score == pytest.approx(20)
    assert blocked.blocked and not allowed.blocked


def test_past_results_nudge_the_ranking_only_with_enough_data() -> None:
    lead = _lead()
    none = MarketPerformance()
    assert none.factor("Plumber", "United States") == 1.0
    thin = MarketPerformance(overall_sent=10, overall_positive=3)
    assert thin.factor("Plumber", "United States") == 1.0

    perf = MarketPerformance(
        overall_sent=200,
        overall_positive=10,
        by_market={
            ("plumber", "united states"): (60, 9),  # 15%, far above the 5% average
            ("dentist", "canada"): (60, 0),
        },
    )
    assert 1.0 < perf.factor("Plumber", "United States") <= 1.25
    assert 0.8 <= perf.factor("Dentist", "Canada") < 1.0
    assert perf.factor("Unknown", "Nowhere") == pytest.approx(1.0)
    boosted = _score(lead, performance=perf)
    assert boosted.score > _score(lead).score
    assert any("Past results" in reason for reason in boosted.reasons)


# ----------------------------------------------------------------- repetition


def test_similarity_catches_near_copies_and_ignores_signatures() -> None:
    a = (
        "Hi Sam,\n\nI noticed customers searching for a plumber in Austin cannot find a page "
        "to request a quote. I sketched a simple homepage that fixes that for you.\n\n"
        "Worth a quick look?\n\nIbrar\nibrar@example.com\n+92 300 0000000"
    )
    near_copy = a.replace("Sam", "Jo").replace("plumber", "electrician")
    different = (
        "Hello,\n\nYour booking page loads slowly on phones, so visitors may leave before they "
        "call. A faster layout would keep more of them.\n\nOpen to a short breakdown?\n\nIbrar\n"
        "ibrar@example.com\n+92 300 0000000"
    )
    assert similarity(a, near_copy) >= SIMILAR_AT
    assert similarity(a, different) < SIMILAR_AT
    assert most_similar(a, [different, near_copy]) >= SIMILAR_AT
    assert most_similar(a, []) == 0.0
    assert "ibrar@example.com" not in strip_signature(a)


def test_quality_gate_flags_text_that_reads_like_a_recent_email() -> None:
    body = (
        "Hi there,\n\nI looked at Northwind Plumbing online and noticed customers cannot request "
        "a quote from their phone. I put together a short homepage concept that fixes that.\n\nBest"
    )
    assert check_draft_quality("Idea for Northwind", body, "Northwind Plumbing") == []
    problems = check_draft_quality("Idea for Northwind", body, "Northwind Plumbing", recent_bodies=[body])
    assert any("recent email" in p for p in problems)


# ------------------------------------------------------------- strategies, styles


def test_each_strategy_adds_its_own_angle_to_the_prompt() -> None:
    prompts = {
        key: _instructions("FACTS", "review", strategy=key, style_hint="")
        for key in STRATEGY_GUIDANCE
    }
    assert len(set(prompts.values())) == len(STRATEGY_GUIDANCE)
    assert "no website" in prompts["no_website"].lower()
    assert "dated" in prompts["outdated"].lower()
    assert "slow" in prompts["slow"].lower()
    assert "FACTS" in prompts["ux"]
    styled = _instructions("FACTS", "review", strategy="slow", style_hint=STYLE_HINTS["question"])
    assert STYLE_HINTS["question"] in styled


def test_variants_are_stable_per_lead_and_spread_across_leads() -> None:
    lead_id = uuid4()
    assert pick_variant(lead_id) == pick_variant(lead_id)
    assert pick_variant(lead_id) != pick_variant(lead_id, shift=1)
    combos = {pick_variant(uuid4()) for _ in range(200)}
    assert len(combos) >= 10


# ------------------------------------------------------------ unsubscribe header


def test_unsubscribe_header_is_added_to_the_raw_message() -> None:
    import base64
    import email

    client = GmailClient.__new__(GmailClient)
    raw = client._build_raw_message(
        to="a@b.example",
        subject="Hi",
        body_text="Body",
        from_email="me@example.com",
        in_reply_to=None,
        references=None,
        attachments=[],
        list_unsubscribe="mailto:me@example.com?subject=unsubscribe",
    )
    message = email.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    assert message["List-Unsubscribe"] == "<mailto:me@example.com?subject=unsubscribe>"
    plain = client._build_raw_message(
        to="a@b.example", subject="Hi", body_text="Body", from_email="me@example.com",
        in_reply_to=None, references=None, attachments=[],
    )
    assert "List-Unsubscribe" not in base64.urlsafe_b64decode(plain + "=" * (-len(plain) % 4)).decode()


# ------------------------------------------------------- daily draft slots (database)


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


def _queued_draft(session: Session, **lead_overrides: object) -> tuple[Lead, PipelineJob]:
    lead = _lead(source_key=f"test:c:{uuid4()}", **lead_overrides)
    session.add(lead)
    session.flush()
    job = PipelineJob(lead_id=lead.id, step="draft", status="QUEUED")
    session.add(job)
    session.flush()
    return lead, job


def test_only_the_best_leads_get_the_daily_draft_slots(db: Session) -> None:
    config = get_config(db)
    config.outreach_daily_limit = 2
    save_config(db, config)
    weak, weak_job = _queued_draft(db, lead_score=45, website_url="https://x.example", website_status="analyzed")
    mid, mid_job = _queued_draft(db, lead_score=72, website_status="social_only")
    top, top_job = _queued_draft(db, lead_score=90)
    service = PipelineService(db, _settings())
    assert service.draft_slots_left() == 2

    first = service.claim_next()
    assert first is not None and first.id == top_job.id
    second = service.claim_next()
    assert second is not None and second.id == mid_job.id
    assert service.draft_slots_left() == 0
    assert service.claim_next() is None
    db.refresh(weak_job)
    assert weak_job.status == "QUEUED"  # waits for a free slot


def test_a_better_lead_found_later_takes_the_next_slot(db: Session) -> None:
    config = get_config(db)
    config.outreach_daily_limit = 1
    save_config(db, config)
    _queued_draft(db, lead_score=55, website_url="https://x.example", website_status="analyzed")
    _, best_job = _queued_draft(db, lead_score=95)
    claimed = PipelineService(db, _settings()).claim_next()
    assert claimed is not None and claimed.id == best_job.id


def test_blocked_countries_are_skipped_not_drafted(db: Session) -> None:
    _, job = _queued_draft(db, country="Germany")
    settings = _settings(outreach_country_policy='{"DE": "block"}')
    assert PipelineService(db, settings).claim_next() is None
    db.refresh(job)
    assert job.status == "SKIPPED"


def test_other_steps_are_not_starved_by_waiting_drafts(db: Session) -> None:
    config = get_config(db)
    config.outreach_daily_limit = 0
    save_config(db, config)
    _queued_draft(db)
    lead = _lead(source_key=f"test:c:{uuid4()}")
    db.add(lead)
    db.flush()
    audit_job = PipelineJob(lead_id=lead.id, step="audit", status="QUEUED")
    db.add(audit_job)
    db.flush()
    claimed = PipelineService(db, _settings()).claim_next()
    assert claimed is not None and claimed.id == audit_job.id


def test_rank_leads_batches_and_reports_reasons(db: Session) -> None:
    a = _lead(source_key=f"test:c:{uuid4()}", lead_score=90)
    b = _lead(source_key=f"test:c:{uuid4()}", lead_score=40, country="Germany")
    db.add_all([a, b])
    db.flush()
    ranks = rank_leads(db, _settings(), [a.id, b.id])
    assert ranks[a.id].score > ranks[b.id].score
    assert ranks[a.id].reasons and ranks[b.id].strategy == "no_website"
    assert rank_leads(db, _settings(), []) == {}


def test_recent_bodies_exclude_cancelled_and_the_current_draft(db: Session) -> None:
    lead = _lead(source_key=f"test:c:{uuid4()}")
    db.add(lead)
    db.flush()
    keep = OutreachMessage(lead_id=lead.id, channel="email", subject="a", message="Kept body text", status="SENT")
    skipped = OutreachMessage(lead_id=lead.id, channel="email", subject="b", message="Skipped body", status="CANCELLED")
    current = OutreachMessage(lead_id=lead.id, channel="email", subject="c", message="Current body", status="DRAFT")
    db.add_all([keep, skipped, current])
    db.flush()
    bodies = recent_outreach_bodies(db, exclude_id=current.id)
    assert "Kept body text" in bodies
    assert "Skipped body" not in bodies and "Current body" not in bodies


def test_attempt_records_the_writing_variant(db: Session) -> None:
    from app.models.enums import AttemptKind
    from app.models.gmail import GmailAccount, LeadEmail
    from app.services.attempts import record_attempt

    lead = _lead(source_key=f"test:c:{uuid4()}", lead_status=LeadStatus.CONTACTED.value)
    db.add(lead)
    account = GmailAccount(email="me@example.com", status="ACTIVE")
    db.add(account)
    db.flush()
    message = OutreachMessage(
        lead_id=lead.id, channel="email", subject="s", message="m", status="SENT", variant="warm/question"
    )
    db.add(message)
    row = LeadEmail(
        lead_id=lead.id, gmail_account_id=account.id, direction="OUTBOUND", classification="OUTGOING",
        recipient_email=lead.email, sender_email="me@example.com", subject="s", body_text="m",
        gmail_message_id=f"m-{uuid4()}", gmail_thread_id="t", occurred_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    record_attempt(db, lead, row, kind=AttemptKind.FIRST, message=message)
    attempt = db.scalar(select(OutreachAttempt).where(OutreachAttempt.lead_id == lead.id))
    assert attempt is not None and attempt.framework == "warm/question"
