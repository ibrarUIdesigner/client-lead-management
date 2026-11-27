"""Numbers behind the Performance & Insights page and the daily email report.

Every figure comes from records the system already keeps: leads, rejections, audits,
mockups, sent emails (``outreach_attempts``), inbound mail and status changes. Nothing is
estimated except "delivered", which is sent minus bounces (Gmail gives no delivery receipts).

Rates are per first email sent, and markets are ranked by a smoothed positive-reply rate
so a small sample cannot top the table.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, literal_column, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.activity import Activity
from app.models.automation import OutreachAttempt
from app.models.enums import AttemptOutcome, AuditStatus, EmailClassification, EmailDirection, MockupStatus
from app.models.followup import Followup
from app.models.gmail import LeadEmail
from app.models.lead import Lead
from app.models.market import DiscoveryRejection
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.models.website_audit import WebsiteAudit
from app.services.automation_config import AutomationConfig
from app.services.discovery_engine import DISCOVERED_SOURCES

REPLY_OUTCOMES = ("reply", "negative", "positive", "interested", "meeting", "won")
POSITIVE_OUTCOMES = ("positive", "interested", "meeting", "won")
INTERESTED_OUTCOMES = ("interested", "meeting", "won")
MIN_SENDS_TO_JUDGE = 15
PRIOR_SENDS = 20
REJECTION_LABELS = {
    "excluded": "on your do-not-contact list",
    "chain": "national chains",
    "no_contact": "no way to contact them",
    "not_preferred": "not a preferred opportunity",
    "low_score": "below the score threshold",
}


def zone_for(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def local_day_start(now: datetime, tz: str) -> datetime:
    local = now.astimezone(zone_for(tz))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def _rate(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def smoothed(positive: int, sent: int, overall_rate: float) -> float:
    """Positive-reply rate pulled toward the overall rate when there is little data."""
    return (positive + PRIOR_SENDS * overall_rate) / (sent + PRIOR_SENDS)


# ------------------------------------------------------------------ activity window


def activity(session: Session, start: datetime, end: datetime) -> dict[str, Any]:
    """What happened between two moments."""

    def count(statement: Any) -> int:
        return int(session.scalar(statement) or 0)

    def attempts(*conditions: Any) -> int:
        return count(select(func.count()).select_from(OutreachAttempt).where(*conditions))

    def status_changes(target: str) -> int:
        return count(
            select(func.count())
            .select_from(Activity)
            .where(
                Activity.type == "status_changed",
                Activity.created_at >= start,
                Activity.created_at < end,
                Activity.details["to"].as_string() == target,
            )
        )

    sent_window = (OutreachAttempt.sent_at >= start, OutreachAttempt.sent_at < end)
    outcome_window = (OutreachAttempt.outcome_at >= start, OutreachAttempt.outcome_at < end)
    first = attempts(OutreachAttempt.kind == "first", *sent_window)
    followups = attempts(OutreachAttempt.kind == "followup", *sent_window)
    bounces = attempts(OutreachAttempt.outcome == "bounce", *outcome_window)
    unsubscribes = attempts(OutreachAttempt.outcome == "unsubscribe", *outcome_window)
    discovered = count(
        select(func.count())
        .select_from(Lead)
        .where(Lead.created_at >= start, Lead.created_at < end, Lead.source.in_(DISCOVERED_SOURCES))
    )
    return {
        "leads_discovered": discovered,
        "leads_rejected": count(
            select(func.count())
            .select_from(DiscoveryRejection)
            .where(DiscoveryRejection.created_at >= start, DiscoveryRejection.created_at < end)
        ),
        "leads_qualified": status_changes("QUALIFIED"),
        "audits_completed": count(
            select(func.count())
            .select_from(WebsiteAudit)
            .where(
                WebsiteAudit.status == AuditStatus.COMPLETED.value,
                WebsiteAudit.completed_at >= start,
                WebsiteAudit.completed_at < end,
            )
        ),
        "mockups_generated": count(
            select(func.count())
            .select_from(Mockup)
            .where(
                Mockup.status == MockupStatus.READY.value,
                Mockup.completed_at >= start,
                Mockup.completed_at < end,
            )
        ),
        "emails_sent": first + followups,
        "first_emails": first,
        "followups_sent": followups,
        "delivered_estimate": max(0, first + followups - bounces),
        "replies": count(
            select(func.count())
            .select_from(LeadEmail)
            .where(
                LeadEmail.direction == EmailDirection.INBOUND.value,
                LeadEmail.classification == EmailClassification.HUMAN_REPLY.value,
                LeadEmail.occurred_at >= start,
                LeadEmail.occurred_at < end,
            )
        ),
        "positive_replies": attempts(OutreachAttempt.outcome.in_(POSITIVE_OUTCOMES), *outcome_window),
        "interested": attempts(OutreachAttempt.outcome.in_(INTERESTED_OUTCOMES), *outcome_window),
        "meetings": status_changes("MEETING") + status_changes("PROPOSAL"),
        "bounces": bounces,
        "unsubscribes": unsubscribes,
        "clients_won": status_changes("WON"),
    }


def discovery_breakdown(session: Session, start: datetime, end: datetime) -> dict[str, Any]:
    rows = session.execute(
        select(Lead.country, Lead.industry, Lead.website_url, Lead.website_status, Lead.lead_status)
        .where(Lead.created_at >= start, Lead.created_at < end, Lead.source.in_(DISCOVERED_SOURCES))
    ).all()
    by_country: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    no_site = 0
    for country, industry, url, status, _lead_status in rows:
        by_country[country or "Unknown"] += 1
        by_category[industry or "Unknown"] += 1
        if not url or status in ("missing", "social_only"):
            no_site += 1
    rejected = session.execute(
        select(DiscoveryRejection.reason, func.count())
        .where(DiscoveryRejection.created_at >= start, DiscoveryRejection.created_at < end)
        .group_by(DiscoveryRejection.reason)
    ).all()
    return {
        "total": len(rows),
        "by_country": _top(by_country),
        "by_category": _top(by_category),
        "no_website": no_site,
        "with_opportunity": len(rows) - no_site,
        "rejected_by_reason": {reason: int(n) for reason, n in rejected},
    }


def _top(values: dict[str, int], limit: int = 10) -> list[dict[str, Any]]:
    ordered = sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [{"label": label, "count": count} for label, count in ordered]


# ----------------------------------------------------------------------- time series


def daily_series(session: Session, tz: str, days: int, now: datetime) -> list[dict[str, Any]]:
    """One row per local day, oldest first, with zeros for quiet days."""
    zone = zone_for(tz)
    today = now.astimezone(zone).date()
    first_day = today - timedelta(days=days - 1)
    start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=zone).astimezone(UTC)

    def day(column: Any) -> Any:
        return cast(func.timezone(tz if zone.key == tz else "UTC", column), Date)

    def grouped(statement: Any) -> dict[date, int]:
        return {d: int(n) for d, n in session.execute(statement)}

    discovered = grouped(
        select(day(Lead.created_at), func.count())
        .where(Lead.created_at >= start, Lead.source.in_(DISCOVERED_SOURCES))
        .group_by(literal_column("1"))
    )
    first = grouped(
        select(day(OutreachAttempt.sent_at), func.count())
        .where(OutreachAttempt.sent_at >= start, OutreachAttempt.kind == "first")
        .group_by(literal_column("1"))
    )
    followups = grouped(
        select(day(OutreachAttempt.sent_at), func.count())
        .where(OutreachAttempt.sent_at >= start, OutreachAttempt.kind == "followup")
        .group_by(literal_column("1"))
    )
    replies = grouped(
        select(day(LeadEmail.occurred_at), func.count())
        .where(
            LeadEmail.occurred_at >= start,
            LeadEmail.direction == EmailDirection.INBOUND.value,
            LeadEmail.classification == EmailClassification.HUMAN_REPLY.value,
        )
        .group_by(literal_column("1"))
    )
    positive = grouped(
        select(day(OutreachAttempt.outcome_at), func.count())
        .where(OutreachAttempt.outcome_at >= start, OutreachAttempt.outcome.in_(POSITIVE_OUTCOMES))
        .group_by(literal_column("1"))
    )
    won = grouped(
        select(day(Activity.created_at), func.count())
        .where(
            Activity.created_at >= start,
            Activity.type == "status_changed",
            Activity.details["to"].as_string() == "WON",
        )
        .group_by(literal_column("1"))
    )
    series = []
    for offset in range(days):
        current = first_day + timedelta(days=offset)
        series.append(
            {
                "date": current.isoformat(),
                "discovered": discovered.get(current, 0),
                "sent": first.get(current, 0),
                "followups": followups.get(current, 0),
                "replies": replies.get(current, 0),
                "positive": positive.get(current, 0),
                "clients": won.get(current, 0),
            }
        )
    return series


_SUM_KEYS = ("discovered", "sent", "followups", "replies", "positive", "clients")


def rollup(series: list[dict[str, Any]], period: str) -> list[dict[str, Any]]:
    """Weekly (Monday start) or monthly totals from the daily rows."""
    buckets: dict[str, dict[str, Any]] = {}
    for row in series:
        current = date.fromisoformat(row["date"])
        if period == "week":
            key = (current - timedelta(days=current.weekday())).isoformat()
        else:
            key = current.replace(day=1).isoformat()
        bucket = buckets.setdefault(key, {"date": key, **{k: 0 for k in _SUM_KEYS}})
        for name in _SUM_KEYS:
            bucket[name] += row[name]
    return [buckets[key] for key in sorted(buckets)]


# ---------------------------------------------------------------- markets and angles


@dataclass
class _Totals:
    sent: int = 0
    replies: int = 0
    positive: int = 0
    won: int = 0


def _cohort(session: Session, column: Any) -> dict[str, _Totals]:
    rows = session.execute(
        select(
            column,
            func.count(),
            func.count().filter(OutreachAttempt.outcome.in_(REPLY_OUTCOMES)),
            func.count().filter(OutreachAttempt.outcome.in_(POSITIVE_OUTCOMES)),
            func.count().filter(OutreachAttempt.outcome == AttemptOutcome.WON.value),
        )
        .where(OutreachAttempt.kind == "first")
        .group_by(column)
    ).all()
    return {
        (key or "Unknown"): _Totals(int(sent), int(replies), int(positive), int(won))
        for key, sent, replies, positive, won in rows
    }


def _overall(session: Session) -> _Totals:
    row = session.execute(
        select(
            func.count(),
            func.count().filter(OutreachAttempt.outcome.in_(REPLY_OUTCOMES)),
            func.count().filter(OutreachAttempt.outcome.in_(POSITIVE_OUTCOMES)),
            func.count().filter(OutreachAttempt.outcome == AttemptOutcome.WON.value),
        ).where(OutreachAttempt.kind == "first")
    ).one()
    return _Totals(*(int(v or 0) for v in row))


def market_table(session: Session, by: str) -> list[dict[str, Any]]:
    """Categories or countries, best quality first."""
    attempt_col = OutreachAttempt.category if by == "category" else OutreachAttempt.country
    lead_col = Lead.industry if by == "category" else Lead.country
    cohort = _cohort(session, attempt_col)
    overall = _overall(session)
    overall_rate = overall.positive / overall.sent if overall.sent else 0.0

    qualified = {
        (key or "Unknown"): int(n)
        for key, n in session.execute(
            select(lead_col, func.count()).where(Lead.source.in_(DISCOVERED_SOURCES)).group_by(lead_col)
        )
    }
    revenue = {
        (key or "Unknown"): float(total or 0)
        for key, total in session.execute(
            select(lead_col, func.sum(Lead.deal_value)).where(Lead.lead_status == "WON").group_by(lead_col)
        )
    }
    keys = set(cohort) | set(qualified)
    rows = []
    for key in keys:
        totals = cohort.get(key, _Totals())
        rows.append(
            {
                "label": key,
                "qualified_leads": qualified.get(key, 0),
                "sent": totals.sent,
                "reply_rate": _rate(totals.replies, totals.sent),
                "positive_rate": _rate(totals.positive, totals.sent),
                "positive": totals.positive,
                "clients": totals.won,
                "conversion_rate": _rate(totals.won, totals.sent),
                "revenue": revenue.get(key, 0.0),
                "enough_data": totals.sent >= MIN_SENDS_TO_JUDGE,
                "score": round(100 * smoothed(totals.positive, totals.sent, overall_rate), 2),
            }
        )
    # Markets with enough emails to judge always rank above thin ones.
    rows.sort(
        key=lambda r: (r["enough_data"], r["score"], r["clients"], r["qualified_leads"]),
        reverse=True,
    )
    return rows


def strategy_table(session: Session) -> list[dict[str, Any]]:
    cohort = _cohort(session, OutreachAttempt.strategy)
    return [
        {
            "label": key,
            "sent": t.sent,
            "reply_rate": _rate(t.replies, t.sent),
            "positive_rate": _rate(t.positive, t.sent),
            "clients": t.won,
            "enough_data": t.sent >= MIN_SENDS_TO_JUDGE,
        }
        for key, t in sorted(cohort.items(), key=lambda kv: kv[1].sent, reverse=True)
    ]


def variant_table(session: Session) -> list[dict[str, Any]]:
    cohort = _cohort(session, OutreachAttempt.framework)
    return [
        {
            "label": key,
            "sent": t.sent,
            "reply_rate": _rate(t.replies, t.sent),
            "positive_rate": _rate(t.positive, t.sent),
            "enough_data": t.sent >= MIN_SENDS_TO_JUDGE,
        }
        for key, t in sorted(cohort.items(), key=lambda kv: kv[1].sent, reverse=True)
        if key != "Unknown"
    ][:12]


def mockup_effect(session: Session) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, flag in (("with_mockup", True), ("without_mockup", False)):
        row = session.execute(
            select(
                func.count(),
                func.count().filter(OutreachAttempt.outcome.in_(REPLY_OUTCOMES)),
                func.count().filter(OutreachAttempt.outcome.in_(POSITIVE_OUTCOMES)),
            ).where(OutreachAttempt.kind == "first", OutreachAttempt.mockup_included.is_(flag))
        ).one()
        sent, replies, positive = (int(v or 0) for v in row)
        result[label] = {
            "sent": sent,
            "reply_rate": _rate(replies, sent),
            "positive_rate": _rate(positive, sent),
            "enough_data": sent >= MIN_SENDS_TO_JUDGE,
        }
    return result


# ----------------------------------------------------------------- funnel and leads


def funnel(session: Session) -> dict[str, int]:
    overall = _overall(session)
    won = int(session.scalar(select(func.count()).select_from(Lead).where(Lead.lead_status == "WON")) or 0)
    total_leads = int(session.scalar(select(func.count()).select_from(Lead)) or 0)
    return {
        "leads": total_leads,
        "emailed": overall.sent,
        "replied": overall.replies,
        "positive": overall.positive,
        "clients": won,
    }


def offer_types(session: Session, limit: int = 8) -> list[dict[str, Any]]:
    """For each category: how a new-website offer compares with a redesign offer."""
    rows = session.execute(
        select(
            OutreachAttempt.category,
            OutreachAttempt.strategy,
            func.count(),
            func.count().filter(OutreachAttempt.outcome.in_(POSITIVE_OUTCOMES)),
        )
        .where(OutreachAttempt.kind == "first")
        .group_by(OutreachAttempt.category, OutreachAttempt.strategy)
    ).all()
    table: dict[str, dict[str, Any]] = {}
    for category, strategy, sent, positive in rows:
        new_site = strategy == "no_website"
        entry = table.setdefault(
            category or "Unknown",
            {"label": category or "Unknown", "new_site": [0, 0], "redesign": [0, 0]},
        )
        bucket = entry["new_site" if new_site else "redesign"]
        bucket[0] += int(sent)
        bucket[1] += int(positive)
    result = []
    for entry in table.values():
        (ns_sent, ns_pos), (rd_sent, rd_pos) = entry["new_site"], entry["redesign"]
        result.append(
            {
                "label": entry["label"],
                "new_site": {
                    "sent": ns_sent,
                    "positive_rate": _rate(ns_pos, ns_sent),
                    "enough_data": ns_sent >= MIN_SENDS_TO_JUDGE,
                },
                "redesign": {
                    "sent": rd_sent,
                    "positive_rate": _rate(rd_pos, rd_sent),
                    "enough_data": rd_sent >= MIN_SENDS_TO_JUDGE,
                },
            }
        )
    result.sort(key=lambda r: r["new_site"]["sent"] + r["redesign"]["sent"], reverse=True)
    return result[:limit]


def explore_suggestions(
    session: Session, settings: Settings, config: AutomationConfig, limit: int = 4
) -> list[dict[str, str]]:
    """Categories and countries worth trying next, with an honest reason for each."""
    from app.models.market import MarketCell
    from app.services.discovery_markets import ANYWHERE_MARKETS
    from app.services.outreach_policy import country_code, policy_table
    from app.services.place_listings import CATEGORIES, category_label

    searched = session.execute(
        select(MarketCell.category, MarketCell.country).where(MarketCell.searches > 0)
    ).all()
    searched_categories = {category_label(c).casefold() for c, _ in searched}
    searched_countries = {country.casefold() for _, country in searched}
    emailed = session.execute(
        select(OutreachAttempt.category, OutreachAttempt.country).where(OutreachAttempt.kind == "first")
    ).all()
    searched_categories |= {(c or "").casefold() for c, _ in emailed}
    searched_countries |= {(n or "").casefold() for _, n in emailed}
    avoid = {c.casefold() for c in config.excluded_countries}

    ideas: list[dict[str, str]] = []
    for table, kind in ((market_table(session, "category"), "category"), (market_table(session, "country"), "country")):
        for row in table:
            if 3 <= row["sent"] < MIN_SENDS_TO_JUDGE and row["positive"] >= 1:
                ideas.append(
                    {
                        "kind": kind,
                        "name": row["label"],
                        "reason": f"Early signs: {row['positive']} positive of {row['sent']} emails. Needs about {MIN_SENDS_TO_JUDGE} to be sure.",
                    }
                )
    # Until there is real data, almost everything is "untried", which says nothing useful.
    if _overall(session).sent < 30:
        return ideas[:limit]
    for category in CATEGORIES:
        if category_label(category.value).casefold() not in searched_categories:
            ideas.append({"kind": "category", "name": category.label, "reason": "Not tried yet."})
    seen_countries: set[str] = set()
    for market in ANYWHERE_MARKETS:
        name = market.country
        if name.casefold() in searched_countries or name.casefold() in avoid or name in seen_countries:
            continue
        seen_countries.add(name)
        policy = policy_table(settings).get(country_code(name) or "", "manual")
        note = (
            "Automatic outreach is allowed there."
            if policy == "allow"
            else "You would send those emails by hand."
        )
        ideas.append({"kind": "country", "name": name, "reason": f"Not tried yet. {note}"})
    # Early signs first, then untried categories, then untried countries.
    return ideas[:limit]


def promising_leads(session: Session, limit: int = 5) -> list[dict[str, Any]]:
    """Prospects who showed interest or wrote back, most advanced first."""
    rows = session.execute(
        select(Lead, OutreachAttempt.outcome)
        .join(OutreachAttempt, OutreachAttempt.lead_id == Lead.id)
        .where(
            OutreachAttempt.outcome.in_(("positive", "interested", "meeting")),
            Lead.lead_status.notin_(("WON", "LOST", "NOT_INTERESTED", "DO_NOT_CONTACT")),
        )
        .order_by(OutreachAttempt.outcome_at.desc())
        .limit(30)
    ).all()
    rank = {"meeting": 3, "interested": 2, "positive": 1}
    seen: dict[Any, dict[str, Any]] = {}
    for lead, outcome in rows:
        entry = seen.get(lead.id)
        if entry is None or rank[outcome] > rank[entry["outcome"]]:
            seen[lead.id] = {
                "lead_id": str(lead.id),
                "business_name": lead.business_name,
                "country": lead.country,
                "category": lead.industry,
                "outcome": outcome,
                "unread": bool(lead.email_unread),
            }
    ordered = sorted(seen.values(), key=lambda e: (rank[e["outcome"]], e["unread"]), reverse=True)
    return ordered[:limit]


# ------------------------------------------------------------------ recommendations


def recommendations(data: dict[str, Any], config: AutomationConfig) -> list[str]:
    """Plain-language next steps from the numbers. Only says what the data supports."""
    tips: list[str] = []
    overall = data["funnel"]
    waiting = data.get("waiting", {})

    if waiting.get("interested"):
        n = waiting["interested"]
        tips.append(
            f"Reply to {n} interested {'prospect' if n == 1 else 'prospects'} first. They are warm and cost nothing to follow up."
        )
    if waiting.get("drafts"):
        n = waiting["drafts"]
        tips.append(f"{n} {'draft is' if n == 1 else 'drafts are'} waiting for your approval.")
    if waiting.get("followups_due"):
        n = waiting["followups_due"]
        tips.append(f"{n} {'follow-up is' if n == 1 else 'follow-ups are'} due. They send automatically if switched on.")

    discovery = data["discovery"]
    if config.discovery_daily_limit and discovery["total"] < config.discovery_daily_limit * 0.5:
        reasons = discovery["rejected_by_reason"]
        if reasons:
            top = max(reasons, key=lambda k: reasons[k])
            tips.append(
                f"Discovery found {discovery['total']} of {config.discovery_daily_limit} leads. "
                f"The most common reason for leaving businesses out was {REJECTION_LABELS.get(top, top)}. "
                "Widening your countries or categories would help."
            )
        else:
            tips.append(
                f"Discovery found {discovery['total']} of {config.discovery_daily_limit} leads. "
                "Add more countries or categories, or connect another listing source."
            )

    sent_total = overall["emailed"]
    overall_rate = overall["positive"] / sent_total if sent_total else 0.0
    for table, kind in ((data["categories"], "category"), (data["countries"], "country")):
        judged = [r for r in table if r["enough_data"]]
        if overall_rate > 0 and judged:
            best = judged[0]
            if best["positive_rate"] > 100 * overall_rate * 1.3 and best["positive"] >= 2:
                tips.append(
                    f"{best['label']} is your strongest {kind}: {best['positive_rate']}% positive replies "
                    f"against {round(100 * overall_rate, 1)}% overall. It gets more of the daily slots as results build up."
                )
        for row in judged:
            if row["sent"] >= 30 and row["positive"] == 0:
                tips.append(
                    f"{row['label']} ({kind}) has had {row['sent']} emails and no positive replies. "
                    "Consider excluding it or trying a different angle."
                )

    effect = data["mockup_effect"]
    with_m, without_m = effect["with_mockup"], effect["without_mockup"]
    if with_m["enough_data"] and without_m["enough_data"] and with_m["positive_rate"] != without_m["positive_rate"]:
        better = "with" if with_m["positive_rate"] > without_m["positive_rate"] else "without"
        tips.append(
            f"Emails {better} a mockup link get more positive replies "
            f"({with_m['positive_rate']}% with, {without_m['positive_rate']}% without)."
        )

    if sent_total == 0:
        tips.append(
            "No emails have been sent yet. Approve a few drafts, or switch to automatic mode once you trust the drafts, to start collecting results."
        )
    elif sent_total < 3 * MIN_SENDS_TO_JUDGE:
        tips.append(
            f"Only {sent_total} emails sent so far. Rankings by category and country firm up after about {MIN_SENDS_TO_JUDGE} emails each."
        )
    for idea in data.get("explore", [])[:2]:
        tips.append(f"Worth exploring: {idea['name']} ({idea['kind']}). {idea['reason']}")
    manual = data.get("manual_only_leads", 0)
    if manual:
        tips.append(
            f"{manual} qualified {'lead is' if manual == 1 else 'leads are'} in manual-only countries. Send those by hand, or allow the country in your policy."
        )
    return tips[:8]


# ----------------------------------------------------------------------- assemble


def build_insights(
    session: Session,
    settings: Settings,
    config: AutomationConfig,
    *,
    days: int = 90,
    now: datetime | None = None,
) -> dict[str, Any]:
    from app.services.outreach_policy import policy_for

    now = now or datetime.now(UTC)
    tz = config.report_timezone
    today_start = local_day_start(now, tz)
    series = daily_series(session, tz, days, now)

    interested = promising_leads(session, 10)
    drafts = int(
        session.scalar(
            select(func.count())
            .select_from(OutreachMessage)
            .where(OutreachMessage.status.in_(("DRAFT", "READY")))
        )
        or 0
    )
    followups_due = int(
        session.scalar(select(func.count()).select_from(Followup).where(Followup.status == "DUE")) or 0
    )
    manual_leads = 0
    for lead in session.scalars(
        select(Lead).where(Lead.source.in_(DISCOVERED_SOURCES), Lead.lead_status.in_(("NEW", "QUALIFIED"))).limit(500)
    ):
        if policy_for(lead, settings) != "allow":
            manual_leads += 1

    data: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "timezone": tz,
        "today": activity(session, today_start, now + timedelta(seconds=1)),
        "last_24h": activity(session, now - timedelta(hours=24), now + timedelta(seconds=1)),
        "discovery": discovery_breakdown(session, now - timedelta(hours=24), now + timedelta(seconds=1)),
        "daily": series,
        "weekly": rollup(series, "week"),
        "monthly": rollup(series, "month"),
        "funnel": funnel(session),
        "categories": market_table(session, "category"),
        "countries": market_table(session, "country"),
        "strategies": strategy_table(session),
        "variants": variant_table(session),
        "mockup_effect": mockup_effect(session),
        "promising": interested[:5],
        "waiting": {
            "interested": len(interested),
            "drafts": drafts,
            "followups_due": followups_due,
        },
        "manual_only_leads": manual_leads,
    }
    sent = data["funnel"]["emailed"]
    data["rates"] = {
        "reply_rate": _rate(data["funnel"]["replied"], sent),
        "positive_rate": _rate(data["funnel"]["positive"], sent),
        "conversion_rate": _rate(data["funnel"]["clients"], sent),
    }
    from app.services.learning import load_state, summary_for_ui

    data["offer_types"] = offer_types(session)
    data["explore"] = explore_suggestions(session, settings, config)
    data["learning"] = summary_for_ui(load_state(session, config))
    data["recommendations"] = recommendations(data, config)
    return data
