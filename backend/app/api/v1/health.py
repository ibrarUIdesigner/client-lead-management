from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db.session import check_database
from app.services.outreach_ai import provider_ready, resolve_email_provider

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str
    database: Literal["ok", "unavailable"]
    email_drafts: Literal["gemini", "groq", "unconfigured"]
    gemini: Literal["ready", "missing"]
    groq: Literal["ready", "missing"]


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    database = "ok" if check_database(request.app.state.engine) else "unavailable"
    provider = resolve_email_provider(settings)
    drafts: Literal["gemini", "groq", "unconfigured"]
    if provider == "gemini":
        drafts = "gemini"
    elif provider == "groq":
        drafts = "groq"
    else:
        drafts = "unconfigured"
    return HealthResponse(
        status="ok",
        service="client-acquisition-api",
        environment=settings.app_env,
        database=database,
        email_drafts=drafts,
        gemini="ready" if provider_ready(settings, "gemini") else "missing",
        groq="ready" if provider_ready(settings, "groq") else "missing",
    )
