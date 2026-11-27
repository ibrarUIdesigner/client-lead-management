"""Performance & Insights data and the daily report controls."""

from fastapi import APIRouter, Request

from app.api.deps import SessionDep
from app.services.automation_config import get_config
from app.services.daily_report import build_report, send_report
from app.services.insights import build_insights

router = APIRouter(tags=["insights"])


@router.get("/insights")
def insights(request: Request, session: SessionDep, days: int = 90) -> dict[str, object]:
    settings = request.app.state.settings
    return build_insights(session, settings, get_config(session), days=max(7, min(days, 365)))


@router.get("/automation/report/preview")
def preview_report(request: Request, session: SessionDep) -> dict[str, str]:
    settings = request.app.state.settings
    return build_report(session, settings, get_config(session))


@router.post("/automation/report/send")
def send_report_now(request: Request, session: SessionDep) -> dict[str, str]:
    """Send the report to your address right now, outside the daily schedule."""
    settings = request.app.state.settings
    return send_report(session, settings, get_config(session))
