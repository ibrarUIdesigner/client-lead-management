import random
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import create_db_engine
from app.models.automation import AutomationRun, OutreachAttempt
from app.models.gmail import GmailAccount, LeadEmail
from app.models.lead import Lead
from app.services.automation_config import AutomationConfig, save_config
from app.services.discovery_engine import candidate_cells, pick_cells
from app.services.insights import explore_suggestions, offer_types
from app.services.learning import (
    FACTOR_MAX,
    FACTOR_MIN,
    LearningState,
    _Cohort,
    load_state,
    maybe_update_learning,
    state_from_config,
    step_toward,
    summary_for_ui,
    target_factor,
    update_learning,
    weighted_choice,
)
from app.services.outreach_priority import score_lead
from app.services.outreach_variants import STYLE_KEYS, TONES, pick_variant

TODAY = date(2026, 11, 27)
NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/x",
        "postgres_url": "",
        "outreach_country_policy": '{"US": "allow", "CA": "allow"}',
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


# --------------------------------------------------------------------- the maths


def test_target_is_neutral_until_there_is_evidence() -> None:
    assert target_factor(_Cohort(sent=14, points=14), 0.1) == 1.0
    assert target_factor(_Cohort(sent=100, points=50), 0.0) == 1.0
    strong = target_factor(_Cohort(sent=60, points=30), 0.1)  # 0.5 per send against 0.1 overall
    weak = target_factor(_Cohort(sent=60, points=0), 0.1)
    assert strong > 1.0 and weak < 1.0
    assert FACTOR_MIN <= weak and strong <= FACTOR_MAX


def test_a_small_sample_is_pulled_back_toward_the_average() -> None:
    lucky = target_factor(_Cohort(sent=15, points=15), 0.4)  # 1 point per send on 15 emails
    proven = target_factor(_Cohort(sent=200, points=200), 0.4)
    assert 1.0 < lucky < proven


def test_a_single_update_moves_at_most_ten_percent() -> None:
    assert step_toward(1.0, 2.0) == pytest.approx(1.1)
    assert step_toward(1.0, 0.5) == pytest.approx(0.9)
    assert step_toward(1.5, 1.0) == pytest.approx(1.35)
    assert step_toward(1.0, 1.04) == pytest.approx(1.04)
    assert step_toward(1.95, 2.0) <= FACTOR_MAX
    assert step_toward(0.52, 0.5) >= FACTOR_MIN


def test_big_swings_take_many_days() -> None:
    value, days = 1.0, 0
    while value < 1.9:
        value = step_toward(value, 2.0)
        days += 1
    assert days >= 7  # 1.1 ** 7 is about 1.95


# ---------------------------------------------------------------- state and pins


def test_pins_boost_and_learning_off_is_neutral() -> None:
    config = AutomationConfig(pinned_categories=["Dentist"], pinned_countries=["Canada"])
    state = state_from_config({"factors": {"category": {"dentist": 0.7, "plumber": 1.4}}}, config)
    assert state.factor("category", "dentist") == 1.5  # pinned beats a weak result
    assert state.factor("category", "Plumber") == 1.4
    assert state.factor("country", "canada") == 1.5
    assert state.market("Plumber", "Brazil") == pytest.approx(1.4**0.5)

    frozen = state_from_config(
        {"factors": {"category": {"plumber": 1.8}}}, AutomationConfig(learning_enabled=False)
    )
    assert frozen.factor("category", "Plumber") == 1.0


def test_weighted_choice_is_repeatable_and_respects_weights() -> None:
    options = ("a", "b", "c")
    assert weighted_choice(options, [1, 1, 1], 0.0) == "a"
    assert weighted_choice(options, [1, 1, 1], 0.99) == "c"
    assert weighted_choice(options, [0.01, 10, 0.01], 0.5) == "b"
    picks = Counter(weighted_choice(options, [1, 8, 1], i / 1000) for i in range(1000))
    assert picks["b"] > 700


# --------------------------------------------------------------- where it is used


def _cells(categories=("dentist",), countries=("United States", "Canada")):
    return candidate_cells(AutomationConfig(target_categories=list(categories), target_countries=list(countries)))


def _first_country(cells, learning, seed):
    return pick_cells(
        cells, {}, settings=_settings(), created_today_by_country=Counter(),
        created_today_by_category=Counter(), daily_limit=50, count=1, now=NOW,
        rng=random.Random(seed), learning=learning,
    )[0].country


def test_discovery_leans_toward_markets_that_earned_replies() -> None:
    cells = _cells()
    boosted = state_from_config({"factors": {"country": {"canada": 2.0, "united states": 0.5}}}, AutomationConfig())
    picks = Counter(_first_country(cells, boosted, seed) for seed in range(400))
    # The effect is softened on purpose (geometric mean) and a fifth of picks explore evenly.
    assert picks["Canada"] > picks["United States"] * 1.25
    neutral = Counter(_first_country(cells, LearningState(), seed) for seed in range(400))
    assert abs(neutral["Canada"] - neutral["United States"]) < 120


def test_discovery_keeps_exploring_even_when_one_market_wins() -> None:
    cells = _cells()
    extreme = state_from_config({"factors": {"country": {"canada": 2.0, "united states": 0.5}}}, AutomationConfig())
    picks = Counter(_first_country(cells, extreme, seed) for seed in range(500))
    assert picks["United States"] >= 40  # never starved


def test_excluded_countries_are_not_searched() -> None:
    config = AutomationConfig(
        target_categories=["dentist"], target_countries=["United States", "Canada"], excluded_countries=["canada"]
    )
    assert {c.country for c in candidate_cells(config)} == {"United States"}


def _score(lead: Lead, learning: LearningState | None):
    return score_lead(
        lead, audit=None, has_mockup=False, has_research=False, has_named_contact=False,
        settings=_settings(), learning=learning,
    )


def _lead(**overrides: object) -> Lead:
    values: dict[str, object] = {
        "business_name": "Acme", "industry": "Dentist", "country": "Canada", "email": "a@b.example",
        "lead_score": 80, "website_status": "missing", "lead_status": "QUALIFIED",
    }
    values.update(overrides)
    return Lead(**values)  # type: ignore[arg-type]


def test_outreach_ranking_uses_learned_factors_and_the_avoid_list() -> None:
    lead = _lead()
    plain = _score(lead, LearningState())
    boosted = _score(lead, state_from_config({"factors": {"category": {"dentist": 1.5}, "strategy": {"no_website": 1.2}}}, AutomationConfig()))
    assert boosted.score > plain.score
    assert any("Learned from your results" in r for r in boosted.reasons)
    avoided = _score(lead, state_from_config({}, AutomationConfig(excluded_countries=["Canada"])))
    assert avoided.blocked


def test_writing_styles_follow_results_but_keep_a_quarter_even() -> None:
    state = state_from_config(
        {"factors": {"tone": {"warm": 2.0, "direct": 0.5, "professional": 0.5}, "style": {"question": 2.0}}},
        AutomationConfig(),
    )
    tones = Counter(pick_variant(uuid4(), learning=state)[0] for _ in range(600))
    assert tones["warm"] > tones["direct"] * 1.5 and tones["direct"] > 20
    styles = Counter(pick_variant(uuid4(), learning=state)[1] for _ in range(600))
    assert styles["question"] == max(styles.values())
    assert set(styles) <= set(STYLE_KEYS) and set(tones) <= set(TONES)


def test_a_retry_changes_both_tone_and_style_even_when_learning() -> None:
    state = state_from_config({"factors": {"tone": {"warm": 2.0}}}, AutomationConfig())
    for _ in range(100):
        lead_id = uuid4()
        first, retry = pick_variant(lead_id, learning=state), pick_variant(lead_id, shift=1, learning=state)
        assert first[0] != retry[0] and first[1] != retry[1]
        assert pick_variant(lead_id, learning=state) == first  # stable


# ------------------------------------------------------------ the daily update (db)


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


def _send(session: Session, *, category: str, country: str, outcome: str, strategy: str = "no_website", framework: str = "warm/question") -> None:
    lead = Lead(
        business_name=f"B {uuid4().hex[:5]}", industry=category, country=country,
        source_key=f"test:e:{uuid4()}", lead_status="CONTACTED", email="o@b.example",
    )
    session.add(lead)
    account = session.scalar(select(GmailAccount).limit(1))
    if account is None:
        account = GmailAccount(email="me@example.com", status="ACTIVE")
        session.add(account)
    session.flush()
    row = LeadEmail(
        lead_id=lead.id, gmail_account_id=account.id, direction="OUTBOUND", classification="OUTGOING",
        recipient_email="o@b.example", sender_email="me@example.com", subject="s", body_text="b",
        gmail_message_id=f"m-{uuid4()}", gmail_thread_id="t", occurred_at=NOW - timedelta(days=2),
    )
    session.add(row)
    session.flush()
    session.add(
        OutreachAttempt(
            lead_id=lead.id, email_id=row.id, kind="first", strategy=strategy, framework=framework,
            category=category, country=country, sent_at=NOW - timedelta(days=2), outcome=outcome,
            outcome_at=None if outcome == "none" else NOW - timedelta(days=1),
        )
    )
    session.flush()


def test_nothing_changes_before_enough_emails(db: Session) -> None:
    for _ in range(10):
        _send(db, category="Dentist", country="Canada", outcome="positive")
    result = update_learning(db, AutomationConfig(), TODAY)
    assert result["status"] == "waiting for data" and result["needed"] == 30
    assert load_state(db, AutomationConfig()).factors == {}


def _seed_results(db: Session) -> None:
    for i in range(20):  # dentists in Canada do well
        _send(db, category="Dentist", country="Canada", outcome="interested" if i < 8 else "none", framework="warm/question")
    for _ in range(20):  # cafes in Canada get nothing
        _send(db, category="Cafe", country="Canada", outcome="none", framework="direct/finding")
    for _ in range(5):  # too few to judge
        _send(db, category="Baker", country="Ireland", outcome="positive")


def test_update_moves_factors_gradually_toward_results(db: Session) -> None:
    _seed_results(db)
    config = AutomationConfig()
    first = update_learning(db, config, TODAY)
    assert first["status"] == "updated" and first["moves"] > 0
    state = load_state(db, config)
    assert state.factor("category", "Dentist") == pytest.approx(1.1, abs=0.001)  # one step, not a leap
    assert state.factor("category", "Cafe") == pytest.approx(0.9, abs=0.001)
    assert state.factor("category", "Baker") == 1.0  # five emails: not judged
    assert state.factor("tone", "warm") > 1.0 > state.factor("tone", "direct")
    assert state.factor("style", "question") > 1.0

    update_learning(db, config, TODAY + timedelta(days=1))
    again = load_state(db, config)
    assert again.factor("category", "Dentist") == pytest.approx(1.21, abs=0.002)
    assert again.history and again.history[0]["date"] == "2026-11-28"


def test_learning_off_changes_nothing(db: Session) -> None:
    _seed_results(db)
    assert update_learning(db, AutomationConfig(learning_enabled=False), TODAY) == {"status": "off"}
    assert load_state(db, AutomationConfig()).factors == {}


def test_a_thing_that_loses_its_evidence_drifts_back_to_neutral(db: Session) -> None:
    _seed_results(db)
    config = AutomationConfig()
    update_learning(db, config, TODAY)
    assert load_state(db, config).factor("category", "Dentist") > 1.0
    # The dentist emails disappear (for example deleted): the multiplier fades instead of sticking.
    for _ in range(12):  # keep the total above the minimum so updates still run
        _send(db, category="Cafe", country="Canada", outcome="none")
    for attempt in db.scalars(select(OutreachAttempt).where(OutreachAttempt.category == "Dentist")):
        db.delete(attempt)
    db.flush()
    for day in range(1, 4):
        update_learning(db, config, TODAY + timedelta(days=day))
    assert load_state(db, config).factor("category", "Dentist") == pytest.approx(1.0, abs=0.001)


def test_daily_run_happens_once_and_is_logged(factory) -> None:
    with factory() as session:
        _seed_results(session)
        session.commit()
    config = AutomationConfig()
    assert maybe_update_learning(factory, config, NOW) == "updated"
    assert maybe_update_learning(factory, config, NOW + timedelta(hours=3)) == "already ran today"
    with factory() as session:
        run = session.scalar(select(AutomationRun).where(AutomationRun.kind == "learning"))
        assert run is not None and run.status == "OK" and run.summary["status"] == "updated"
        ui = summary_for_ui(load_state(session, config))
        assert any(item["name"] == "dentist" for item in ui["boosted"])
        assert any(item["name"] == "cafe" for item in ui["reduced"])


def test_pinned_markets_keep_their_boost_after_updates(db: Session) -> None:
    _seed_results(db)
    config = AutomationConfig(pinned_categories=["Cafe"])
    update_learning(db, config, TODAY)
    assert load_state(db, config).factor("category", "Cafe") == 1.5  # results say 0.9, the pin wins


# ------------------------------------------------------------------ suggestions


def test_offer_types_split_new_site_and_redesign(db: Session) -> None:
    for i in range(16):
        _send(db, category="Dentist", country="Canada", strategy="no_website", outcome="positive" if i < 4 else "none")
    for _ in range(3):
        _send(db, category="Dentist", country="Canada", strategy="outdated", outcome="none")
    dentist = next(r for r in offer_types(db) if r["label"] == "Dentist")
    assert dentist["new_site"]["sent"] == 16 and dentist["new_site"]["positive_rate"] == 25.0
    assert dentist["new_site"]["enough_data"] and not dentist["redesign"]["enough_data"]


def test_explore_ideas_need_data_and_are_honest(db: Session) -> None:
    config = AutomationConfig()
    assert explore_suggestions(db, _settings(), config) == []  # nothing sent: everything is untried
    for i in range(8):
        _send(db, category="Dentist", country="Canada", outcome="positive" if i < 2 else "none")
    ideas = explore_suggestions(db, _settings(), config)
    early = [i for i in ideas if "Early signs" in i["reason"]]
    assert early and "2 positive of 8" in early[0]["reason"]
    for _ in range(30):
        _send(db, category="Cafe", country="Canada", outcome="none")
    later = explore_suggestions(db, _settings(), config, limit=20)
    assert any(i["reason"].startswith("Not tried yet") for i in later)
    assert not any(i["name"] == "Cafe" and "Not tried" in i["reason"] for i in later)


def test_config_round_trip_keeps_learning_controls(db: Session) -> None:
    from app.services.automation_config import get_config

    config = get_config(db)
    config.pinned_categories = ["Dentist", "dentist"]
    config.excluded_countries = ["Germany"]
    config.learning_enabled = False
    save_config(db, config)
    loaded = get_config(db)
    assert loaded.pinned_categories == ["Dentist"]
    assert loaded.excluded_countries == ["Germany"] and loaded.learning_enabled is False
