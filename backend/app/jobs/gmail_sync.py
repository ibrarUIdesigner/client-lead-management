import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app.services.gmail_sync import sync_all_gmail_accounts

logger = logging.getLogger(__name__)


def start_gmail_scheduler(app: FastAPI) -> BackgroundScheduler:
    settings = app.state.settings
    scheduler = BackgroundScheduler(timezone="UTC")
    minutes = settings.gmail_sync_interval_minutes
    scheduler.add_job(
        sync_all_gmail_accounts,
        IntervalTrigger(minutes=minutes),
        id="gmail_reply_sync",
        kwargs={
            "session_factory": app.state.session_factory,
            "settings": settings,
        },
        misfire_grace_time=minutes * 60,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("gmail_scheduler_started interval_minutes=%s", minutes)
    return scheduler
