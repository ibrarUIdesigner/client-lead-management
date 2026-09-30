from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.models.enums import DiscoveryTrigger
from app.schemas.discovery import (
    DiscoveryRunStarted,
    DiscoverySearchCreate,
    DiscoverySearchRead,
    DiscoverySearchUpdate,
    DiscoveryStatus,
)
from app.services.discovery import DiscoveryService, start_discovery_run

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _next_run(request: Request):
    scheduler = getattr(request.app.state, "discovery_scheduler", None)
    if scheduler is None:
        return None
    job = scheduler.get_job("daily_lead_discovery")
    if job is None:
        return None
    return job.next_run_time


@router.get("", response_model=DiscoveryStatus)
def get_discovery(session: SessionDep, request: Request) -> DiscoveryStatus:
    settings = request.app.state.settings
    return DiscoveryService(session, settings).status(_next_run(request))


@router.post("/searches", response_model=DiscoverySearchRead, status_code=201)
def create_search(
    data: DiscoverySearchCreate,
    session: SessionDep,
    request: Request,
) -> DiscoverySearchRead:
    return DiscoveryService(session, request.app.state.settings).create_search(data)


@router.patch("/searches/{search_id}", response_model=DiscoverySearchRead)
def update_search(
    search_id: UUID,
    data: DiscoverySearchUpdate,
    session: SessionDep,
    request: Request,
) -> DiscoverySearchRead:
    return DiscoveryService(session, request.app.state.settings).update_search(search_id, data)


@router.delete("/searches/{search_id}", status_code=204)
def delete_search(search_id: UUID, session: SessionDep, request: Request) -> Response:
    DiscoveryService(session, request.app.state.settings).delete_search(search_id)
    return Response(status_code=204)


@router.post("/run", response_model=DiscoveryRunStarted, status_code=202)
def run_discovery(
    session: SessionDep,
    request: Request,
    search_id: UUID | None = None,
) -> DiscoveryRunStarted:
    settings = request.app.state.settings
    service = DiscoveryService(session, settings)
    if search_id is not None:
        service.ensure_search(search_id)
    result = start_discovery_run(
        request.app.state.session_factory,
        settings,
        search_id=search_id,
        trigger=DiscoveryTrigger.MANUAL,
    )
    if result == "busy":
        raise AppError(
            code="SEARCH_RUNNING",
            message="A search is already running.",
            status_code=409,
        )
    if result == "empty":
        raise AppError(
            code="SEARCH_EMPTY",
            message="Save an active search first.",
            status_code=400,
        )
    return DiscoveryRunStarted(started=True)
