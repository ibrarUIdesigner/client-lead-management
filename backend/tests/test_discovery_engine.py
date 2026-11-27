import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import create_db_engine
from app.integrations.source_errors import PlaceSourceError
from app.models.lead import Lead
from app.models.market import DiscoveryRejection, MarketCell
from app.models.automation import LeadExclusion
from app.services.automation_config import AutomationConfig, ExclusionSet
from app.services.discovery_engine import (
    CellKey,
    candidate_cells,
    cooldown_days,
    pick_cells,
    remaining_quota,
    run_discovery_slice,
    yield_weight,
)
from app.services.discovery_filter import is_chain, reject_reason
from app.services.place_listings import FoundBusiness


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/x",
        "postgres_url": "",
        "discovery_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _biz(name: str = "Northwind Plumbing", **overrides: object) -> FoundBusiness:
    values: dict[str, object] = {
        "source_key": f"test:{uuid4()}",
        "source": "openstreetmap",
        "name": name,
        "industry": "Plumber",
        "phone": "555-0100",
        "email": None,
        "website_url": None,
        "facebook_url": None,
        "instagram_url": None,
        "google_maps_url": None,
        "city": "Austin",
        "country": "United States",
        "website_status": "missing",
        "lead_score": 85,
        "description": "d",
        "notes": "n",
        "tags": ["discovered"],
    }
    values.update(overrides)
    return FoundBusiness(**values)  # type: ignore[arg-type]


# ----------------------------------------------------------------------- the filter


def test_chains_are_detected_without_false_matches() -> None:
    assert is_chain("McDonald's")
    assert is_chain("Starbucks Reserve")
    assert is_chain("Holiday Inn Express")
    assert not is_chain("Midastouch Salon")
    assert not is_chain("Northwind Plumbing")


def test_reject_reasons() -> None:
    config = AutomationConfig()
    none = ExclusionSet([])
    assert reject_reason(_biz(), config, none) is None
    assert reject_reason(_biz("Subway"), config, none) == "chain"
    assert reject_reason(_biz(phone=None), config, none) == "no_contact"
    assert reject_reason(_biz(lead_score=10), config, none) == "low_score"
    excluded = ExclusionSet([LeadExclusion(kind="name", value="northwind")])
    assert reject_reason(_biz(), config, excluded) == "excluded"


def test_business_type_preferences_filter_leads() -> None:
    none = ExclusionSet([])
    only_new_sites = AutomationConfig(business_types=["no_website"])
    only_redesigns = AutomationConfig(business_types=["outdated", "slow", "ux"])
    with_site = _biz(website_status="present", website_url="https://x.example", lead_score=48)
    assert reject_reason(with_site, only_new_sites, none) == "not_preferred"
    assert reject_reason(_biz(), only_redesigns, none) == "not_preferred"
    assert reject_reason(with_site, only_redesigns, none) is None


# --------------------------------------------------------------------- the allocator


def test_candidate_cells_follow_targets() -> None:
    everywhere = candidate_cells(AutomationConfig())
    assert len({c.country for c in everywhere}) >= 6
    assert len({c.category for c in everywhere}) >= 15

    narrow = candidate_cells(
        AutomationConfig(target_countries=["Canada", "Brazil"], target_categories=["dentist"])
    )
    countries = {c.country for c in narrow}
    assert countries == {"Canada", "Brazil"}
    assert {c.category for c in narrow} == {"dentist"}
    assert any(c.country == "Brazil" and c.city == "Capital" for c in narrow)


def test_cooldown_grows_for_empty_searches() -> None:
    assert cooldown_days(0, produced=True) == 2
    assert cooldown_days(1, produced=False) == 3
    assert cooldown_days(2, produced=False) == 6
    assert cooldown_days(3, produced=False) == 12
    assert cooldown_days(20, produced=False) == 45


def test_yield_weight_blends_with_a_prior() -> None:
    assert yield_weight(0, 0) == pytest.approx(3.0)
    assert yield_weight(30, 2) > yield_weight(0, 2)
    # One lucky search does not dominate the prior.
    assert yield_weight(10, 1) < 10


def _pick(candidates, states=None, *, today_country=None, seed=1, count=5, settings=None, limit=50):
    return pick_cells(
        candidates,
        states or {},
        settings=settings or _settings(),
        created_today_by_country=Counter(today_country or {}),
        created_today_by_category=Counter(),
        daily_limit=limit,
        count=count,
        now=datetime.now(UTC),
        rng=random.Random(seed),
    )


def test_picks_spread_across_countries_and_categories() -> None:
    cells = candidate_cells(AutomationConfig())
    picked = _pick(cells, count=6)
    assert len(picked) == 6
    # A country and category pair is never picked twice in one slice.
    assert len({(c.country, c.category) for c in picked}) == 6
    assert len({c.country for c in picked}) >= 3


def test_resting_cells_are_skipped() -> None:
    cells = candidate_cells(AutomationConfig(target_countries=["Canada"], target_categories=["dentist"]))
    now = datetime.now(UTC)
    states = {
        c.tuple: MarketCell(
            category=c.category, country=c.country, city=c.city, searches=3,
            next_eligible_at=now + timedelta(days=5),
        )
        for c in cells
    }
    assert _pick(cells, states) == []
    states[cells[0].tuple].next_eligible_at = now - timedelta(minutes=1)
    assert _pick(cells, states) == [cells[0]]


def test_countries_that_filled_today_are_picked_less() -> None:
    cells = candidate_cells(
        AutomationConfig(target_countries=["United States", "Canada"], target_categories=["dentist"])
    )
    both_allowed = _settings(outreach_country_policy='{"US": "allow", "CA": "allow"}')
    us = sum(
        1
        for seed in range(300)
        for c in _pick(
            cells, today_country={"United States": 50}, seed=seed, count=1, settings=both_allowed
        )
        if c.country == "United States"
    )
    canada = 300 - us
    assert canada > us * 2


def test_contactable_countries_are_preferred() -> None:
    cells = candidate_cells(
        AutomationConfig(target_countries=["United States", "Germany"], target_categories=["dentist"])
    )
    first = [_pick(cells, seed=s, count=1)[0].country for s in range(400)]
    assert first.count("United States") > first.count("Germany")


def test_unexplored_markets_get_a_share_of_picks() -> None:
    cells = candidate_cells(
        AutomationConfig(target_countries=["United States"], target_categories=["dentist"])
    )
    searched, fresh = cells[0], cells[1]
    states = {
        searched.tuple: MarketCell(
            category=searched.category, country=searched.country, city=searched.city,
            searches=5, created=50,
        )
    }
    picks = [_pick(cells[:2], states, seed=s, count=1)[0] for s in range(300)]
    assert sum(1 for p in picks if p.tuple == fresh.tuple) > 40


# ------------------------------------------------------------------ the whole slice


@pytest.fixture
def factory():
    """A session factory whose sessions all share one transaction that is rolled back."""
    engine = create_db_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    # The dev database may already hold leads found today (the app searches on start-up).
    # Inside this rolled-back transaction, start from a clean day so the quota maths is exact.
    connection.execute(
        text(
            "DELETE FROM leads WHERE created_at >= date_trunc('day', now()) "
            "AND source IN ('openstreetmap','google_places','yelp','yell','businesslist',"
            "'epages','apollo','serpapi','scrapingbee')"
        )
    )

    def make() -> Session:
        return Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield make
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def _collector(businesses: list[FoundBusiness]):
    calls: list[dict[str, object]] = []

    def collect(**kwargs):
        calls.append(kwargs)
        return list(businesses), []

    collect.calls = calls  # type: ignore[attr-defined]
    return collect


def _config(**overrides: object) -> AutomationConfig:
    values: dict[str, object] = {
        "target_countries": ["Canada"],
        "target_categories": ["dentist"],
        "discovery_daily_limit": 3,
    }
    values.update(overrides)
    return AutomationConfig(**values)  # type: ignore[arg-type]


def test_slice_keeps_the_best_leads_up_to_the_quota_and_remembers_the_rest(factory) -> None:
    businesses = [
        _biz(f"Biz {i}", lead_score=score, phone=f"555-01{i}0", city="Toronto", country="Canada")
        for i, score in enumerate([85, 72, 48, 85, 70])
    ] + [
        _biz("Subway", city="Toronto", country="Canada"),
        _biz("No Contact Ltd", phone=None, city="Toronto", country="Canada"),
    ]
    collector = _collector(businesses)
    summary = run_discovery_slice(
        factory, _settings(), _config(), collector=collector, rng=random.Random(2), max_cells=1
    )
    assert summary.created == 3 and summary.quota_remaining == 0
    assert summary.rejected == {"chain": 1, "no_contact": 1}
    assert summary.cells_searched == 1 and len(collector.calls) == 1  # type: ignore[attr-defined]

    with factory() as session:
        kept = list(session.scalars(select(Lead).where(Lead.source_key.in_([b.source_key for b in businesses]))))
        assert len(kept) == 3
        assert sorted(lead.lead_score for lead in kept) == [72, 85, 85]  # the two 85s and the 72 beat 70 and 48
        assert {r.reason for r in session.scalars(select(DiscoveryRejection))} >= {"chain", "no_contact"}
        cell = session.scalar(select(MarketCell))
        assert cell is not None and cell.searches == 1 and cell.created == 3
        assert cell.next_eligible_at is not None


def test_slice_stops_when_the_quota_is_already_met(factory) -> None:
    collector = _collector([_biz(city="Toronto", country="Canada")])
    config = _config(discovery_daily_limit=1)
    first = run_discovery_slice(factory, _settings(), config, collector=collector, max_cells=1)
    assert first.created == 1
    second = run_discovery_slice(factory, _settings(), config, collector=collector, max_cells=1)
    assert second.stopped_because == "daily quota reached" and second.cells_searched == 0
    with factory() as session:
        assert remaining_quota(session, config) == 0


def test_known_and_rejected_businesses_are_not_evaluated_again(factory) -> None:
    business = _biz("Subway", city="Toronto", country="Canada")
    other = _biz("Fresh Plumbing", phone="555-0199", city="Toronto", country="Canada")
    collector = _collector([business, other])
    config = _config(discovery_daily_limit=10)
    run_discovery_slice(factory, _settings(), config, collector=collector, max_cells=1)
    # Clear the cooldown so the same market is searched again.
    with factory() as session:
        for cell in session.scalars(select(MarketCell)):
            cell.next_eligible_at = None
        session.commit()
    again = run_discovery_slice(factory, _settings(), config, collector=collector, max_cells=1)
    assert again.created == 0 and again.duplicates == 2 and again.rejected == {}
    with factory() as session:
        cell = session.scalar(select(MarketCell).where(MarketCell.empty_streak == 1))
        assert cell is not None
        assert cell.next_eligible_at > datetime.now(UTC) + timedelta(days=2)


def test_a_failing_source_rests_the_market_and_is_reported(factory) -> None:
    def broken(**_kwargs):
        raise PlaceSourceError("The directory did not answer.")

    summary = run_discovery_slice(
        factory, _settings(), _config(), collector=broken, max_cells=1
    )
    assert summary.created == 0 and summary.cells_searched == 0
    assert "did not answer" in summary.errors[0]
    with factory() as session:
        cell = session.scalar(select(MarketCell))
        assert cell is not None and cell.last_error and cell.next_eligible_at is not None


def test_slice_does_nothing_when_discovery_is_off(factory) -> None:
    collector = _collector([_biz()])
    off = run_discovery_slice(
        factory, _settings(discovery_enabled=False), _config(), collector=collector
    )
    zero = run_discovery_slice(
        factory, _settings(), _config(discovery_daily_limit=0), collector=collector
    )
    assert off.stopped_because == "discovery is off" and zero.stopped_because == "discovery is off"
    assert not collector.calls  # type: ignore[attr-defined]


def test_excluded_businesses_are_rejected_not_saved(factory) -> None:
    with factory() as session:
        session.add(LeadExclusion(kind="name", value="blocked co"))
        session.commit()
    collector = _collector([_biz("Blocked Co", city="Toronto", country="Canada")])
    summary = run_discovery_slice(factory, _settings(), _config(), collector=collector, max_cells=1)
    assert summary.created == 0 and summary.rejected == {"excluded": 1}
