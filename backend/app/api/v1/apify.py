from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.api.deps import SessionDep
from app.integrations.apify import apify_client
from app.schemas.apify import (
    ApifyConnectorCreate,
    ApifyConnectorRead,
    ApifyImportRequest,
    ApifyImportResult,
    ApifyOverview,
    ApifyRunCreate,
    ApifyRunRead,
    DatasetPageRead,
)
from app.services.apify import ApifyService

router = APIRouter(prefix="/apify", tags=["apify"])


@router.get("", response_model=ApifyOverview)
def get_apify(session: SessionDep, request: Request) -> ApifyOverview:
    return ApifyService(session, request.app.state.settings).overview()


@router.post("/connectors", response_model=ApifyConnectorRead, status_code=201)
def create_connector(
    data: ApifyConnectorCreate,
    session: SessionDep,
    request: Request,
) -> ApifyConnectorRead:
    settings = request.app.state.settings
    with apify_client(settings) as client:
        return ApifyService(session, settings, client).create_connector(data)


@router.delete("/connectors/{connector_id}", status_code=204)
def delete_connector(connector_id: UUID, session: SessionDep, request: Request) -> Response:
    ApifyService(session, request.app.state.settings).delete_connector(connector_id)
    return Response(status_code=204)


@router.post("/connectors/{connector_id}/runs", response_model=ApifyRunRead, status_code=201)
def start_run(
    connector_id: UUID,
    data: ApifyRunCreate,
    session: SessionDep,
    request: Request,
) -> ApifyRunRead:
    settings = request.app.state.settings
    with apify_client(settings) as client:
        return ApifyService(session, settings, client).start_run(connector_id, data)


@router.get("/runs/{run_id}", response_model=ApifyRunRead)
def get_run(run_id: UUID, session: SessionDep, request: Request) -> ApifyRunRead:
    settings = request.app.state.settings
    if settings.apify_token:
        with apify_client(settings) as client:
            return ApifyService(session, settings, client).refresh_run(run_id)
    return ApifyService(session, settings).refresh_run(run_id)


@router.post("/runs/{run_id}/abort", response_model=ApifyRunRead)
def abort_run(run_id: UUID, session: SessionDep, request: Request) -> ApifyRunRead:
    settings = request.app.state.settings
    with apify_client(settings) as client:
        return ApifyService(session, settings, client).abort_run(run_id)


@router.get("/runs/{run_id}/items", response_model=DatasetPageRead)
def list_items(
    run_id: UUID,
    session: SessionDep,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> DatasetPageRead:
    settings = request.app.state.settings
    with apify_client(settings) as client:
        return ApifyService(session, settings, client).list_items(
            run_id,
            offset=offset,
            limit=limit,
        )


@router.post("/runs/{run_id}/import", response_model=ApifyImportResult)
def import_items(
    run_id: UUID,
    data: ApifyImportRequest,
    session: SessionDep,
    request: Request,
) -> ApifyImportResult:
    settings = request.app.state.settings
    if settings.apify_token:
        with apify_client(settings) as client:
            return ApifyService(session, settings, client).import_items(run_id, data)
    return ApifyService(session, settings).import_items(run_id, data)
