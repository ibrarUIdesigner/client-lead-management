import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.place_sources import PlaceSourceError, collect_places
from app.models.discovery import DiscoveryRun, DiscoverySearch
from app.models.enums import DiscoveryRunStatus, DiscoveryTrigger, LeadStatus
from app.models.lead import Lead
from app.repositories.activities import ActivityRepository
from app.schemas.discovery import (
    CategoryOption,
    DiscoverySearchCreate,
    DiscoverySearchRead,
    DiscoverySearchUpdate,
    DiscoveryStatus,
)
from app.schemas.values import slugify
from app.services.persistence import flush_or_reject
from app.services.place_listings import CATEGORIES, FoundBusiness

logger = logging.getLogger(__name__)

MAX_SEARCHES = 8
_state = threading.Lock()
_running = False


def discovery_is_running() -> bool:
    with _state:
        return _running


def _begin_run() -> bool:
    global _running
    with _state:
        if _running:
            return False
        _running = True
        return True


def _end_run() -> None:
    global _running
    with _state:
        _running = False


class DiscoveryService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def status(self, next_run_at: datetime | None) -> DiscoveryStatus:
        searches = list(
            self.session.scalars(select(DiscoverySearch).order_by(DiscoverySearch.created_at.asc()))
        )
        reads = [self._read(search) for search in searches]
        latest = self.session.scalar(
            select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).limit(1)
        )
        zone = discovery_zone(self.settings.discovery_timezone)
        hour = f"{self.settings.discovery_hour:02d}:00"
        return DiscoveryStatus(
            running=discovery_is_running(),
            google_configured=bool(self.settings.google_places_api_key.strip()),
            yelp_configured=bool(self.settings.yelp_api_key.strip()),
            schedule=f"Once a day at {hour} {zone.key}",
            next_run_at=next_run_at,
            categories=[CategoryOption(value=item.value, label=item.label) for item in CATEGORIES],
            searches=reads,
            latest_message=latest.message if latest else None,
        )

    def create_search(self, data: DiscoverySearchCreate) -> DiscoverySearchRead:
        total = self.session.scalar(select(func.count()).select_from(DiscoverySearch))
        if int(total or 0) >= MAX_SEARCHES:
            raise AppError(
                code="SEARCH_LIMIT",
                message="Eight saved searches is the limit. Remove one before adding another.",
                status_code=400,
            )
        search = DiscoverySearch(
            category=data.category,
            city=data.city,
            country=data.country,
            use_openstreetmap=data.use_openstreetmap,
            use_google=data.use_google,
            use_yelp=data.use_yelp,
            use_yell=data.use_yell,
            use_businesslist=data.use_businesslist,
            use_epages=data.use_epages,
        )
        self.session.add(search)
        flush_or_reject(self.session)
        self.session.refresh(search)
        return self._read(search)

    def update_search(self, search_id: UUID, data: DiscoverySearchUpdate) -> DiscoverySearchRead:
        search = self._require(search_id)
        if data.is_active is not None:
            search.is_active = data.is_active
        for field in (
            "use_openstreetmap",
            "use_google",
            "use_yelp",
            "use_yell",
            "use_businesslist",
            "use_epages",
        ):
            value = getattr(data, field)
            if value is not None:
                setattr(search, field, value)
        if not any(
            (
                search.use_openstreetmap,
                search.use_google,
                search.use_yelp,
                search.use_yell,
                search.use_businesslist,
                search.use_epages,
            )
        ):
            raise AppError(
                code="VALIDATION_ERROR",
                message="Choose at least one source.",
                status_code=422,
            )
        flush_or_reject(self.session)
        self.session.refresh(search)
        return self._read(search)

    def ensure_search(self, search_id: UUID) -> None:
        self._require(search_id)

    def delete_search(self, search_id: UUID) -> None:
        if discovery_is_running():
            raise AppError(
                code="SEARCH_RUNNING",
                message="Wait for the current search to finish before deleting it.",
                status_code=409,
            )
        search = self._require(search_id)
        self.session.delete(search)

    def _require(self, search_id: UUID) -> DiscoverySearch:
        search = self.session.get(DiscoverySearch, search_id)
        if search is None:
            raise AppError(
                code="SEARCH_NOT_FOUND",
                message="That search could not be found.",
                status_code=404,
            )
        return search

    def _read(self, search: DiscoverySearch) -> DiscoverySearchRead:
        run = self.session.scalar(
            select(DiscoveryRun)
            .where(DiscoveryRun.search_id == search.id)
            .order_by(DiscoveryRun.started_at.desc())
            .limit(1)
        )
        payload = DiscoverySearchRead.model_validate(search)
        if run is None:
            return payload
        return payload.model_copy(
            update={
                "last_status": run.status,
                "last_started_at": run.started_at,
                "last_finished_at": run.finished_at,
                "last_found_count": run.found_count,
                "last_created_count": run.created_count,
                "last_updated_count": run.updated_count,
                "last_skipped_count": run.skipped_count,
                "last_message": run.message,
            }
        )


def start_discovery_run(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    search_id: UUID | None,
    trigger: DiscoveryTrigger,
) -> str:
    """Return started, busy, empty, or skipped."""
    if not _begin_run():
        return "busy"
    try:
        run_ids = _prepare_runs(session_factory, settings, search_id=search_id, trigger=trigger)
    except Exception:
        _end_run()
        raise
    if not run_ids:
        _end_run()
        if trigger is DiscoveryTrigger.DAILY:
            return "skipped"
        return "empty"
    threading.Thread(
        target=_execute_runs,
        args=(session_factory, settings, run_ids),
        name="lead-discovery",
        daemon=True,
    ).start()
    return "started"


def catch_up_daily_run(session_factory: sessionmaker[Session], settings: Settings) -> None:
    zone = discovery_zone(settings.discovery_timezone)
    local_now = datetime.now(zone)
    if local_now.hour < settings.discovery_hour:
        return
    with session_factory() as session:
        if _daily_already_ran(session, settings) or _daily_failed_recently(session):
            return
        active = session.scalar(
            select(func.count())
            .select_from(DiscoverySearch)
            .where(DiscoverySearch.is_active.is_(True))
        )
        if int(active or 0) == 0:
            return
    start_discovery_run(
        session_factory,
        settings,
        search_id=None,
        trigger=DiscoveryTrigger.DAILY,
    )


def _prepare_runs(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    search_id: UUID | None,
    trigger: DiscoveryTrigger,
) -> list[UUID]:
    with session_factory() as session:
        _recover_stale_runs(session)
        if trigger is DiscoveryTrigger.DAILY and _daily_already_ran(session, settings):
            session.commit()
            return []
        if search_id is None:
            searches = list(
                session.scalars(
                    select(DiscoverySearch)
                    .where(DiscoverySearch.is_active.is_(True))
                    .order_by(DiscoverySearch.created_at.asc())
                )
            )
        else:
            search = session.get(DiscoverySearch, search_id)
            searches = [search] if search is not None else []
        if not searches:
            session.commit()
            return []
        now = datetime.now(UTC)
        run_ids: list[UUID] = []
        for search in searches:
            run = DiscoveryRun(
                search_id=search.id,
                trigger=trigger.value,
                status=DiscoveryRunStatus.RUNNING.value,
                started_at=now,
                message="Searching public business listings.",
            )
            session.add(run)
            session.flush()
            run_ids.append(run.id)
        session.commit()
        return run_ids


def _execute_runs(
    session_factory: sessionmaker[Session],
    settings: Settings,
    run_ids: list[UUID],
) -> None:
    try:
        with httpx.Client(timeout=35.0, follow_redirects=True) as client:
            for index, run_id in enumerate(run_ids):
                if index:
                    time.sleep(1.1)
                _execute_one(session_factory, settings, client, run_id)
    finally:
        _end_run()


def _execute_one(
    session_factory: sessionmaker[Session],
    settings: Settings,
    client: httpx.Client,
    run_id: UUID,
) -> None:
    with session_factory() as session:
        run = session.get(DiscoveryRun, run_id)
        if run is None:
            return
        search = session.get(DiscoverySearch, run.search_id)
        if search is None:
            run.status = DiscoveryRunStatus.FAILED.value
            run.finished_at = datetime.now(UTC)
            run.message = "The saved search was removed before it ran."
            session.commit()
            return
        category = search.category
        city = search.city
        country = search.country
        use_openstreetmap = search.use_openstreetmap
        use_google = search.use_google
        use_yelp = search.use_yelp
        use_yell = search.use_yell
        use_businesslist = search.use_businesslist
        use_epages = search.use_epages
    try:
        found, notes = collect_places(
            category=category,
            city=city,
            country=country,
            use_openstreetmap=use_openstreetmap,
            use_google=use_google,
            use_yelp=use_yelp,
            use_yell=use_yell,
            use_businesslist=use_businesslist,
            use_epages=use_epages,
            settings=settings,
            client=client,
        )
        created, updated, skipped = _save_businesses(session_factory, found, city)
        message = (
            f"Saved {created} new, updated {updated}, skipped {skipped} already on file. "
            + " ".join(notes)
        )
        _finish_run(
            session_factory,
            run_id,
            status=DiscoveryRunStatus.COMPLETED,
            found=len(found),
            created=created,
            updated=updated,
            skipped=skipped,
            message=message,
        )
    except PlaceSourceError as exc:
        _finish_run(
            session_factory,
            run_id,
            status=DiscoveryRunStatus.FAILED,
            found=0,
            created=0,
            updated=0,
            skipped=0,
            message=exc.message,
        )
    except Exception:
        logger.exception("discovery_run_failed")
        _finish_run(
            session_factory,
            run_id,
            status=DiscoveryRunStatus.FAILED,
            found=0,
            created=0,
            updated=0,
            skipped=0,
            message="The search stopped because of an unexpected error.",
        )


def _save_businesses(
    session_factory: sessionmaker[Session],
    found: list[FoundBusiness],
    fallback_city: str,
) -> tuple[int, int, int]:
    created = 0
    updated = 0
    skipped = 0
    seen_names: set[tuple[str, str]] = set()
    for business in found:
        name_key = (business.name.casefold(), (business.city or fallback_city).casefold())
        if name_key in seen_names:
            skipped += 1
            continue
        seen_names.add(name_key)
        with session_factory() as session:
            outcome = _save_one(session, business)
            if outcome == "created":
                created += 1
            elif outcome == "updated":
                updated += 1
            else:
                skipped += 1
    return created, updated, skipped


def _save_one(session: Session, business: FoundBusiness) -> str:
    existing = session.scalar(select(Lead).where(Lead.source_key == business.source_key))
    if existing is None:
        existing = session.scalar(
            select(Lead).where(
                func.lower(Lead.business_name) == business.name.casefold(),
                func.lower(func.coalesce(Lead.city, "")) == business.city.casefold(),
            )
        )
    if existing is None and business.phone:
        existing = session.scalar(select(Lead).where(Lead.phone == business.phone))
    if existing is None and business.website_url:
        existing = session.scalar(select(Lead).where(Lead.website_url == business.website_url))
    if existing is None:
        lead = Lead(
            business_name=business.name,
            slug=slugify(business.name),
            industry=business.industry,
            description=business.description,
            country=business.country,
            city=business.city,
            website_url=business.website_url,
            website_status=business.website_status,
            email=business.email,
            phone=business.phone,
            instagram_url=business.instagram_url,
            facebook_url=business.facebook_url,
            google_maps_url=business.google_maps_url,
            lead_score=business.lead_score,
            lead_status=LeadStatus.NEW.value,
            source=business.source,
            source_key=business.source_key,
            tags=business.tags,
            notes=business.notes,
        )
        session.add(lead)
        try:
            flush_or_reject(session)
        except AppError:
            session.rollback()
            return "skipped"
        ActivityRepository(session).add(
            lead.id,
            "lead_discovered",
            "Lead found",
            description=f"Found on {business.source.replace('_', ' ')}",
        )
        session.commit()
        return "created"
    discovered = existing.source in {
        "openstreetmap",
        "google_places",
        "yelp",
        "yell",
        "businesslist",
        "epages",
    }
    still_new = existing.lead_status == LeadStatus.NEW.value
    if not discovered or not still_new:
        return "skipped"
    changed = False
    gained_website = not existing.website_url and bool(business.website_url)
    for field in (
        "phone",
        "email",
        "website_url",
        "facebook_url",
        "instagram_url",
        "google_maps_url",
    ):
        if getattr(existing, field) in (None, "") and getattr(business, field):
            setattr(existing, field, getattr(business, field))
            changed = True
    if gained_website or (
        existing.website_status in (None, "missing") and business.website_status != "missing"
    ):
        existing.website_status = business.website_status
        existing.lead_score = business.lead_score
        existing.description = business.description
        changed = True
    if not changed:
        return "skipped"
    try:
        flush_or_reject(session)
    except AppError:
        session.rollback()
        return "skipped"
    session.commit()
    return "updated"


def _finish_run(
    session_factory: sessionmaker[Session],
    run_id: UUID,
    *,
    status: DiscoveryRunStatus,
    found: int,
    created: int,
    updated: int,
    skipped: int,
    message: str,
) -> None:
    with session_factory() as session:
        run = session.get(DiscoveryRun, run_id)
        if run is None:
            return
        run.status = status.value
        run.finished_at = datetime.now(UTC)
        run.found_count = found
        run.created_count = created
        run.updated_count = updated
        run.skipped_count = skipped
        run.message = message[:4000]
        session.commit()


def _recover_stale_runs(session: Session) -> None:
    cutoff = datetime.now(UTC) - timedelta(minutes=15)
    stale = session.scalars(
        select(DiscoveryRun).where(
            DiscoveryRun.status == DiscoveryRunStatus.RUNNING.value,
            DiscoveryRun.started_at < cutoff,
        )
    )
    for run in stale:
        run.status = DiscoveryRunStatus.FAILED.value
        run.finished_at = datetime.now(UTC)
        run.message = "The search stopped before it finished."


def _daily_failed_recently(session: Session) -> bool:
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    found = session.scalar(
        select(DiscoveryRun.id).where(
            DiscoveryRun.trigger == DiscoveryTrigger.DAILY.value,
            DiscoveryRun.status == DiscoveryRunStatus.FAILED.value,
            DiscoveryRun.started_at >= cutoff,
        )
    )
    return found is not None


def _daily_already_ran(session: Session, settings: Settings) -> bool:
    zone = discovery_zone(settings.discovery_timezone)
    local_now = datetime.now(zone)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    found = session.scalar(
        select(DiscoveryRun.id).where(
            DiscoveryRun.trigger == DiscoveryTrigger.DAILY.value,
            DiscoveryRun.status == DiscoveryRunStatus.COMPLETED.value,
            DiscoveryRun.started_at >= start,
        )
    )
    return found is not None


def discovery_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logger.warning("discovery_timezone_invalid timezone=%s", name)
        return ZoneInfo("UTC")
