import logging
import os
from collections.abc import Callable
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.models.enums import MockupStatus
from app.models.mockup import Mockup
from app.schemas.design_guides import (
    MockupCreate,
    MockupCreated,
    MockupDetail,
    MockupEligibilityRead,
    MockupGuideRead,
    MockupRefine,
    MockupRetry,
)
from app.services.mockups import MockupService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mockups"])


def _on_vercel() -> bool:
    return os.environ.get("VERCEL") == "1"


async def run_mockup(
    mockup_id: UUID,
    session_factory: Callable[[], Session],
    settings: object,
) -> None:
    session = session_factory()
    try:
        service = MockupService(session, settings, settings.storage_dir)  # type: ignore[attr-defined]
        await service.execute(mockup_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("mockup_job_failed mockup_id=%s", mockup_id)
    finally:
        session.close()


async def run_mockup_screenshots(
    mockup_id: UUID,
    session_factory: Callable[[], Session],
    settings: object,
) -> None:
    session = session_factory()
    try:
        service = MockupService(session, settings, settings.storage_dir)  # type: ignore[attr-defined]
        await service.execute_screenshots(mockup_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("mockup_screenshot_job_failed mockup_id=%s", mockup_id)
    finally:
        session.close()


async def _schedule_mockup(
    *,
    mockup_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    screenshots_only: bool = False,
) -> None:
    """Schedule mockup work.

    On Vercel, background tasks freeze after the HTTP response, so create/refine
    only persist the GENERATING row. The client must call POST /process to run
    the job in-request.
    """
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory
    if _on_vercel():
        logger.info(
            "mockup_deferred_to_process mockup_id=%s screenshots_only=%s",
            mockup_id,
            screenshots_only,
        )
        return
    if screenshots_only:
        background_tasks.add_task(run_mockup_screenshots, mockup_id, session_factory, settings)
    else:
        background_tasks.add_task(run_mockup, mockup_id, session_factory, settings)


@router.post("/mockups", response_model=MockupCreated, status_code=201)
async def create_mockup(
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> MockupCreated:
    content_type = (request.headers.get("content-type") or "").lower()
    assets: list[tuple[str, bytes, str | None]] = []
    if "multipart/form-data" in content_type:
        form = await request.form()
        data = MockupCreate(
            lead_id=UUID(str(form.get("lead_id"))),
            requirements=_optional_str(form.get("requirements")),
            source_mockup_id=_optional_uuid(form.get("source_mockup_id")),
            design_guide_id=_optional_uuid(form.get("design_guide_id")),
            guide_mode=_guide_mode(form.get("guide_mode")),
            provider=_provider(form.get("provider")),
            goal=_goal(form.get("goal")),
        )
        uploads = form.getlist("assets")
        for item in uploads:
            if not hasattr(item, "read"):
                continue
            payload = await item.read()  # type: ignore[misc]
            if not payload:
                continue
            assets.append(
                (
                    getattr(item, "filename", None) or "asset",
                    payload,
                    getattr(item, "content_type", None),
                )
            )
    else:
        payload = await request.json()
        data = MockupCreate.model_validate(payload)

    service = MockupService(session, request.app.state.settings)
    created = service.create(data, assets=assets or None)
    session.commit()
    await _schedule_mockup(
        mockup_id=created.id,
        request=request,
        background_tasks=background_tasks,
    )
    return created


@router.post("/mockups/{mockup_id}/process", response_model=MockupDetail)
async def process_mockup(mockup_id: UUID, request: Request, session: SessionDep) -> MockupDetail:
    """Resume a stuck GENERATING/PENDING mockup (needed when background jobs did not run)."""
    service = MockupService(session, request.app.state.settings)
    mockup = session.get(Mockup, mockup_id)
    if mockup is None:
        raise AppError(
            code="MOCKUP_NOT_FOUND",
            message="That mockup could not be found.",
            status_code=404,
        )
    if mockup.status in {MockupStatus.GENERATING.value, MockupStatus.PENDING.value}:
        session.commit()
        await run_mockup(mockup_id, request.app.state.session_factory, request.app.state.settings)
    elif (
        mockup.status == MockupStatus.READY.value
        and mockup.html_content
        and mockup.screenshot_status == "PENDING"
    ):
        session.commit()
        await run_mockup_screenshots(
            mockup_id,
            request.app.state.session_factory,
            request.app.state.settings,
        )
    session.expire_all()
    detail = service.detail(mockup_id, include_html=True)
    if detail.asset_refs:
        detail.asset_refs = [
            {key: value for key, value in item.items() if key != "data_uri"}
            if isinstance(item, dict)
            else item
            for item in detail.asset_refs
        ]
    return detail


@router.get("/leads/{lead_id}/mockup-eligibility", response_model=MockupEligibilityRead)
def mockup_eligibility(lead_id: UUID, request: Request, session: SessionDep) -> MockupEligibilityRead:
    payload = MockupService(session, request.app.state.settings).eligibility(lead_id)
    return MockupEligibilityRead.model_validate(payload)


@router.get("/mockups/{mockup_id}", response_model=MockupDetail)
def get_mockup(mockup_id: UUID, request: Request, session: SessionDep) -> MockupDetail:
    detail = MockupService(session, request.app.state.settings).detail(mockup_id, include_html=True)
    if detail.asset_refs:
        detail.asset_refs = [
            {key: value for key, value in item.items() if key != "data_uri"}
            if isinstance(item, dict)
            else item
            for item in detail.asset_refs
        ]
    return detail


@router.post("/mockups/{mockup_id}/refine", response_model=MockupCreated, status_code=201)
async def refine_mockup(
    mockup_id: UUID,
    data: MockupRefine,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> MockupCreated:
    created = MockupService(session, request.app.state.settings).refine(mockup_id, data)
    session.commit()
    await _schedule_mockup(
        mockup_id=created.id,
        request=request,
        background_tasks=background_tasks,
    )
    return created


@router.post("/mockups/{mockup_id}/retry", response_model=MockupCreated)
async def retry_mockup(
    mockup_id: UUID,
    data: MockupRetry,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> MockupCreated:
    created = MockupService(session, request.app.state.settings).retry(mockup_id, data)
    session.commit()
    await _schedule_mockup(
        mockup_id=created.id,
        request=request,
        background_tasks=background_tasks,
    )
    return created


@router.post("/mockups/{mockup_id}/screenshots/retry", response_model=MockupDetail)
async def retry_mockup_screenshots(
    mockup_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> MockupDetail:
    detail = MockupService(session, request.app.state.settings).retry_screenshots(mockup_id)
    session.commit()
    await _schedule_mockup(
        mockup_id=mockup_id,
        request=request,
        background_tasks=background_tasks,
        screenshots_only=True,
    )
    return MockupService(session, request.app.state.settings).detail(mockup_id, include_html=True)


@router.get("/mockups/{mockup_id}/guide", response_model=MockupGuideRead)
def mockup_guide(mockup_id: UUID, request: Request, session: SessionDep) -> MockupGuideRead:
    return MockupService(session, request.app.state.settings).guide_snapshot(mockup_id)


@router.get("/mockups/{mockup_id}/html")
def download_mockup_html(mockup_id: UUID, request: Request, session: SessionDep) -> Response:
    html = MockupService(session, request.app.state.settings).read_html(mockup_id)
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="mockup-{mockup_id}.html"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.get("/mockups/{mockup_id}/preview")
def preview_mockup_html(mockup_id: UUID, request: Request, session: SessionDep) -> Response:
    html = MockupService(session, request.app.state.settings).read_preview_html(mockup_id)
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; "
                "font-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get("/mockups/{mockup_id}/screenshots/{variant}")
def get_mockup_screenshot(
    mockup_id: UUID,
    variant: Literal["desktop", "mobile", "thumb"],
    request: Request,
    session: SessionDep,
) -> Response:
    data = MockupService(session, request.app.state.settings).read_screenshot(mockup_id, variant)
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="mockup-{mockup_id}-{variant}.png"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=60",
        },
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_uuid(value: object) -> UUID | None:
    text = _optional_str(value)
    if text is None:
        return None
    try:
        return UUID(text)
    except ValueError as exc:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Enter a valid identifier.",
            status_code=422,
        ) from exc


def _guide_mode(value: object) -> Literal["keep", "selected", "none"]:
    text = (_optional_str(value) or "none").lower()
    if text not in {"keep", "selected", "none"}:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Choose keep, selected, or none for the design guide.",
            status_code=422,
        )
    return text  # type: ignore[return-value]


def _provider(value: object) -> Literal["gemini", "groq"]:
    text = (_optional_str(value) or "").lower()
    if text not in {"gemini", "groq"}:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Choose Gemini or Groq.",
            status_code=422,
        )
    return text  # type: ignore[return-value]


def _goal(value: object) -> Literal["calls", "whatsapp", "bookings", "quotes"]:
    text = (_optional_str(value) or "calls").lower()
    if text not in {"calls", "whatsapp", "bookings", "quotes"}:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Choose calls, WhatsApp, bookings, or quotes.",
            status_code=422,
        )
    return text  # type: ignore[return-value]
