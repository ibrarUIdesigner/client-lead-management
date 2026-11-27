"""Automation settings you edit in the app, exclusions, and the run log.

The config lives in ``app_settings`` as one JSON document. Environment variables
still provide safe defaults and hard ceilings. The first-email mode is stored with the
existing automation switches so there is one source of truth for "automatic or approval".
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.app_setting import AppSetting
from app.models.automation import AutomationRun, LeadExclusion
from app.models.enums import AutomationRunStatus, ExclusionKind
from app.models.lead import Lead

logger = logging.getLogger(__name__)

KEY_CONFIG = "automation_config"
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BUSINESS_TYPES = ("no_website", "outdated", "slow", "ux")


def _clean_list(values: list[str], limit: int = 100) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in values:
        value = " ".join(str(raw).split())[:120]
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            cleaned.append(value)
    return cleaned[:limit]


class AutomationConfig(BaseModel):
    paused: bool = False
    discovery_daily_limit: int = Field(default=50, ge=0, le=500)
    outreach_daily_limit: int = Field(default=10, ge=0, le=200)
    target_countries: list[str] = Field(default_factory=list)
    target_categories: list[str] = Field(default_factory=list)
    business_types: list[str] = Field(default_factory=lambda: list(BUSINESS_TYPES))
    min_score: int = Field(default=40, ge=0, le=100)
    followup_intervals: list[int] = Field(default_factory=lambda: [4, 10, 20])
    followup_max_attempts: int = Field(default=3, ge=0, le=6)
    report_time: str = "08:00"
    report_timezone: str = "UTC"
    report_email: str = ""
    outreach_mode: Literal["approval", "automatic"] = "approval"
    learning_enabled: bool = True
    pinned_categories: list[str] = Field(default_factory=list)
    pinned_countries: list[str] = Field(default_factory=list)
    excluded_countries: list[str] = Field(default_factory=list)

    @field_validator(
        "target_countries",
        "target_categories",
        "pinned_categories",
        "pinned_countries",
        "excluded_countries",
    )
    @classmethod
    def tidy_lists(cls, value: list[str]) -> list[str]:
        return _clean_list(value)

    @field_validator("business_types")
    @classmethod
    def known_types(cls, value: list[str]) -> list[str]:
        return [item for item in dict.fromkeys(value) if item in BUSINESS_TYPES]

    @field_validator("followup_intervals")
    @classmethod
    def intervals(cls, value: list[int]) -> list[int]:
        days = sorted({int(item) for item in value if 1 <= int(item) <= 90})
        return days[:6]

    @field_validator("report_time")
    @classmethod
    def report_time_format(cls, value: str) -> str:
        if not _TIME.match(value):
            raise ValueError("Use 24-hour HH:MM, for example 08:00.")
        return value

    @field_validator("report_timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("Unknown timezone.") from exc
        return value

    @field_validator("report_email")
    @classmethod
    def report_email_format(cls, value: str) -> str:
        value = value.strip()
        if value and not _EMAIL.match(value):
            raise ValueError("Enter a valid email address.")
        return value

    def sequence_days(self) -> list[int]:
        """Follow-up days after the first email, limited by the maximum attempts."""
        return self.followup_intervals[: self.followup_max_attempts]


def get_config(session: Session) -> AutomationConfig:
    from app.services.automation import get_flags

    row = session.get(AppSetting, KEY_CONFIG)
    stored = row.value if row is not None and isinstance(row.value, dict) else {}
    try:
        config = AutomationConfig.model_validate(stored)
    except Exception:
        logger.warning("automation_config_invalid_using_defaults")
        config = AutomationConfig()
    config.outreach_mode = "automatic" if get_flags(session)["auto_send_enabled"] else "approval"
    return config


def save_config(session: Session, config: AutomationConfig) -> AutomationConfig:
    from app.services.automation import set_flags

    data = config.model_dump()
    set_flags(session, {"auto_send_enabled": config.outreach_mode == "automatic"})
    row = session.get(AppSetting, KEY_CONFIG)
    if row is None:
        session.add(AppSetting(key=KEY_CONFIG, value=data))
    else:
        row.value = data
    session.flush()
    return config


def effective_settings(session: Session, settings: Settings) -> tuple[Settings, AutomationConfig]:
    """Settings with the values you edited in the app applied on top of the environment."""
    config = get_config(session)
    return settings.model_copy(update={"pipeline_min_score": config.min_score}), config


# --------------------------------------------------------------------- exclusions


class ExclusionSet:
    def __init__(self, rows: list[LeadExclusion]) -> None:
        self.domains = {r.value for r in rows if r.kind == ExclusionKind.DOMAIN.value}
        self.emails = {r.value for r in rows if r.kind == ExclusionKind.EMAIL.value}
        self.names = [r.value for r in rows if r.kind == ExclusionKind.NAME.value]
        self.categories = {r.value for r in rows if r.kind == ExclusionKind.CATEGORY.value}

    @classmethod
    def load(cls, session: Session) -> ExclusionSet:
        return cls(list(session.scalars(select(LeadExclusion))))

    def match(
        self,
        *,
        name: str | None,
        website: str | None,
        email: str | None,
        category: str | None,
    ) -> str | None:
        """Return the reason a business is excluded, or None."""
        email_value = (email or "").strip().casefold()
        if email_value:
            if email_value in self.emails:
                return f"Email {email_value} is excluded."
            domain = email_value.rpartition("@")[2]
            if _domain_listed(domain, self.domains):
                return f"Domain {domain} is excluded."
        host = _host(website)
        if host and _domain_listed(host, self.domains):
            return f"Domain {host} is excluded."
        name_value = (name or "").casefold()
        for fragment in self.names:
            if fragment in name_value:
                return f"Name matches excluded '{fragment}'."
        if category and category.strip().casefold() in self.categories:
            return f"Category {category} is excluded."
        return None

    def match_lead(self, lead: Lead) -> str | None:
        return self.match(
            name=lead.business_name,
            website=lead.website_url,
            email=lead.email,
            category=lead.industry,
        )


def _host(url: str | None) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if "//" not in value:
        value = "//" + value
    host = (urlparse(value).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _domain_listed(host: str, domains: set[str]) -> bool:
    host = host.casefold()
    return any(host == d or host.endswith("." + d) for d in domains)


def normalize_exclusion(kind: str, value: str) -> str:
    cleaned = " ".join(value.split()).strip().casefold()
    if kind == ExclusionKind.DOMAIN.value:
        cleaned = _host(cleaned) or cleaned.removeprefix("www.")
    return cleaned[:255]


# ---------------------------------------------------------------------- run log


def claim_run(
    session: Session, kind: str, run_key: str, now: datetime | None = None
) -> AutomationRun | None:
    """Create the run row. Returns None when that run already exists (duplicate)."""
    run = AutomationRun(
        kind=kind,
        run_key=run_key,
        status=AutomationRunStatus.RUNNING.value,
        started_at=now or datetime.now(UTC),
    )
    try:
        with session.begin_nested():
            session.add(run)
            session.flush()
    except Exception:
        return None
    return run


def finish_run(
    session: Session,
    run: AutomationRun,
    status: AutomationRunStatus,
    *,
    summary: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    run.status = status.value
    run.finished_at = datetime.now(UTC)
    run.summary = summary
    run.error = (error or "")[:2000] or None
    session.flush()


def another_tick_running(session: Session, window_minutes: int = 6) -> bool:
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    return (
        session.scalar(
            select(AutomationRun.id)
            .where(
                AutomationRun.kind == "tick",
                AutomationRun.status == AutomationRunStatus.RUNNING.value,
                AutomationRun.started_at > cutoff,
            )
            .limit(1)
        )
        is not None
    )


def mark_stale_runs(session: Session, older_than_minutes: int = 15) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
    rows = list(
        session.scalars(
            select(AutomationRun).where(
                AutomationRun.status == AutomationRunStatus.RUNNING.value,
                AutomationRun.started_at < cutoff,
            )
        )
    )
    for run in rows:
        run.status = AutomationRunStatus.FAILED.value
        run.finished_at = datetime.now(UTC)
        run.error = "Stopped before finishing (the function timed out or crashed)."
    return len(rows)
