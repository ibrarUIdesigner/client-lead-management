import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.enums import DiscoveryTrigger
from app.services.discovery import catch_up_daily_run, discovery_zone, start_discovery_run

logger = logging.getLogger(__name__)


def start_discovery_scheduler(app: FastAPI) -> BackgroundScheduler:
    settings = app.state.settings
    zone = discovery_zone(settings.discovery_timezone)
    scheduler = BackgroundScheduler(timezone=zone)
    scheduler.add_job(
        start_discovery_run,
        CronTrigger(hour=settings.discovery_hour, minute=0, timezone=zone),
        id="daily_lead_discovery",
        kwargs={
            "session_factory": app.state.session_factory,
            "settings": settings,
            "search_id": None,
            "trigger": DiscoveryTrigger.DAILY,
        },
        misfire_grace_time=60 * 60,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    threading.Thread(
        target=_catch_up,
        args=(app.state.session_factory, settings),
        name="discovery-catchup",
        daemon=True,
    ).start()
    logger.info(
        "discovery_scheduler_started hour=%s timezone=%s",
        settings.discovery_hour,
        zone.key,
    )
    return scheduler


def _catch_up(session_factory: sessionmaker[Session], settings: Settings) -> None:
    try:
        catch_up_daily_run(session_factory, settings)
    except Exception:
        logger.exception("discovery_catchup_failed")
