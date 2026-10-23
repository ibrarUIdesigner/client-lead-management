import logging
from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.research import LeadResearchRead, LeadResearchTrigger
from app.services.research import ResearchService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["lead-research"])


def run_research_background(
    research_id: UUID,
    session_factory: Callable[[], Session],
    settings: Settings,
    preferred_tool: str | None = None,
) -> None:
    session = session_factory()
    try:
        service = ResearchService(session, settings)
        service.execute_research(research_id, preferred_tool=preferred_tool)
    except Exception:
        logger.exception("research_background_job_failed")
    finally:
        session.close()


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
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    data: LeadResearchTrigger | None = None,
) -> LeadResearchRead:
    force = data.force_refresh if data else False
    custom_query = data.custom_query if data else None
    preferred_tool = data.preferred_tool if data else None
    settings = request.app.state.settings
    service = ResearchService(session, settings)
    research, should_run = service.prepare_research(
        lead_id,
        force_refresh=force,
        custom_query=custom_query,
        preferred_tool=preferred_tool,
    )
    if should_run:
        background_tasks.add_task(
            run_research_background,
            research.id,
            request.app.state.session_factory,
            settings,
            preferred_tool=preferred_tool,
        )
    return LeadResearchRead.model_validate(research)
