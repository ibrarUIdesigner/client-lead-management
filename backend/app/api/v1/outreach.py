from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.outreach import (
    OutreachCreate,
    OutreachGenerate,
    OutreachOfferSuggestion,
    OutreachUpdate,
)
from app.schemas.workspace import OutreachMessageRead
from app.services.outreach import OutreachService

router = APIRouter(tags=["outreach"])


@router.get("/leads/{lead_id}/outreach", response_model=list[OutreachMessageRead])
def list_lead_outreach(lead_id: UUID, session: SessionDep) -> list[OutreachMessageRead]:
    return OutreachService(session).list_for_lead(lead_id)


@router.get("/leads/{lead_id}/outreach/offer", response_model=OutreachOfferSuggestion)
def suggest_outreach_offer(lead_id: UUID, session: SessionDep) -> OutreachOfferSuggestion:
    return OutreachService(session).suggest_offer(lead_id)


@router.post(
    "/leads/{lead_id}/outreach/generate",
    response_model=OutreachMessageRead,
    status_code=201,
)
def generate_outreach(
    lead_id: UUID,
    data: OutreachGenerate,
    session: SessionDep,
) -> OutreachMessageRead:
    return OutreachService(session).generate(lead_id, data)


@router.post("/outreach", response_model=OutreachMessageRead, status_code=201)
def create_outreach(data: OutreachCreate, session: SessionDep) -> OutreachMessageRead:
    return OutreachService(session).create(data)


@router.patch("/outreach/{message_id}", response_model=OutreachMessageRead)
def update_outreach(
    message_id: UUID,
    data: OutreachUpdate,
    session: SessionDep,
) -> OutreachMessageRead:
    return OutreachService(session).update(message_id, data)


@router.post("/outreach/{message_id}/mark-contacted", response_model=OutreachMessageRead)
def mark_outreach_contacted(message_id: UUID, session: SessionDep) -> OutreachMessageRead:
    return OutreachService(session).mark_contacted(message_id)


@router.post("/outreach/{message_id}/mark-replied", response_model=OutreachMessageRead)
def mark_outreach_replied(message_id: UUID, session: SessionDep) -> OutreachMessageRead:
    return OutreachService(session).mark_replied(message_id)
