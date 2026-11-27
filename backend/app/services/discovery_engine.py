"""Daily lead discovery: spread a quota across categories and countries, rotate, remember.

How a slice works (one slice runs inside each scheduler tick):
  1. Work out how many leads are still needed today (daily limit minus leads found today).
  2. Pick a few "cells" (category in a city) to search. Cells that gave nothing new recently
     rest for days. Countries and categories that already filled today's quota are less
     likely. Countries where automatic outreach is allowed are preferred, because leads there
     can be contacted. A fifth of picks go to cells never searched, so new markets are tried.
  3. Search, drop what you do not want (with a stored reason), keep the best-scoring
     businesses first until the quota is met, and record what the cell produced.
"""

from __future__ import annotations

import logging
import math
import random
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.integrations.place_sources import collect_places
from app.integrations.source_errors import PlaceSourceError
from app.models.lead import Lead
from app.models.market import DiscoveryRejection, MarketCell
from app.services.automation_config import AutomationConfig, ExclusionSet
from app.services.discovery_filter import reject_reason
from app.services.discovery_markets import ANYWHERE_MARKETS, GLOBAL_SOURCES
from app.services.learning import NEUTRAL, LearningState, load_state
from app.services.outreach_policy import country_code, policy_table
from app.services.place_listings import CATEGORIES, FoundBusiness, category_label

logger = logging.getLogger(__name__)

EXPLORE_SHARE = 0.2
PRIOR_LEADS_PER_SEARCH = 3.0
PRIOR_WEIGHT = 2.0
POLICY_WEIGHT = {"allow": 1.0, "manual": 0.5, "block": 0.1}
DISCOVERED_SOURCES = (
    "openstreetmap",
    "google_places",
    "yelp",
    "yell",
    "businesslist",
    "epages",
    "apollo",
    "serpapi",
    "scrapingbee",
)
SOURCE_FLAGS = {
    "openstreetmap": "use_openstreetmap",
    "google": "use_google",
    "yelp": "use_yelp",
    "yell": "use_yell",
    "businesslist": "use_businesslist",
    "epages": "use_epages",
    "apollo": "use_apollo",
    "serpapi": "use_serpapi",
    "scrapingbee": "use_scrapingbee",
}

Collector = Callable[..., tuple[list[FoundBusiness], list[str]]]


@dataclass(frozen=True)
class CellKey:
    category: str
    country: str
    city: str
    sources: frozenset[str] = field(default=GLOBAL_SOURCES, compare=False)

    @property
    def tuple(self) -> tuple[str, str, str]:
        return (self.category, self.country, self.city)


@dataclass
class SliceSummary:
    quota_remaining: int = 0
    cells_searched: int = 0
    found: int = 0
    created: int = 0
    duplicates: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    searched: list[str] = field(default_factory=list)
    stopped_because: str = ""

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


# --------------------------------------------------------------------------- cells


def candidate_cells(config: AutomationConfig) -> list[CellKey]:
    """Every category and place the daily quota may be spread over."""
    categories = config.target_categories or [c.value for c in CATEGORIES]
    avoid = {c.casefold() for c in config.excluded_countries}
    if config.target_countries:
        wanted = {c.casefold() for c in config.target_countries}
        places = [(m.country, m.city, m.sources) for m in ANYWHERE_MARKETS if m.country.casefold() in wanted]
        known = {country.casefold() for country, _, _ in places}
        for country in config.target_countries:
            if country.casefold() not in known:
                # Not in the built-in list: search the country through the global sources.
                places.append((country, "Capital", GLOBAL_SOURCES))
    else:
        places = [(m.country, m.city, m.sources) for m in ANYWHERE_MARKETS]
    return [
        CellKey(category=category.strip().lower(), country=country, city=city, sources=sources)
        for category in categories
        for country, city, sources in places
        if country.casefold() not in avoid
    ]


def contact_weight(settings: Settings, country: str) -> float:
    code = country_code(country)
    policy = policy_table(settings).get(code or "", "manual")
    return POLICY_WEIGHT[policy]


def cooldown_days(empty_streak: int, produced: bool) -> float:
    """Rest period after a search. Empty searches rest longer each time."""
    if produced:
        return 2.0
    return float(min(45, 3 * 2 ** max(0, empty_streak - 1)))


def yield_weight(created: int, searches: int) -> float:
    """Leads per search, blended with a prior so one lucky search does not dominate."""
    return (created + PRIOR_LEADS_PER_SEARCH * PRIOR_WEIGHT) / (searches + PRIOR_WEIGHT)


def pick_cells(
    candidates: list[CellKey],
    states: dict[tuple[str, str, str], MarketCell],
    *,
    settings: Settings,
    created_today_by_country: Counter[str],
    created_today_by_category: Counter[str],
    daily_limit: int,
    count: int,
    now: datetime,
    rng: random.Random,
    learning: LearningState = NEUTRAL,
) -> list[CellKey]:
    """Choose up to ``count`` cells. Weighted by yield, contactability and today's balance."""
    eligible = [
        c
        for c in candidates
        if not (states.get(c.tuple) and states[c.tuple].next_eligible_at and states[c.tuple].next_eligible_at > now)
    ]
    if not eligible:
        return []

    # Category and country yield, from every cell of that category or country.
    cat_stats: dict[str, tuple[int, int]] = {}
    country_stats: dict[str, tuple[int, int]] = {}
    for state in states.values():
        for table, key in ((cat_stats, state.category), (country_stats, state.country)):
            created, searches = table.get(key, (0, 0))
            table[key] = (created + (state.created or 0), searches + (state.searches or 0))

    cells_per_country = Counter(c.country for c in eligible)

    def weight(cell: CellKey) -> float:
        cat = yield_weight(*cat_stats.get(cell.category, (0, 0)))
        country = yield_weight(*country_stats.get(cell.country, (0, 0)))
        share_country = created_today_by_country[cell.country] / max(1, daily_limit)
        share_category = created_today_by_category[cell.category] / max(1, daily_limit)
        balance = 1.0 / ((1.0 + 3.0 * share_country) * (1.0 + 3.0 * share_category))
        # Dividing by the number of cities keeps a country with many cities from
        # crowding out one with few.
        fair_share = 1.0 / cells_per_country[cell.country]
        return max(
            0.001,
            math.sqrt(cat * country)
            * contact_weight(settings, cell.country)
            * balance
            * fair_share
            * learning.market(category_label(cell.category), cell.country),
        )

    chosen: list[CellKey] = []
    pool = list(eligible)
    while pool and len(chosen) < count:
        unexplored = [
            c for c in pool if c.tuple not in states or not (states[c.tuple].searches or 0)
        ]
        if unexplored and rng.random() < EXPLORE_SHARE:
            pick = rng.choice(unexplored)
        else:
            weights = [weight(c) for c in pool]
            pick = rng.choices(pool, weights=weights, k=1)[0]
        chosen.append(pick)
        pool = [c for c in pool if c.country != pick.country or c.category != pick.category]
    return chosen


# ----------------------------------------------------------------------- bookkeeping


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def created_today(session: Session, now: datetime | None = None) -> tuple[int, Counter[str], Counter[str]]:
    start = _day_start(now or datetime.now(UTC))
    rows = session.execute(
        select(Lead.country, Lead.industry)
        .where(Lead.created_at >= start, Lead.source.in_(DISCOVERED_SOURCES))
    ).all()
    by_country: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    labels = {category_label(c.value).casefold(): c.value for c in CATEGORIES}
    for country, industry in rows:
        by_country[country or ""] += 1
        by_category[labels.get((industry or "").casefold(), (industry or "").casefold())] += 1
    return len(rows), by_country, by_category


def remaining_quota(session: Session, config: AutomationConfig, now: datetime | None = None) -> int:
    done, _, _ = created_today(session, now)
    return max(0, config.discovery_daily_limit - done)


def rejections_today(session: Session, now: datetime | None = None) -> dict[str, int]:
    start = _day_start(now or datetime.now(UTC))
    rows = session.execute(
        select(DiscoveryRejection.reason, func.count())
        .where(DiscoveryRejection.created_at >= start)
        .group_by(DiscoveryRejection.reason)
    ).all()
    return {reason: int(count) for reason, count in rows}


def _known(session: Session, source_key: str) -> bool:
    if session.scalar(select(Lead.id).where(Lead.source_key == source_key).limit(1)) is not None:
        return True
    return (
        session.scalar(
            select(DiscoveryRejection.id).where(DiscoveryRejection.source_key == source_key).limit(1)
        )
        is not None
    )


def _store_rejection(session: Session, business: FoundBusiness, reason: str) -> None:
    session.add(
        DiscoveryRejection(
            source_key=business.source_key,
            name=business.name,
            category=business.industry,
            city=business.city,
            country=business.country,
            source=business.source,
            reason=reason,
            score=business.lead_score,
        )
    )


def _cell_state(session: Session, cell: CellKey) -> MarketCell:
    state = session.scalar(
        select(MarketCell).where(
            MarketCell.category == cell.category,
            MarketCell.country == cell.country,
            MarketCell.city == cell.city,
        )
    )
    if state is None:
        state = MarketCell(category=cell.category, country=cell.country, city=cell.city)
        session.add(state)
        session.flush()
    return state


# ------------------------------------------------------------------------- the slice


def run_discovery_slice(
    session_factory: sessionmaker[Session],
    settings: Settings,
    config: AutomationConfig,
    *,
    max_cells: int = 2,
    time_budget_seconds: float = 70.0,
    rng: random.Random | None = None,
    collector: Collector = collect_places,
    now: datetime | None = None,
) -> SliceSummary:
    from app.services.discovery import _save_one

    summary = SliceSummary()
    rng = rng or random.Random()
    started = time.monotonic()
    clock = now or datetime.now(UTC)

    if not settings.discovery_enabled or config.discovery_daily_limit <= 0:
        summary.stopped_because = "discovery is off"
        return summary

    with session_factory() as session:
        summary.quota_remaining = remaining_quota(session, config, clock)
        if summary.quota_remaining <= 0:
            summary.stopped_because = "daily quota reached"
            return summary
        _done, by_country, by_category = created_today(session, clock)
        learning = load_state(session, config)
        states = {
            (s.category, s.country, s.city): s for s in session.scalars(select(MarketCell))
        }
        picks = pick_cells(
            candidate_cells(config),
            states,
            settings=settings,
            created_today_by_country=by_country,
            created_today_by_category=by_category,
            daily_limit=config.discovery_daily_limit,
            count=max_cells,
            now=clock,
            rng=rng,
            learning=learning,
        )
    if not picks:
        summary.stopped_because = "every market is resting"
        return summary

    with httpx.Client(timeout=35.0, follow_redirects=True) as client:
        for index, cell in enumerate(picks):
            if summary.quota_remaining <= 0:
                summary.stopped_because = "daily quota reached"
                break
            if index and time.monotonic() - started > time_budget_seconds:
                summary.stopped_because = "time budget used"
                break
            _search_cell(
                session_factory, settings, config, client, cell, summary, collector, _save_one, clock
            )
    if not summary.stopped_because:
        summary.stopped_because = "slice finished"
    return summary


def _search_cell(
    session_factory: sessionmaker[Session],
    settings: Settings,
    config: AutomationConfig,
    client: httpx.Client,
    cell: CellKey,
    summary: SliceSummary,
    collector: Collector,
    save_one: Callable[[Session, FoundBusiness], str],
    now: datetime,
) -> None:
    flags = {flag: name in cell.sources for name, flag in SOURCE_FLAGS.items()}
    label = f"{category_label(cell.category)} in {cell.city}, {cell.country}"
    found: list[FoundBusiness] = []
    error: str | None = None
    try:
        found, _notes = collector(
            category=cell.category,
            city=cell.city,
            country=cell.country,
            settings=settings,
            client=client,
            **flags,
        )
    except PlaceSourceError as exc:
        error = exc.message
    except Exception:
        logger.exception("discovery_cell_failed cell=%s", label)
        error = "The search stopped because of an unexpected error."

    created = rejected = 0
    with session_factory() as session:
        state = _cell_state(session, cell)
        if error:
            state.last_error = error[:500]
            state.next_eligible_at = now + timedelta(days=1)
            session.commit()
            summary.errors.append(f"{label}: {error}")
            return

        exclusions = ExclusionSet.load(session)
        # Best opportunities first, so a small quota goes to the strongest leads.
        for business in sorted(found, key=lambda b: b.lead_score, reverse=True):
            if _known(session, business.source_key):
                summary.duplicates += 1
                continue
            reason = reject_reason(business, config, exclusions)
            if reason:
                _store_rejection(session, business, reason)
                rejected += 1
                summary.rejected[reason] = summary.rejected.get(reason, 0) + 1
                continue
            if summary.quota_remaining <= 0:
                continue  # kept for another day, not rejected
            session.commit()
            outcome = save_one(session, business)
            if outcome == "created":
                created += 1
                summary.created += 1
                summary.quota_remaining -= 1
            else:
                summary.duplicates += 1

        state = _cell_state(session, cell)
        state.searches += 1
        state.found += len(found)
        state.created += created
        state.rejected += rejected
        state.empty_streak = 0 if created else state.empty_streak + 1
        state.last_searched_at = now
        state.last_error = None
        state.next_eligible_at = now + timedelta(days=cooldown_days(state.empty_streak, bool(created)))
        session.commit()
    summary.cells_searched += 1
    summary.found += len(found)
    summary.searched.append(f"{label}: {created} new")
