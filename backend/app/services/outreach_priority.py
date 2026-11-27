"""Rank leads for outreach: who deserves one of today's few email slots.

The score favours businesses with a clear, provable problem, a ready mockup to show,
and a country where automatic outreach is allowed. It is then nudged by how that
category and country have actually performed for you, once enough emails were sent
to say anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.automation import OutreachAttempt
from app.models.contact import Contact
from app.models.enums import AuditStatus, MockupStatus, ResearchStatus
from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.mockup import Mockup
from app.models.website_audit import WebsiteAudit
from app.services.attempts import derive_strategy
from app.services.learning import LearningState, load_state
from app.services.outreach_policy import policy_for

SCORE_WEIGHT = 0.4
STRATEGY_POINTS = {"no_website": 25, "outdated": 20, "slow": 15, "ux": 10, "other": 0}
STRATEGY_LABELS = {
    "no_website": "No website",
    "outdated": "Outdated design",
    "slow": "Slow or poor on mobile",
    "ux": "Usability problems",
    "other": "General improvement",
}
MOCKUP_POINTS = 15
RESEARCH_POINTS = 5
NAMED_CONTACT_POINTS = 5
POLICY_POINTS = {"allow": 10, "manual": -10}
BLOCKED = -1000.0
MIN_SENDS_FOR_OVERALL = 20
PRIOR_SENDS = 20
FACTOR_RANGE = (0.8, 1.25)
POSITIVE_OUTCOMES = ("positive", "interested", "meeting", "won")


@dataclass
class Priority:
    score: float
    strategy: str
    reasons: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.score <= BLOCKED / 2


@dataclass
class MarketPerformance:
    """First-email results per (category, country), used to nudge the ranking."""

    overall_sent: int = 0
    overall_positive: int = 0
    by_market: dict[tuple[str, str], tuple[int, int]] = field(default_factory=dict)

    def factor(self, category: str | None, country: str | None) -> float:
        if self.overall_sent < MIN_SENDS_FOR_OVERALL or self.overall_positive == 0:
            return 1.0
        overall = self.overall_positive / self.overall_sent
        sent, positive = self.by_market.get(((category or "").casefold(), (country or "").casefold()), (0, 0))
        smoothed = (positive + PRIOR_SENDS * overall) / (sent + PRIOR_SENDS)
        low, high = FACTOR_RANGE
        return max(low, min(high, smoothed / overall))


def market_performance(session: Session) -> MarketPerformance:
    rows = session.execute(
        select(
            OutreachAttempt.category,
            OutreachAttempt.country,
            func.count(),
            func.count().filter(OutreachAttempt.outcome.in_(POSITIVE_OUTCOMES)),
        )
        .where(OutreachAttempt.kind == "first")
        .group_by(OutreachAttempt.category, OutreachAttempt.country)
    ).all()
    perf = MarketPerformance()
    for category, country, sent, positive in rows:
        perf.overall_sent += int(sent)
        perf.overall_positive += int(positive)
        perf.by_market[((category or "").casefold(), (country or "").casefold())] = (
            int(sent),
            int(positive),
        )
    return perf


def _clamp_factor(value: float) -> float:
    return max(0.5, min(2.0, value))


def score_lead(
    lead: Lead,
    *,
    audit: WebsiteAudit | None,
    has_mockup: bool,
    has_research: bool,
    has_named_contact: bool,
    settings: Settings,
    performance: MarketPerformance | None = None,
    learning: LearningState | None = None,
) -> Priority:
    strategy = derive_strategy(lead, audit)
    reasons: list[str] = []
    total = SCORE_WEIGHT * (lead.lead_score or 0)
    reasons.append(f"Lead score {lead.lead_score or 0}")

    points = STRATEGY_POINTS[strategy]
    if points:
        total += points
        reasons.append(f"{STRATEGY_LABELS[strategy]} (+{points})")
    if has_mockup:
        total += MOCKUP_POINTS
        reasons.append(f"Mockup ready (+{MOCKUP_POINTS})")
    if has_research:
        total += RESEARCH_POINTS
        reasons.append(f"Researched (+{RESEARCH_POINTS})")
    if has_named_contact:
        total += NAMED_CONTACT_POINTS
        reasons.append(f"Known contact name (+{NAMED_CONTACT_POINTS})")

    policy = policy_for(lead, settings)
    if policy == "block":
        return Priority(score=BLOCKED, strategy=strategy, reasons=["Country is blocked"])
    adjustment = POLICY_POINTS.get(policy, 0)
    total += adjustment
    reasons.append(
        f"Automatic sending allowed (+{adjustment})"
        if adjustment > 0
        else f"Manual-only country ({adjustment})"
    )

    if learning is not None and (lead.country or "").strip().casefold() in learning.avoid_countries:
        return Priority(score=BLOCKED, strategy=strategy, reasons=["Country is on your avoid list"])
    if learning is not None:
        factor = _clamp_factor(
            learning.market(lead.industry, lead.country) * learning.factor("strategy", strategy)
        )
        if abs(factor - 1.0) > 0.01:
            total *= factor
            reasons.append(f"Learned from your results (x{factor:.2f})")
    elif performance is not None:
        factor = performance.factor(lead.industry, lead.country)
        if abs(factor - 1.0) > 0.01:
            total *= factor
            reasons.append(f"Past results in this market (x{factor:.2f})")
    return Priority(score=round(total, 1), strategy=strategy, reasons=reasons)


def rank_leads(
    session: Session, settings: Settings, lead_ids: list[UUID]
) -> dict[UUID, Priority]:
    """Priority for many leads with a handful of queries."""
    if not lead_ids:
        return {}
    leads = {lead.id: lead for lead in session.scalars(select(Lead).where(Lead.id.in_(lead_ids)))}

    audits: dict[UUID, WebsiteAudit] = {}
    for audit in session.scalars(
        select(WebsiteAudit)
        .where(
            WebsiteAudit.lead_id.in_(lead_ids),
            WebsiteAudit.status == AuditStatus.COMPLETED.value,
        )
        .order_by(WebsiteAudit.created_at.desc())
    ):
        audits.setdefault(audit.lead_id, audit)
    mockups = set(
        session.scalars(
            select(Mockup.lead_id).where(
                Mockup.lead_id.in_(lead_ids), Mockup.status == MockupStatus.READY.value
            )
        )
    )
    researched = set(
        session.scalars(
            select(LeadResearch.lead_id).where(
                LeadResearch.lead_id.in_(lead_ids),
                LeadResearch.status == ResearchStatus.COMPLETED.value,
            )
        )
    )
    named = set(
        session.scalars(
            select(Contact.lead_id).where(
                Contact.lead_id.in_(lead_ids), Contact.name.is_not(None)
            )
        )
    )
    learning = load_state(session)
    return {
        lead_id: score_lead(
            lead,
            audit=audits.get(lead_id),
            has_mockup=lead_id in mockups,
            has_research=lead_id in researched,
            has_named_contact=lead_id in named,
            settings=settings,
            learning=learning,
        )
        for lead_id, lead in leads.items()
    }
