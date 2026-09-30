from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.workspace import (
    AnalyticsRead,
    FollowupRead,
    MockupRead,
    OutreachMessageRead,
    OutreachTemplateRead,
)
from app.services.workspace import WorkspaceService

router = APIRouter(tags=["workspace"])


@router.get("/mockups", response_model=list[MockupRead])
def list_mockups(session: SessionDep, lead_id: UUID | None = None) -> list[MockupRead]:
    return WorkspaceService(session).list_mockups(lead_id)


@router.get("/outreach/messages", response_model=list[OutreachMessageRead])
def list_outreach_messages(
    session: SessionDep,
    lead_id: UUID | None = None,
) -> list[OutreachMessageRead]:
    return WorkspaceService(session).list_messages(lead_id)


@router.get("/outreach/templates", response_model=list[OutreachTemplateRead])
def list_outreach_templates(session: SessionDep) -> list[OutreachTemplateRead]:
    return WorkspaceService(session).list_templates()


@router.get("/followups", response_model=list[FollowupRead])
def list_followups(session: SessionDep) -> list[FollowupRead]:
    return WorkspaceService(session).list_followups()


@router.get("/analytics", response_model=AnalyticsRead)
def read_analytics(session: SessionDep) -> AnalyticsRead:
    return WorkspaceService(session).analytics()
