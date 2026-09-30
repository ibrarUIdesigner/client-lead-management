from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import SessionDep
from app.schemas.outreach import FollowupCreate, FollowupUpdate
from app.schemas.workspace import FollowupRead
from app.services.followups import FollowupService

router = APIRouter(tags=["followups"])


@router.post("/followups", response_model=FollowupRead, status_code=201)
def create_followup(data: FollowupCreate, session: SessionDep) -> FollowupRead:
    return FollowupService(session).create(data)


@router.patch("/followups/{followup_id}", response_model=FollowupRead)
def update_followup(
    followup_id: UUID,
    data: FollowupUpdate,
    session: SessionDep,
) -> FollowupRead:
    return FollowupService(session).update(followup_id, data)


@router.post("/followups/{followup_id}/complete", response_model=FollowupRead)
def complete_followup(followup_id: UUID, session: SessionDep) -> FollowupRead:
    return FollowupService(session).complete(followup_id)


@router.delete("/followups/{followup_id}", status_code=204)
def cancel_followup(followup_id: UUID, session: SessionDep) -> Response:
    FollowupService(session).cancel(followup_id)
    return Response(status_code=204)
