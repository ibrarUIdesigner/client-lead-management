import os

from fastapi import APIRouter, HTTPException, Request

from app.models.enums import DiscoveryTrigger
from app.services.discovery import start_discovery_run
from app.services.gmail_sync import sync_all_gmail_accounts

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _require_cron(request: Request) -> None:
    secret = os.environ.get("CRON_SECRET", "")
    authorization = request.headers.get("authorization", "")
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/discovery")
def run_discovery(request: Request) -> dict[str, str]:
    _require_cron(request)
    settings = request.app.state.settings
    if not settings.discovery_enabled:
        return {"status": "disabled"}
    status = start_discovery_run(
        request.app.state.session_factory,
        settings,
        search_id=None,
        trigger=DiscoveryTrigger.DAILY,
        wait=True,
    )
    return {"status": status}


@router.get("/gmail-sync")
def run_gmail_sync(request: Request) -> dict[str, str]:
    _require_cron(request)
    settings = request.app.state.settings
    if not settings.gmail_sync_enabled:
        return {"status": "disabled"}
    sync_all_gmail_accounts(request.app.state.session_factory, settings)
    return {"status": "ok"}
