from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db.session import check_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    database = "ok" if check_database(request.app.state.engine) else "unavailable"
    return HealthResponse(
        status="ok",
        service="client-acquisition-api",
        environment=settings.app_env,
        database=database,
    )
