from typing import Any
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.gmail import LeadEmail
from app.schemas.intelligence import LeadIntelligenceRead
from app.services.knowledge import sales_knowledge
from app.services.lead_intelligence import LeadIntelligenceService
from app.services.persistence import flush_or_reject
from app.services.reply_handler import ReplyHandlerService

router = APIRouter()


@router.get("/leads/{lead_id}/intelligence", response_model=LeadIntelligenceRead)
def get_lead_intelligence(
    lead_id: UUID,
    db: SessionDep,
) -> LeadIntelligenceRead:
    service = LeadIntelligenceService(db)
    intel = service.get_intelligence(lead_id)
    flush_or_reject(db)
    return LeadIntelligenceRead(**intel.to_dict())


@router.post("/leads/{lead_id}/intelligence/refresh", response_model=LeadIntelligenceRead)
def refresh_lead_intelligence(
    lead_id: UUID,
    db: SessionDep,
) -> LeadIntelligenceRead:
    service = LeadIntelligenceService(db)
    intel = service.get_intelligence(lead_id)
    flush_or_reject(db)
    return LeadIntelligenceRead(**intel.to_dict())


@router.get("/sales/playbooks")
def list_sales_playbooks() -> dict[str, list[str]]:
    return {"playbooks": sales_knowledge.list_playbooks()}


@router.get("/sales/playbooks/{name}")
def get_sales_playbook(name: str) -> dict[str, str]:
    content = sales_knowledge.get_playbook(name)
    if not content:
        raise AppError(
            code="PLAYBOOK_NOT_FOUND",
            message=f"Sales playbook '{name}' could not be found.",
            status_code=404,
        )
    return {"name": name, "content": content}


@router.get("/leads/{lead_id}/reply-suggestion")
def get_lead_reply_suggestion(
    lead_id: UUID,
    db: SessionDep,
) -> dict[str, Any]:
    statement = (
        select(LeadEmail)
        .where(LeadEmail.lead_id == lead_id, LeadEmail.direction == "INBOUND")
        .order_by(LeadEmail.occurred_at.desc())
    )
    email = db.scalars(statement).first()
    if email is None:
        raise AppError(
            code="NO_INBOUND_EMAIL",
            message="No inbound email found for this lead.",
            status_code=404,
        )
    handler = ReplyHandlerService(db, get_settings())
    analysis = handler.analyze_reply(
        lead_id,
        subject=email.subject,
        body_text=email.body_text or "",
        sender_email=email.sender_email,
    )
    return analysis.to_dict()
