"""Who may be emailed automatically, what every cold email must contain, and send caps.

Policies per country are one of:
  allow   - automation may send (after your approval rules)
  manual  - never auto-send; you can still send by hand from the lead page
  block   - never send
Unknown or missing countries are "manual". This is a conservative default, not legal
advice. Override it with OUTREACH_COUNTRY_POLICY, for example '{"US":"allow","DE":"block"}'.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import EmailDirection
from app.models.gmail import LeadEmail
from app.models.lead import Lead

logger = logging.getLogger(__name__)

Policy = Literal["allow", "manual", "block"]
_VALID: set[str] = {"allow", "manual", "block"}

DEFAULT_POLICY: dict[str, Policy] = {"US": "allow"}

_NAME_TO_CODE = {
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "england": "GB",
    "canada": "CA",
    "australia": "AU",
    "new zealand": "NZ",
    "germany": "DE",
    "austria": "AT",
    "france": "FR",
    "spain": "ES",
    "italy": "IT",
    "netherlands": "NL",
    "ireland": "IE",
    "pakistan": "PK",
    "india": "IN",
    "united arab emirates": "AE",
    "uae": "AE",
    "saudi arabia": "SA",
    "south africa": "ZA",
    "singapore": "SG",
}

UNSUBSCRIBE_MARKER = "reply \"unsubscribe\""


def country_code(country: str | None) -> str | None:
    value = (country or "").strip()
    if not value:
        return None
    named = _NAME_TO_CODE.get(value.casefold())
    if named:
        return named
    if len(value) == 2 and value.isalpha():
        return value.upper()
    return None


def policy_table(settings: Settings) -> dict[str, Policy]:
    table: dict[str, Policy] = dict(DEFAULT_POLICY)
    raw = settings.outreach_country_policy.strip()
    if not raw:
        return table
    try:
        parsed = json.loads(raw)
    except ValueError:
        logger.warning("outreach_country_policy_invalid_json")
        return table
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if isinstance(key, str) and isinstance(value, str) and value.lower() in _VALID:
                table[key.strip().upper()] = value.lower()  # type: ignore[assignment]
    return table


def policy_for(lead: Lead, settings: Settings) -> Policy:
    code = country_code(lead.country)
    if code is None:
        return "manual"
    return policy_table(settings).get(code, "manual")


def blocked_reason(lead: Lead) -> str | None:
    if lead.do_not_contact or lead.lead_status == "DO_NOT_CONTACT":
        return "Lead is marked do not contact."
    if lead.email_suppressed:
        return "Email address is suppressed after a bounce."
    if not (lead.email or "").strip():
        return "Lead has no email address."
    return None


def can_auto_send(lead: Lead, settings: Settings) -> tuple[bool, str]:
    reason = blocked_reason(lead)
    if reason:
        return False, reason
    policy = policy_for(lead, settings)
    if policy != "allow":
        return False, f"Country policy is '{policy}' for {lead.country or 'an unknown country'}."
    if not settings.outreach_postal_address.strip():
        return False, "Set OUTREACH_POSTAL_ADDRESS before automatic sending."
    return True, "ok"


def enforce_policy_for_send(lead: Lead, settings: Settings) -> None:
    """Manual sends are allowed for 'manual' countries but never for 'block'."""
    if policy_for(lead, settings) == "block":
        raise AppError(
            code="COUNTRY_BLOCKED",
            message=f"Your country policy blocks email to {lead.country or 'this country'}.",
            status_code=409,
        )


def with_compliance_footer(body: str, settings: Settings) -> str:
    if UNSUBSCRIBE_MARKER in body.lower():
        return body
    lines = [
        "",
        "--",
        "Not relevant? Just reply \"unsubscribe\" and I will not contact you again.",
    ]
    address = settings.outreach_postal_address.strip()
    if address:
        lines.append(address)
    return body.rstrip() + "\n" + "\n".join(lines) + "\n"


def sent_today(session: Session) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = session.scalar(
        select(func.count())
        .select_from(LeadEmail)
        .where(
            LeadEmail.direction == EmailDirection.OUTBOUND.value,
            LeadEmail.occurred_at >= start,
        )
    )
    return int(count or 0)


def first_emails_sent_today(session: Session) -> int:
    """Emails sent today that are not automatic follow-ups."""
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = session.scalar(
        select(func.count())
        .select_from(LeadEmail)
        .where(
            LeadEmail.direction == EmailDirection.OUTBOUND.value,
            LeadEmail.occurred_at >= start,
            func.coalesce(LeadEmail.idempotency_key, "").not_like("followup:%"),
        )
    )
    return int(count or 0)


def enforce_daily_cap(session: Session, settings: Settings) -> None:
    cap = settings.outreach_daily_send_cap
    if cap and sent_today(session) >= cap:
        raise AppError(
            code="SEND_CAP_REACHED",
            message=f"Daily send limit of {cap} reached. It resets at 00:00 UTC.",
            status_code=429,
        )
