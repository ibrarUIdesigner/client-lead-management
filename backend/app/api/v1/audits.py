import logging
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.schemas.audits import AuditRead
from app.services.audits import AuditService
from app.services.storage import resolve_storage_path

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
) -> FileResponse:
    service = AuditService(session, request.app.state.settings.storage_dir)
    audit = service.get(audit_id)
    relative = audit.desktop_screenshot_url if variant == "desktop" else None
    if variant == "mobile":
        relative = audit.mobile_screenshot_url
    if variant not in {"desktop", "mobile"} or not relative:
        raise AppError(
            code="NOT_FOUND",
            message="That screenshot could not be found.",
            status_code=404,
        )
    path = resolve_storage_path(request.app.state.settings.storage_dir, relative)
    if not path.is_file():
        raise AppError(
            code="NOT_FOUND",
            message="That screenshot could not be found.",
            status_code=404,
        )
    return FileResponse(
        path,
        media_type="image/png",
        filename=f"{variant}.png",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=300"},
    )
