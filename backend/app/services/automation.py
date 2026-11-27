"""Automation switches, send safety checks, follow-up sequences and readiness checks.

Everything that can email a prospect on its own lives behind three switches that
default to OFF and that you flip from Settings:

  auto_send_enabled   first emails are sent automatically (after the quality gate)
  followups_auto_send Day 4 and Day 10 follow-ups are sent automatically
  breakup_auto_send   the Day 20 closing note is sent automatically too

Safety checks that always apply, with or without the switches: do-not-contact,
bounce suppression, country policy, daily cap, weekday send window, compliance
footer, and reply detection (a reply cancels pending follow-ups).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.app_setting import AppSetting
from app.models.contact import Contact
from app.models.enums import EmailDirection, FollowupStatus, LeadStatus
from app.models.followup import Followup
from app.models.gmail import LeadEmail
from app.models.lead import Lead
from app.repositories.activities import ActivityRepository
from app.schemas.gmail import LeadEmailReplyRequest
from app.services.automation_config import ExclusionSet
from app.services.outreach_policy import (
    can_auto_send,
    enforce_daily_cap,
    sent_today,
    with_compliance_footer,
)

logger = logging.getLogger(__name__)

KEY_FLAGS = "automation_flags"
KEY_TICK = "last_tick"
FLAG_DEFAULTS: dict[str, bool] = {
    "auto_send_enabled": False,
    "followups_auto_send": False,
    "breakup_auto_send": False,
}
SEQUENCE_DAYS = (4, 10, 20)
FOLLOWUPS_PER_TICK = 5
_PLACEHOLDER = re.compile(r"\{\{|\}\}|\[[A-Za-z][A-Za-z _/-]{1,30}\]|<[A-Za-z_ ]{2,30}>|lorem ipsum", re.I)


# ----------------------------------------------------------------------- switches


def get_flags(session: Session) -> dict[str, bool]:
    row = session.get(AppSetting, KEY_FLAGS)
    stored = row.value if row is not None and isinstance(row.value, dict) else {}
    return {key: bool(stored.get(key, default)) for key, default in FLAG_DEFAULTS.items()}


def set_flags(session: Session, updates: dict[str, bool]) -> dict[str, bool]:
    flags = get_flags(session)
    for key, value in updates.items():
        if key in FLAG_DEFAULTS:
            flags[key] = bool(value)
    row = session.get(AppSetting, KEY_FLAGS)
    if row is None:
        session.add(AppSetting(key=KEY_FLAGS, value=dict(flags)))
    else:
        row.value = dict(flags)
    session.flush()
    return flags


def record_tick(session: Session, summary: dict[str, Any]) -> None:
    payload = {"at": datetime.now(UTC).isoformat(), "summary": summary}
    row = session.get(AppSetting, KEY_TICK)
    if row is None:
        session.add(AppSetting(key=KEY_TICK, value=payload))
    else:
        row.value = payload
    session.flush()


def get_last_tick(session: Session) -> dict[str, Any] | None:
    row = session.get(AppSetting, KEY_TICK)
    return row.value if row is not None and isinstance(row.value, dict) else None


# ------------------------------------------------------------------ safety checks


def in_send_window(settings: Settings, now: datetime | None = None) -> bool:
    try:
        zone = ZoneInfo(settings.outreach_timezone)
    except Exception:
        zone = ZoneInfo("UTC")
    local = (now or datetime.now(UTC)).astimezone(zone)
    if local.weekday() >= 5:
        return False
    return settings.outreach_send_start_hour <= local.hour < settings.outreach_send_end_hour


def recent_outreach_bodies(session: Session, exclude_id: Any = None, limit: int = 30) -> list[str]:
    """The last drafts and sent emails, used to catch repetitive wording."""
    from app.models.outreach import OutreachMessage

    statement = (
        select(OutreachMessage.message)
        .where(OutreachMessage.message.is_not(None), OutreachMessage.status != "CANCELLED")
        .order_by(OutreachMessage.created_at.desc())
        .limit(limit)
    )
    if exclude_id is not None:
        statement = statement.where(OutreachMessage.id != exclude_id)
    return [row for row in session.scalars(statement) if row]


def check_draft_quality(
    subject: str | None,
    body: str | None,
    business_name: str,
    recent_bodies: list[str] | None = None,
) -> list[str]:
    """Reasons a draft must be reviewed by a person before it can go out on its own."""
    problems: list[str] = []
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject:
        problems.append("missing subject")
    elif len(subject) > 120:
        problems.append("subject is too long")
    if len(body) < 60:
        problems.append("message is too short")
    elif len(body) > 2500:
        problems.append("message is too long")
    if _PLACEHOLDER.search(subject) or _PLACEHOLDER.search(body):
        problems.append("contains an unfilled placeholder")
    if recent_bodies:
        from app.services.draft_similarity import SIMILAR_AT, most_similar

        if most_similar(body, recent_bodies) >= SIMILAR_AT:
            problems.append("reads too much like a recent email")
    first_word = business_name.split()[0].casefold() if business_name.strip() else ""
    if first_word and len(first_word) > 3 and first_word not in (subject + " " + body).casefold():
        problems.append("does not mention the business")
    return problems


def latest_outbound(session: Session, lead_id: Any) -> LeadEmail | None:
    return session.scalar(
        select(LeadEmail)
        .where(LeadEmail.lead_id == lead_id, LeadEmail.direction == EmailDirection.OUTBOUND.value)
        .order_by(LeadEmail.occurred_at.desc())
        .limit(1)
    )


def followups_sent_today(session: Session) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = session.scalar(
        select(func.count())
        .select_from(LeadEmail)
        .where(
            LeadEmail.direction == EmailDirection.OUTBOUND.value,
            LeadEmail.occurred_at >= start,
            LeadEmail.idempotency_key.like("followup:%"),
        )
    )
    return int(count or 0)


# --------------------------------------------------------------------- sequences


def schedule_followup_sequence(
    session: Session,
    lead: Lead,
    outreach_id: Any,
    sent_at: datetime | None = None,
    days: list[int] | None = None,
) -> int:
    """Create the follow-ups after a first email, using your configured intervals.

    Safe to call twice: nothing is added while follow-ups are still open.
    """
    if days is None:
        from app.services.automation_config import get_config

        days = get_config(session).sequence_days()
    if not days:
        return 0
    open_exists = session.scalar(
        select(func.count())
        .select_from(Followup)
        .where(
            Followup.lead_id == lead.id,
            Followup.status.in_([FollowupStatus.SCHEDULED.value, FollowupStatus.DUE.value]),
        )
    )
    if open_exists:
        return 0
    base = sent_at or datetime.now(UTC)
    rows = [
        Followup(
            lead_id=lead.id,
            outreach_id=outreach_id,
            scheduled_for=base + timedelta(days=day),
            type="email",
            status=FollowupStatus.SCHEDULED.value,
            notes=f"Automatic sequence: Day {day}",
        )
        for day in days
    ]
    session.add_all(rows)
    lead.next_followup_at = rows[0].scheduled_for
    session.flush()
    return len(rows)


def process_due_followups(session: Session, settings: Settings) -> dict[str, int]:
    """Send due follow-ups as replies in the original thread. Needs followups_auto_send."""
    from app.services.followups import FollowupService
    from app.services.gmail_mail import GmailMailService

    result = {"sent": 0, "waiting": 0, "skipped": 0}
    flags = get_flags(session)
    if not flags["followups_auto_send"]:
        return result
    if not in_send_window(settings):
        result["waiting"] = 1
        return result

    due = list(
        session.scalars(
            select(Followup)
            .where(Followup.status == FollowupStatus.DUE.value)
            .order_by(Followup.scheduled_for.asc())
            .limit(25)
        )
    )
    activities = ActivityRepository(session)
    exclusions = ExclusionSet.load(session)
    for followup in due:
        if result["sent"] >= FOLLOWUPS_PER_TICK:
            break
        if settings.followup_daily_limit and followups_sent_today(session) >= settings.followup_daily_limit:
            result["waiting"] += 1
            break
        if (followup.type or "email") != "email":
            continue
        lead = session.get(Lead, followup.lead_id)
        if lead is None or lead.lead_status not in {
            LeadStatus.CONTACTED.value,
            LeadStatus.FOLLOW_UP.value,
        }:
            result["skipped"] += 1
            continue
        allowed, _reason = can_auto_send(lead, settings)
        parent = latest_outbound(session, lead.id)
        if not allowed or parent is None or exclusions.match_lead(lead):
            result["skipped"] += 1
            continue
        try:
            enforce_daily_cap(session, settings)
            draft = FollowupService(session).generate_followup_draft(followup.id)
            if draft["sequence_step"] >= 3 and not flags["breakup_auto_send"]:
                result["skipped"] += 1
                continue
            body = with_compliance_footer(str(draft["body"]), settings)
            sent_reply = GmailMailService(session, settings).reply(
                lead.id,
                parent.id,
                LeadEmailReplyRequest(
                    body=body,
                    subject=str(draft["subject"]),
                    idempotency_key=f"followup:{followup.id}",
                ),
            )
            sent_row = session.get(LeadEmail, sent_reply.id)
            if sent_row is not None:
                from app.models.enums import AttemptKind
                from app.services.attempts import record_attempt

                record_attempt(
                    session,
                    lead,
                    sent_row,
                    kind=AttemptKind.FOLLOWUP,
                    sequence_step=int(draft["sequence_step"]),
                    automatic=True,
                )
            FollowupService(session).complete(followup.id)
            lead = session.get(Lead, followup.lead_id) or lead
            if lead.lead_status == LeadStatus.CONTACTED.value:
                lead.lead_status = LeadStatus.FOLLOW_UP.value
                activities.add(
                    lead.id,
                    "status_changed",
                    "Status changed",
                    description="CONTACTED to FOLLOW_UP (automatic follow-up sent)",
                    details={"from": "CONTACTED", "to": "FOLLOW_UP"},
                )
            session.commit()
            result["sent"] += 1
        except AppError as exc:
            session.rollback()
            logger.warning("followup_auto_send_blocked code=%s", exc.code)
            if exc.code in {
                "SEND_CAP_REACHED",
                "GMAIL_NOT_CONNECTED",
                "GMAIL_NEEDS_REAUTH",
                "GMAIL_SEND_FAILED",
            }:
                result["waiting"] += 1
                break
            result["skipped"] += 1
        except Exception:
            session.rollback()
            logger.exception("followup_auto_send_failed followup_id=%s", followup.id)
            result["skipped"] += 1
    return result


# ---------------------------------------------------------------------- readiness


def readiness(session: Session, settings: Settings) -> list[dict[str, Any]]:
    """What is still missing before the pipeline can run end to end."""
    from app.services.gmail_accounts import GmailAccountService
    from app.services.outreach_ai import resolve_email_provider
    from app.services.public_links import public_base_url

    try:
        gmail_ok = bool(GmailAccountService(session, settings).status().connected)
    except Exception:
        gmail_ok = False
    items = [
        (
            "ai",
            "AI provider for drafts and mockups",
            resolve_email_provider(settings) is not None,
            "Set GEMINI_API_KEY or GROQ_API_KEY.",
        ),
        (
            "gmail",
            "Gmail connected",
            gmail_ok,
            "Connect Gmail in Settings. Needed for sending and reply tracking.",
        ),
        (
            "base_url",
            "Public app URL for mockup links",
            bool(public_base_url(settings)),
            "Set PUBLIC_BASE_URL. Without it, emails go out without a mockup link.",
        ),
        (
            "postal",
            "Postal address for the email footer",
            bool(settings.outreach_postal_address.strip()),
            "Set OUTREACH_POSTAL_ADDRESS. Required for automatic sending.",
        ),
        (
            "cron",
            "Cron secret",
            bool(os.environ.get("CRON_SECRET", "").strip()),
            "Set CRON_SECRET and add APP_URL and CRON_SECRET as GitHub secrets.",
        ),
        (
            "research",
            "Research provider (optional)",
            settings.lead_research_configured,
            "Set TAVILY_API_KEY or EXA_API_KEY for richer emails and mockups.",
        ),
    ]
    return [{"key": k, "label": label, "ok": ok, "hint": hint} for k, label, ok, hint in items]


def discovery_overview(session: Session, settings: Settings) -> dict[str, Any]:
    from app.models.market import MarketCell
    from app.services.automation_config import get_config
    from app.services.discovery_engine import (
        candidate_cells,
        created_today,
        rejections_today,
    )

    config = get_config(session)
    done, by_country, by_category = created_today(session)
    now = datetime.now(UTC)
    cells = list(session.scalars(select(MarketCell)))
    resting = sum(1 for c in cells if c.next_eligible_at and c.next_eligible_at > now)
    return {
        "enabled": settings.discovery_enabled and config.discovery_daily_limit > 0,
        "limit": config.discovery_daily_limit,
        "created_today": done,
        "by_country": dict(by_country.most_common(8)),
        "by_category": dict(by_category.most_common(8)),
        "rejected_today": rejections_today(session),
        "markets_total": len(candidate_cells(config)),
        "markets_searched": sum(1 for c in cells if c.searches > 0),
        "markets_resting": resting,
    }


def learning_overview(session: Session) -> dict[str, Any]:
    from app.services.learning import load_state, summary_for_ui

    return summary_for_ui(load_state(session))


def outreach_overview(session: Session, settings: Settings) -> dict[str, Any]:
    from app.models.outreach import OutreachMessage
    from app.services.automation_config import get_config
    from app.services.outreach_policy import first_emails_sent_today
    from app.services.pipeline import PipelineService

    config = get_config(session)
    service = PipelineService(session, settings)
    ranking = service.queued_draft_ranking()
    next_up: list[dict[str, Any]] = []
    for job, priority in ranking[:5]:
        lead = session.get(Lead, job.lead_id)
        if lead is None or priority.blocked:
            continue
        next_up.append(
            {
                "lead_id": str(lead.id),
                "business_name": lead.business_name,
                "country": lead.country,
                "priority": priority.score,
                "strategy": priority.strategy,
                "reasons": priority.reasons,
            }
        )
    return {
        "daily_limit": config.outreach_daily_limit,
        "drafted_today": service.used_today("draft"),
        "slots_left": service.draft_slots_left(),
        "sent_today": first_emails_sent_today(session),
        "waiting": len(ranking),
        "drafts_to_review": int(
            session.scalar(
                select(func.count())
                .select_from(OutreachMessage)
                .where(OutreachMessage.status.in_(("DRAFT", "READY")))
            )
            or 0
        ),
        "next_up": next_up,
    }


def overview(session: Session, settings: Settings) -> dict[str, Any]:
    return {
        "discovery": discovery_overview(session, settings),
        "outreach": outreach_overview(session, settings),
        "learning": learning_overview(session),
        "flags": get_flags(session),
        "readiness": readiness(session, settings),
        "last_tick": get_last_tick(session),
        "sent_today": sent_today(session),
        "daily_cap": settings.outreach_daily_send_cap,
        "send_window": {
            "timezone": settings.outreach_timezone,
            "start_hour": settings.outreach_send_start_hour,
            "end_hour": settings.outreach_send_end_hour,
            "open_now": in_send_window(settings),
        },
    }


def first_contact_name(session: Session, lead_id: Any) -> str | None:
    name = session.scalar(
        select(Contact.name)
        .where(Contact.lead_id == lead_id, Contact.name.is_not(None))
        .order_by(Contact.is_primary.desc(), Contact.created_at.asc())
        .limit(1)
    )
    if not isinstance(name, str):
        return None
    first = name.strip().split(" ", 1)[0].strip(" ,.")
    if not first or "@" in first:
        return None
    return first
