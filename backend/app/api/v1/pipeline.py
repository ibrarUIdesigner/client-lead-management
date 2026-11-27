"""Pipeline status and controls. Protected by the session middleware."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.models.lead import Lead
from app.models.pipeline_job import PipelineJob
from app.services.pipeline import PipelineService

router = APIRouter(tags=["pipeline"])


class PipelineJobRead(BaseModel):
    id: UUID
    step: str
    status: str
    attempts: int
    max_attempts: int
    run_after: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None
    detail: str | None = None


class LeadPipelineRead(BaseModel):
    paused: bool
    next_step: str | None
    jobs: list[PipelineJobRead]


def _read(job: PipelineJob) -> PipelineJobRead:
    detail = job.result.get("detail") if isinstance(job.result, dict) else None
    return PipelineJobRead(
        id=job.id,
        step=job.step,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        run_after=job.run_after,
        started_at=job.started_at,
        finished_at=job.finished_at,
        last_error=job.last_error,
        detail=detail if isinstance(detail, str) else None,
    )


def _lead(session: SessionDep, lead_id: UUID) -> Lead:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise AppError(code="LEAD_NOT_FOUND", message="That lead could not be found.", status_code=404)
    return lead


@router.get("/pipeline/status")
def pipeline_status(request: Request, session: SessionDep) -> dict[str, object]:
    return PipelineService(session, request.app.state.settings).status_overview()


@router.get("/leads/{lead_id}/pipeline", response_model=LeadPipelineRead)
def lead_pipeline(lead_id: UUID, request: Request, session: SessionDep) -> LeadPipelineRead:
    lead = _lead(session, lead_id)
    service = PipelineService(session, request.app.state.settings)
    jobs = service.jobs_for_lead(lead_id)
    return LeadPipelineRead(
        paused=lead.pipeline_paused,
        next_step=service.decide_next_step(lead, jobs),
        jobs=[_read(job) for job in jobs],
    )


@router.post("/leads/{lead_id}/pipeline/advance", response_model=LeadPipelineRead)
def advance_lead(lead_id: UUID, request: Request, session: SessionDep) -> LeadPipelineRead:
    """Queue the next step now. The next cron tick runs it."""
    lead = _lead(session, lead_id)
    service = PipelineService(session, request.app.state.settings)
    service.enqueue_next(lead)
    session.flush()
    jobs = service.jobs_for_lead(lead_id)
    return LeadPipelineRead(
        paused=lead.pipeline_paused,
        next_step=service.decide_next_step(lead, jobs),
        jobs=[_read(job) for job in jobs],
    )


@router.post("/leads/{lead_id}/pipeline/pause", response_model=LeadPipelineRead)
def pause_lead(lead_id: UUID, request: Request, session: SessionDep) -> LeadPipelineRead:
    lead = _lead(session, lead_id)
    lead.pipeline_paused = True
    return lead_pipeline(lead_id, request, session)


@router.post("/leads/{lead_id}/pipeline/resume", response_model=LeadPipelineRead)
def resume_lead(lead_id: UUID, request: Request, session: SessionDep) -> LeadPipelineRead:
    lead = _lead(session, lead_id)
    lead.pipeline_paused = False
    lead.pipeline_checked_at = None
    return lead_pipeline(lead_id, request, session)


@router.post("/pipeline/jobs/{job_id}/retry", response_model=PipelineJobRead)
def retry_job(job_id: UUID, request: Request, session: SessionDep) -> PipelineJobRead:
    job = PipelineService(session, request.app.state.settings).retry_job(job_id)
    return _read(job)
