"""Record every email we send and what came of it. This is the data learning relies on."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.automation import OutreachAttempt
from app.models.enums import AttemptKind, AttemptOutcome, AuditStatus, MockupStatus
from app.models.gmail import LeadEmail
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.models.website_audit import WebsiteAudit

logger = logging.getLogger(__name__)

_RANK = {
    AttemptOutcome.NONE.value: 0,
    AttemptOutcome.REPLY.value: 1,
    AttemptOutcome.NEGATIVE.value: 1,
    AttemptOutcome.POSITIVE.value: 2,
    AttemptOutcome.INTERESTED.value: 3,
    AttemptOutcome.MEETING.value: 4,
    AttemptOutcome.WON.value: 5,
}
_TERMINAL_NEGATIVE = {AttemptOutcome.BOUNCE.value, AttemptOutcome.UNSUBSCRIBE.value}

INTENT_TO_OUTCOME = {
    "Interested": AttemptOutcome.INTERESTED,
    "Meeting Request": AttemptOutcome.MEETING,
    "Positive": AttemptOutcome.POSITIVE,
    "Pricing": AttemptOutcome.POSITIVE,
    "Question": AttemptOutcome.POSITIVE,
    "Objection": AttemptOutcome.REPLY,
    "Not Interested": AttemptOutcome.NEGATIVE,
    "Wrong Person": AttemptOutcome.NEGATIVE,
    "Unsubscribe": AttemptOutcome.UNSUBSCRIBE,
    "Other": AttemptOutcome.REPLY,
}


def outcome_for_intent(intent: str | None) -> AttemptOutcome | None:
    """None means the reply says nothing about interest (for example out of office)."""
    if not intent or intent == "Out of Office":
        return None
    return INTENT_TO_OUTCOME.get(intent, AttemptOutcome.REPLY)


def derive_strategy(lead: Lead, audit: WebsiteAudit | None) -> str:
    """The main angle for this lead, from verified facts only."""
    has_site = bool((lead.website_url or "").strip()) and (lead.website_status or "") not in {
        "missing",
        "social_only",
    }
    if not has_site:
        return "no_website"
    if audit is not None:
        if (audit.design_score is not None) and audit.design_score < 50:
            return "outdated"
        if (audit.performance_score is not None and audit.performance_score < 50) or (
            audit.mobile_score is not None and audit.mobile_score < 50
        ):
            return "slow"
        if audit.ux_score is not None and audit.ux_score < 60:
            return "ux"
    return "other"


def _latest_audit(session: Session, lead_id: UUID) -> WebsiteAudit | None:
    return session.scalar(
        select(WebsiteAudit)
        .where(WebsiteAudit.lead_id == lead_id, WebsiteAudit.status == AuditStatus.COMPLETED.value)
        .order_by(WebsiteAudit.created_at.desc())
        .limit(1)
    )


def record_attempt(
    session: Session,
    lead: Lead,
    email: LeadEmail,
    *,
    kind: AttemptKind,
    sequence_step: int = 0,
    automatic: bool = False,
    message: OutreachMessage | None = None,
) -> OutreachAttempt | None:
    """Store one sent email. Safe to call twice for the same email."""
    existing = session.scalar(
        select(OutreachAttempt).where(OutreachAttempt.email_id == email.id).limit(1)
    )
    if existing is not None:
        return existing
    try:
        audit = _latest_audit(session, lead.id)
        has_mockup = bool(
            session.scalar(
                select(Mockup.id)
                .where(Mockup.lead_id == lead.id, Mockup.status == MockupStatus.READY.value)
                .limit(1)
            )
        )
        body = email.body_text or ""
        attempt = OutreachAttempt(
            lead_id=lead.id,
            email_id=email.id,
            outreach_message_id=message.id if message is not None else email.outreach_message_id,
            kind=kind.value,
            sequence_step=sequence_step,
            strategy=derive_strategy(lead, audit),
            framework=getattr(message, "variant", None),
            template_id=getattr(message, "template_id", None),
            mockup_included=has_mockup and "/api/v1/m/" in body,
            automatic=automatic,
            category=lead.industry,
            country=lead.country,
            city=lead.city,
            sent_at=email.occurred_at or datetime.now(UTC),
        )
        with session.begin_nested():
            session.add(attempt)
            session.flush()
        return attempt
    except Exception:
        logger.exception("record_attempt_failed lead_id=%s", lead.id)
        return None


def record_outcome(
    session: Session,
    lead_id: UUID,
    outcome: AttemptOutcome | None,
    *,
    at: datetime | None = None,
) -> None:
    """Attach what happened to the most recent email sent to this lead."""
    if outcome is None:
        return
    try:
        attempt = session.scalar(
            select(OutreachAttempt)
            .where(OutreachAttempt.lead_id == lead_id)
            .order_by(OutreachAttempt.sent_at.desc())
            .limit(1)
        )
        if attempt is None or attempt.outcome == AttemptOutcome.WON.value:
            return
        value = outcome.value
        if value in _TERMINAL_NEGATIVE:
            change = True
        else:
            change = _RANK.get(value, 0) > _RANK.get(attempt.outcome, 0)
            if attempt.outcome in _TERMINAL_NEGATIVE:
                change = False
        if change:
            attempt.outcome = value
            attempt.outcome_at = at or datetime.now(UTC)
            session.flush()
    except Exception:
        logger.exception("record_outcome_failed lead_id=%s", lead_id)


def attempt_summary(session: Session, lead_id: UUID) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(OutreachAttempt)
        .where(OutreachAttempt.lead_id == lead_id)
        .order_by(OutreachAttempt.sent_at.asc())
    )
    return [
        {
            "kind": row.kind,
            "step": row.sequence_step,
            "strategy": row.strategy,
            "mockup": row.mockup_included,
            "outcome": row.outcome,
            "sent_at": row.sent_at.isoformat(),
        }
        for row in rows
    ]
