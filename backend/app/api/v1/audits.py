import logging
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.schemas.audits import AuditRead
from app.services.audits import AuditService
from app.services.storage import read_screenshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audits"])


async def run_audit(
    audit_id: UUID,
    session_factory: Callable[[], Session],
    storage_dir: Path,
    pagespeed_api_key: str = "",
    user_agent: str = "",
) -> None:
    session = session_factory()
    try:
        await AuditService(session, storage_dir, pagespeed_api_key, user_agent).execute(audit_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("audit_job_failed")
    finally:
        session.close()


@router.post("/leads/{lead_id}/audit", response_model=AuditRead, status_code=201)
async def start_audit(
    lead_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> AuditRead:
    service = AuditService(session, request.app.state.settings.storage_dir)
    audit, should_run = service.prepare(lead_id)
    session.commit()
    if should_run:
        background_tasks.add_task(
            run_audit,
            audit.id,
            request.app.state.session_factory,
            request.app.state.settings.storage_dir,
            request.app.state.settings.google_pagespeed_api_key,
            request.app.state.settings.discovery_user_agent,
        )
    return AuditRead.model_validate(audit)


@router.get("/leads/{lead_id}/audit", response_model=AuditRead)
def get_latest_audit(lead_id: UUID, request: Request, session: SessionDep) -> AuditRead:
    audit = AuditService(session, request.app.state.settings.storage_dir).latest(lead_id)
    return AuditRead.model_validate(audit)


@router.get("/leads/{lead_id}/audits", response_model=list[AuditRead])
def list_audits(lead_id: UUID, request: Request, session: SessionDep) -> list[AuditRead]:
    audits = AuditService(session, request.app.state.settings.storage_dir).list_for_lead(lead_id)
    return [AuditRead.model_validate(audit) for audit in audits]


@router.post("/audits/{audit_id}/rerun", response_model=AuditRead, status_code=201)
async def rerun_audit(
    audit_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> AuditRead:
    service = AuditService(session, request.app.state.settings.storage_dir)
    audit, should_run = service.rerun(audit_id)
    session.commit()
    if should_run:
        background_tasks.add_task(
            run_audit,
            audit.id,
            request.app.state.session_factory,
            request.app.state.settings.storage_dir,
            request.app.state.settings.google_pagespeed_api_key,
            request.app.state.settings.discovery_user_agent,
        )
    return AuditRead.model_validate(audit)


@router.get("/audits/{audit_id}/screenshots/{variant}")
def get_screenshot(
    audit_id: UUID, variant: str, request: Request, session: SessionDep
) -> Response:
    service = AuditService(session, request.app.state.settings.storage_dir)
    audit = service.get(audit_id)
    relative = None
    if variant == "desktop":
        relative = audit.desktop_screenshot_url
    elif variant == "mobile":
        relative = audit.mobile_screenshot_url
    data = None
    if variant in {"desktop", "mobile"}:
        data = read_screenshot(
            request.app.state.settings.storage_dir,
            relative,
            audit.raw_analysis,
            variant,
        )
    if data is None:
        raise AppError(
            code="NOT_FOUND",
            message="That screenshot could not be found.",
            status_code=404,
        )
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{variant}.png"',
            "Cache-Control": "private, max-age=300",
        },
    )
