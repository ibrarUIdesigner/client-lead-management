"""Approval queue: drafts waiting for you. Protected by the session middleware."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.models.enums import MockupStatus, OutreachStatus
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.repositories.activities import ActivityRepository
from app.schemas.gmail import LeadEmailSendRequest
from app.services.automation import check_draft_quality, recent_outreach_bodies
from app.services.automation_config import ExclusionSet
from app.services.gmail_mail import GmailMailService
from app.services.outreach_policy import blocked_reason, policy_for
from app.services.outreach_priority import STRATEGY_LABELS, rank_leads
from app.services.public_links import public_mockup_url

router = APIRouter(prefix="/outreach/queue", tags=["outreach"])

_PENDING = [OutreachStatus.DRAFT.value, OutreachStatus.READY.value]


class QueueItem(BaseModel):
    id: UUID
    lead_id: UUID
    business_name: str
    industry: str | None = None
    country: str | None = None
    email: str | None = None
    lead_score: int | None = None
    subject: str | None = None
    body: str | None = None
    mockup_url: str | None = None
    country_policy: str
    priority: float = 0
    strategy: str | None = None
    strategy_label: str | None = None
    reasons: list[str] = []
    variant: str | None = None
    problems: list[str]
    blocked: str | None = None
    created_at: datetime


class ApproveBody(BaseModel):
    subject: str | None = Field(default=None, max_length=998)
    body: str | None = Field(default=None, max_length=20000)


@router.get("", response_model=list[QueueItem])
def list_queue(request: Request, session: SessionDep) -> list[QueueItem]:
    settings = request.app.state.settings
    exclusions = ExclusionSet.load(session)
    rows = session.execute(
        select(OutreachMessage, Lead)
        .join(Lead, Lead.id == OutreachMessage.lead_id)
        .where(
            OutreachMessage.status.in_(_PENDING),
            OutreachMessage.channel.in_(["email"]) | OutreachMessage.channel.is_(None),
        )
        .order_by(Lead.lead_score.desc().nulls_last(), OutreachMessage.created_at.desc())
        .limit(100)
    ).all()
    ranks = rank_leads(session, settings, [lead.id for _m, lead in rows])
    items: list[QueueItem] = []
    for message, lead in rows:
        priority = ranks.get(lead.id)
        mockup = session.scalar(
            select(Mockup)
            .where(Mockup.lead_id == lead.id, Mockup.status == MockupStatus.READY.value)
            .order_by(Mockup.version.desc())
            .limit(1)
        )
        items.append(
            QueueItem(
                id=message.id,
                lead_id=lead.id,
                business_name=lead.business_name,
                industry=lead.industry,
                country=lead.country,
                email=lead.email,
                lead_score=lead.lead_score,
                subject=message.subject,
                body=message.message,
                mockup_url=public_mockup_url(settings, mockup),
                country_policy=policy_for(lead, settings),
                priority=priority.score if priority else 0,
                strategy=priority.strategy if priority else None,
                strategy_label=STRATEGY_LABELS.get(priority.strategy) if priority else None,
                reasons=priority.reasons if priority else [],
                variant=message.variant,
                problems=check_draft_quality(
                    message.subject,
                    message.message,
                    lead.business_name,
                    recent_bodies=recent_outreach_bodies(session, exclude_id=message.id),
                ),
                blocked=blocked_reason(lead) or exclusions.match_lead(lead),
                created_at=message.created_at,
            )
        )
    items.sort(key=lambda item: item.priority, reverse=True)
    return items


def _pending(session: SessionDep, message_id: UUID) -> tuple[OutreachMessage, Lead]:
    message = session.get(OutreachMessage, message_id)
    if message is None or message.status not in _PENDING:
        raise AppError(
            code="OUTREACH_NOT_FOUND",
            message="That draft is no longer waiting for approval.",
            status_code=404,
        )
    lead = session.get(Lead, message.lead_id)
    if lead is None:
        raise AppError(code="LEAD_NOT_FOUND", message="That lead could not be found.", status_code=404)
    return message, lead


@router.post("/{message_id}/approve")
def approve(
    message_id: UUID, body: ApproveBody, request: Request, session: SessionDep
) -> dict[str, str]:
    """Send this draft now. Your edits are saved first. Limits and safety rules still apply."""
    message, lead = _pending(session, message_id)
    if body.subject is not None:
        message.subject = body.subject
    if body.body is not None:
        message.message = body.body
    session.flush()
    GmailMailService(session, request.app.state.settings).send(
        lead.id,
        LeadEmailSendRequest(
            subject=message.subject or "",
            body=message.message or "",
            outreach_message_id=message.id,
            idempotency_key=f"approve:{message.id}",
        ),
    )
    return {"status": "sent"}


@router.post("/{message_id}/skip")
def skip(message_id: UUID, session: SessionDep) -> dict[str, str]:
    message, lead = _pending(session, message_id)
    message.status = OutreachStatus.CANCELLED.value
    ActivityRepository(session).add(
        lead.id, "outreach_skipped", "Draft skipped", description=message.subject
    )
    return {"status": "skipped"}
