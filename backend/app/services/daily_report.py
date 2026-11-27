"""The daily email: what happened in the last 24 hours and what to do next."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.models.automation import AutomationRun
from app.models.enums import AutomationRunStatus
from app.services.automation_config import AutomationConfig, claim_run, finish_run
from app.services.insights import REJECTION_LABELS, build_insights, zone_for
from app.services.public_links import public_base_url

logger = logging.getLogger(__name__)

MAX_REPORT_ATTEMPTS = 3
RETRY_AFTER = timedelta(minutes=30)
_INK = "#111827"
_MUTED = "#6b7280"
_LINE = "#e5e7eb"
_ACCENT = "#4f46e5"


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def recipient(settings: Settings, config: AutomationConfig) -> str:
    return (config.report_email or settings.outreach_sender_email or "").strip()


# ----------------------------------------------------------------------- the content


def headline(day: dict[str, Any]) -> str:
    if day["emails_sent"] == 0 and day["leads_discovered"] == 0:
        return "A quiet day. Nothing was found or sent."
    parts = [f"Found {_plural(day['leads_discovered'], 'new lead')}"]
    parts.append(f"sent {_plural(day['emails_sent'], 'email')}")
    if day["replies"]:
        parts.append(f"got {_plural(day['replies'], 'reply', 'replies')}")
    if day["interested"]:
        parts.append(f"{day['interested']} interested")
    return ", ".join(parts) + "."


def subject_line(day: dict[str, Any], now: datetime, tz: str) -> str:
    local = now.astimezone(zone_for(tz))
    tail = f"{day['emails_sent']} sent, {day['replies']} replies"
    if day["interested"]:
        tail += f", {day['interested']} interested"
    return f"Acquisition report {local:%b %d}: {tail}"


def _market_lines(rows: list[dict[str, Any]]) -> list[str]:
    judged = [r for r in rows if r["enough_data"]][:3]
    if not judged:
        return []
    return [
        f"{r['label']}: {r['positive_rate']}% positive replies from {r['sent']} emails"
        + (f", {r['clients']} won" if r["clients"] else "")
        for r in judged
    ]


def build_report(
    session: Session,
    settings: Settings,
    config: AutomationConfig,
    now: datetime | None = None,
) -> dict[str, str]:
    now = now or datetime.now(UTC)
    data = build_insights(session, settings, config, days=14, now=now)
    day = data["last_24h"]
    discovery = data["discovery"]
    base = public_base_url(settings)
    link = (lambda path: f"{base}{path}") if base else (lambda path: "")

    rejected_text = ", ".join(
        f"{n} {REJECTION_LABELS.get(reason, reason)}"
        for reason, n in discovery["rejected_by_reason"].items()
    )
    text_lines = [
        f"DAILY ACQUISITION REPORT ({now.astimezone(zone_for(config.report_timezone)):%A %d %B})",
        "The last 24 hours",
        "",
        headline(day),
        "",
        "LEAD DISCOVERY",
        f"  Found: {discovery['total']} (no website: {discovery['no_website']}, "
        f"with improvement opportunities: {discovery['with_opportunity']})",
        f"  Qualified: {day['leads_qualified']}   Left out: {day['leads_rejected']}"
        + (f" ({rejected_text})" if rejected_text else ""),
        "  By country: " + (", ".join(f"{r['label']} {r['count']}" for r in discovery["by_country"]) or "none"),
        "  By category: " + (", ".join(f"{r['label']} {r['count']}" for r in discovery["by_category"]) or "none"),
        "",
        "OUTREACH",
        f"  Sent: {day['emails_sent']} ({day['first_emails']} first emails, {day['followups_sent']} follow-ups)",
        f"  Delivered (estimate, sent minus bounces): {day['delivered_estimate']}",
        f"  Replies: {day['replies']}   Positive: {day['positive_replies']}   Interested: {day['interested']}",
        f"  Meetings or opportunities: {day['meetings']}   New clients: {day['clients_won']}",
        f"  Bounces: {day['bounces']}   Unsubscribes: {day['unsubscribes']}",
        "",
        "WORK DONE",
        f"  Audits: {day['audits_completed']}   Mockups: {day['mockups_generated']}",
    ]
    promising = data["promising"]
    if promising:
        text_lines += ["", "MOST PROMISING RIGHT NOW"]
        text_lines += [
            f"  {p['business_name']} ({p['outcome']}{', unread reply' if p['unread'] else ''})"
            + (f" {link('/leads/' + p['lead_id'])}" if base else "")
            for p in promising
        ]
    best_cat = _market_lines(data["categories"])
    best_country = _market_lines(data["countries"])
    if best_cat or best_country:
        text_lines += ["", "WHAT IS WORKING"]
        text_lines += [f"  Category: {line}" for line in best_cat]
        text_lines += [f"  Country: {line}" for line in best_country]
    text_lines += ["", "FOR TOMORROW"]
    text_lines += [f"  - {tip}" for tip in data["recommendations"]] or ["  - Nothing to change."]
    if base:
        text_lines += ["", f"Open the dashboard: {base}/insights"]

    subject = subject_line(day, now, config.report_timezone)
    return {
        "subject": subject,
        "text": "\n".join(text_lines),
        "html": _render_html(data, day, discovery, base, best_cat, best_country, subject),
    }


# ------------------------------------------------------------------------- HTML


def _kpi(label: str, value: Any, hint: str = "") -> str:
    return (
        f'<td style="padding:12px 8px;text-align:center;border:1px solid {_LINE};border-radius:8px;" width="25%">'
        f'<div style="font-size:24px;font-weight:700;color:{_INK};">{escape(str(value))}</div>'
        f'<div style="font-size:12px;color:{_MUTED};margin-top:2px;">{escape(label)}</div>'
        + (f'<div style="font-size:11px;color:{_MUTED};">{escape(hint)}</div>' if hint else "")
        + "</td>"
    )


def _row_of_kpis(items: list[tuple[str, Any, str]]) -> str:
    cells = "".join(_kpi(*item) for item in items)
    return (
        '<table role="presentation" width="100%" cellspacing="6" cellpadding="0" style="margin:6px 0 2px;">'
        f"<tr>{cells}</tr></table>"
    )


def _section(title: str, body: str) -> str:
    return (
        f'<h2 style="font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:{_ACCENT};'
        f'margin:26px 0 8px;">{escape(title)}</h2>{body}'
    )


def _list(items: list[str]) -> str:
    if not items:
        return f'<p style="margin:4px 0;color:{_MUTED};font-size:14px;">Nothing yet.</p>'
    li = "".join(f'<li style="margin:5px 0;font-size:14px;color:{_INK};">{escape(i)}</li>' for i in items)
    return f'<ul style="margin:4px 0 0;padding-left:20px;">{li}</ul>'


def _render_html(
    data: dict[str, Any],
    day: dict[str, Any],
    discovery: dict[str, Any],
    base: str,
    best_cat: list[str],
    best_country: list[str],
    subject: str,
) -> str:
    rejected = ", ".join(
        f"{n} {REJECTION_LABELS.get(r, r)}" for r, n in discovery["rejected_by_reason"].items()
    )
    discovery_html = (
        _row_of_kpis(
            [
                ("Leads found", discovery["total"], ""),
                ("No website", discovery["no_website"], ""),
                ("Can be improved", discovery["with_opportunity"], ""),
                ("Left out", day["leads_rejected"], ""),
            ]
        )
        + _list(
            [
                "Countries: " + (", ".join(f"{r['label']} ({r['count']})" for r in discovery["by_country"]) or "none"),
                "Categories: " + (", ".join(f"{r['label']} ({r['count']})" for r in discovery["by_category"]) or "none"),
            ]
            + ([f"Left out because: {rejected}"] if rejected else [])
        )
    )
    outreach_html = (
        _row_of_kpis(
            [
                ("Emails sent", day["emails_sent"], f"{day['first_emails']} first, {day['followups_sent']} follow-up"),
                ("Replies", day["replies"], ""),
                ("Positive", day["positive_replies"], ""),
                ("Interested", day["interested"], ""),
            ]
        )
        + _row_of_kpis(
            [
                ("Meetings", day["meetings"], ""),
                ("New clients", day["clients_won"], ""),
                ("Bounces", day["bounces"], ""),
                ("Unsubscribes", day["unsubscribes"], ""),
            ]
        )
        + f'<p style="font-size:12px;color:{_MUTED};margin:6px 0 0;">Delivered is an estimate: '
        f"{day['delivered_estimate']} of {day['emails_sent']} (sent minus bounces).</p>"
    )
    promising_items = []
    for p in data["promising"]:
        label = f"{p['business_name']}: {p['outcome']}" + (" (unread reply)" if p["unread"] else "")
        if base:
            label_html = (
                f'<a href="{escape(base)}/leads/{escape(p["lead_id"])}" style="color:{_ACCENT};">'
                f"{escape(label)}</a>"
            )
        else:
            label_html = escape(label)
        promising_items.append(f'<li style="margin:5px 0;font-size:14px;">{label_html}</li>')
    promising_html = (
        f'<ul style="margin:4px 0 0;padding-left:20px;">{"".join(promising_items)}</ul>'
        if promising_items
        else f'<p style="margin:4px 0;color:{_MUTED};font-size:14px;">No interested prospects yet.</p>'
    )
    working_html = _list([f"Category: {x}" for x in best_cat] + [f"Country: {x}" for x in best_country])
    if not best_cat and not best_country:
        working_html = (
            f'<p style="margin:4px 0;color:{_MUTED};font-size:14px;">'
            "Too early to say. Rankings appear after about 15 emails per category or country.</p>"
        )
    dash = (
        f'<p style="margin:26px 0 0;"><a href="{escape(base)}/insights" '
        f'style="display:inline-block;background:{_ACCENT};color:#fff;text-decoration:none;'
        f'padding:10px 18px;border-radius:8px;font-size:14px;">Open the dashboard</a></p>'
        if base
        else ""
    )
    return (
        '<!doctype html><html><body style="margin:0;background:#f3f4f6;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="640" cellspacing="0" cellpadding="0" '
        'style="max-width:640px;width:100%;background:#fff;border-radius:12px;">'
        '<tr><td style="padding:28px 28px 32px;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;">'
        f'<div style="font-size:12px;color:{_MUTED};">Daily acquisition report, last 24 hours</div>'
        f'<h1 style="font-size:22px;line-height:1.3;color:{_INK};margin:6px 0 0;">{escape(headline(day))}</h1>'
        + _section("Lead discovery", discovery_html)
        + _section("Outreach", outreach_html)
        + _section("Most promising right now", promising_html)
        + _section("What is working", working_html)
        + _section("For tomorrow", _list(data["recommendations"]) if data["recommendations"] else _list(["Nothing to change."]))
        + dash
        + "</td></tr></table></td></tr></table></body></html>"
    )


# --------------------------------------------------------------------------- sending


def send_report(session: Session, settings: Settings, config: AutomationConfig, now: datetime | None = None) -> dict[str, str]:
    from app.services.gmail_accounts import GmailAccountService

    to = recipient(settings, config)
    if not to:
        raise AppError(
            code="REPORT_NO_ADDRESS",
            message="Set a report email address on the Automation page.",
            status_code=422,
        )
    report = build_report(session, settings, config, now)
    accounts = GmailAccountService(session, settings)
    account = accounts.require_active_account()
    access = accounts.access_token_for(account)
    accounts.client.send_message(
        access,
        to=to,
        subject=report["subject"],
        body_text=report["text"],
        body_html=report["html"],
        from_email=account.email,
    )
    return {"to": to, "subject": report["subject"]}


def maybe_send_daily_report(
    session_factory: sessionmaker[Session],
    settings: Settings,
    config: AutomationConfig,
    now: datetime | None = None,
) -> str:
    """Send today's report once the configured time has passed. Safe to call every tick."""
    now = now or datetime.now(UTC)
    zone = zone_for(config.report_timezone)
    local = now.astimezone(zone)
    hour, minute = (int(part) for part in config.report_time.split(":"))
    if local < local.replace(hour=hour, minute=minute, second=0, microsecond=0):
        return "not due yet"
    date_key = local.date().isoformat()

    with session_factory() as session:
        runs = list(
            session.scalars(
                select(AutomationRun).where(
                    AutomationRun.kind == "report", AutomationRun.run_key.like(f"report:{date_key}:%")
                )
            )
        )
        if any(r.status == AutomationRunStatus.OK.value for r in runs):
            return "already sent"
        if any(
            r.status == AutomationRunStatus.RUNNING.value and r.started_at > now - timedelta(minutes=15)
            for r in runs
        ):
            return "in progress"
        failures = [r for r in runs if r.status != AutomationRunStatus.RUNNING.value]
        if len(failures) >= MAX_REPORT_ATTEMPTS:
            return "gave up for today"
        if failures and max(r.started_at for r in failures) > now - RETRY_AFTER:
            return "waiting to retry"
        run = claim_run(session, "report", f"report:{date_key}:{len(runs) + 1}", now)
        if run is None:
            session.commit()
            return "already running"
        run_id = run.id
        session.commit()

    with session_factory() as session:
        run = session.get(AutomationRun, run_id)
        assert run is not None
        try:
            sent = send_report(session, settings, config, now)
            finish_run(session, run, AutomationRunStatus.OK, summary=sent)
            result = "sent"
        except AppError as exc:
            finish_run(session, run, AutomationRunStatus.FAILED, error=exc.message)
            result = f"failed: {exc.message}"
        except Exception as exc:
            logger.exception("daily_report_failed")
            finish_run(session, run, AutomationRunStatus.FAILED, error=str(exc) or "The report could not be sent.")
            result = "failed"
        session.commit()
    return result
