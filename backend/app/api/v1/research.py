from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.schemas.research import LeadResearchRead, LeadResearchTrigger
from app.services.research import ResearchService

router = APIRouter(tags=["lead-research"])


@router.get("/leads/{lead_id}/research", response_model=LeadResearchRead)
def get_lead_research(lead_id: UUID, session: SessionDep) -> LeadResearchRead:
    research = ResearchService(session).get_for_lead(lead_id)
    if research is None:
        raise AppError(
            code="RESEARCH_NOT_FOUND",
            message="No research has been conducted for this lead yet.",
            status_code=404,
        )
    return LeadResearchRead.model_validate(research)


@router.post("/leads/{lead_id}/research", response_model=LeadResearchRead)
def trigger_lead_research(
    lead_id: UUID,
    session: SessionDep,
    data: LeadResearchTrigger | None = None,
) -> LeadResearchRead:
    force = data.force_refresh if data else False
    custom_query = data.custom_query if data else None
    preferred_tool = data.preferred_tool if data else None
    research = ResearchService(session).research_lead(
        lead_id,
        force_refresh=force,
        custom_query=custom_query,
        preferred_tool=preferred_tool,
    )
    return LeadResearchRead.model_validate(research)
