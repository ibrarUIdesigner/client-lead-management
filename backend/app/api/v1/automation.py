"""Automation switches and readiness. Protected by the session middleware."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.models.automation import AutomationRun, LeadExclusion
from app.models.lead import Lead
from app.models.pipeline_job import PipelineJob
from app.services import automation
from app.services.automation_config import (
    AutomationConfig,
    get_config,
    normalize_exclusion,
    save_config,
)
from app.services.pipeline import PipelineService

router = APIRouter(prefix="/automation", tags=["automation"])


class FlagsUpdate(BaseModel):
    auto_send_enabled: bool | None = None
    followups_auto_send: bool | None = None
    breakup_auto_send: bool | None = None


@router.get("")
def get_automation(request: Request, session: SessionDep) -> dict[str, object]:
    settings = request.app.state.settings
    data = automation.overview(session, settings)
    data["pipeline"] = PipelineService(session, settings).status_overview()
    return data


@router.put("/flags")
def update_flags(
    body: FlagsUpdate, request: Request, session: SessionDep
) -> dict[str, bool]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    # The closing note and follow-ups only make sense when the first email is automatic
    # or sent by you, so each switch is independent. Nothing is implied.
    return automation.set_flags(session, updates)


# ------------------------------------------------------------------------ config


@router.get("/config", response_model=AutomationConfig)
def read_config(session: SessionDep) -> AutomationConfig:
    return get_config(session)


@router.put("/config", response_model=AutomationConfig)
def write_config(body: AutomationConfig, session: SessionDep) -> AutomationConfig:
    return save_config(session, body)


@router.post("/pause", response_model=AutomationConfig)
def pause(session: SessionDep) -> AutomationConfig:
    config = get_config(session)
    config.paused = True
    return save_config(session, config)


@router.post("/resume", response_model=AutomationConfig)
def resume(session: SessionDep) -> AutomationConfig:
    config = get_config(session)
    config.paused = False
    return save_config(session, config)


# -------------------------------------------------------------------- exclusions


class ExclusionCreate(BaseModel):
    kind: Literal["domain", "email", "name", "category"]
    value: str = Field(min_length=2, max_length=255)
    note: str | None = Field(default=None, max_length=500)


class ExclusionRead(BaseModel):
    id: UUID
    kind: str
    value: str
    note: str | None = None
    created_at: datetime


@router.get("/exclusions", response_model=list[ExclusionRead])
def list_exclusions(session: SessionDep) -> list[ExclusionRead]:
    rows = session.scalars(select(LeadExclusion).order_by(LeadExclusion.created_at.desc()))
    return [ExclusionRead.model_validate(r, from_attributes=True) for r in rows]


@router.post("/exclusions", response_model=ExclusionRead, status_code=201)
def add_exclusion(body: ExclusionCreate, session: SessionDep) -> ExclusionRead:
    value = normalize_exclusion(body.kind, body.value)
    if len(value) < 2:
        raise AppError(code="VALIDATION_ERROR", message="Enter a longer value.", status_code=422)
    existing = session.scalar(
        select(LeadExclusion).where(LeadExclusion.kind == body.kind, LeadExclusion.value == value)
    )
    if existing is not None:
        return ExclusionRead.model_validate(existing, from_attributes=True)
    row = LeadExclusion(kind=body.kind, value=value, note=body.note)
    session.add(row)
    session.flush()
    return ExclusionRead.model_validate(row, from_attributes=True)


@router.delete("/exclusions/{exclusion_id}", status_code=204)
def remove_exclusion(exclusion_id: UUID, session: SessionDep) -> None:
    row = session.get(LeadExclusion, exclusion_id)
    if row is None:
        raise AppError(code="NOT_FOUND", message="That exclusion was not found.", status_code=404)
    session.delete(row)


# ---------------------------------------------------------------------------- log


class RunRead(BaseModel):
    id: UUID
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    summary: dict[str, object] | None = None
    error: str | None = None


class FailedJobRead(BaseModel):
    id: UUID
    lead_id: UUID
    business_name: str | None = None
    step: str
    attempts: int
    last_error: str | None = None
    finished_at: datetime | None = None


class ActivityLog(BaseModel):
    runs: list[RunRead]
    failed_jobs: list[FailedJobRead]


@router.get("/log", response_model=ActivityLog)
def activity_log(session: SessionDep, limit: int = 40) -> ActivityLog:
    limit = max(1, min(limit, 200))
    runs = session.scalars(
        select(AutomationRun).order_by(AutomationRun.created_at.desc()).limit(limit)
    )
    failed = session.execute(
        select(PipelineJob, Lead.business_name)
        .join(Lead, Lead.id == PipelineJob.lead_id)
        .where(PipelineJob.status == "FAILED")
        .order_by(PipelineJob.updated_at.desc())
        .limit(20)
    ).all()
    return ActivityLog(
        runs=[RunRead.model_validate(r, from_attributes=True) for r in runs],
        failed_jobs=[
            FailedJobRead(
                id=job.id,
                lead_id=job.lead_id,
                business_name=name,
                step=job.step,
                attempts=job.attempts,
                last_error=job.last_error,
                finished_at=job.finished_at,
            )
            for job, name in failed
        ],
    )
