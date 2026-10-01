import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.apify import ApifyClient
from app.models.apify import (
    ApifyConnector,
    ApifyDatasetItem,
    ApifyDismissedActor,
    ApifyImport,
    ApifyRun,
)
from app.models.enums import ApifyRunStatus, LeadStatus
from app.models.lead import Lead
from app.repositories.activities import ActivityRepository
from app.schemas.apify import (
    ApifyConnectorCreate,
    ApifyConnectorRead,
    ApifyImportRequest,
    ApifyImportResult,
    ApifyOverview,
    ApifyRunCreate,
    ApifyRunRead,
    DatasetItemRead,
    DatasetPageRead,
    PreviewField,
)
from app.schemas.values import slugify
from app.services.apify_mapping import (
    PreparedLead,
    build_fields,
    classify_import,
    coerce_input,
    connector_identity,
    extract_input_schema,
    item_collected_at,
    last_run_started_at,
    normalize_actor_ref,
    parse_timestamp,
    prepare_item,
    preview_fields,
    same_business,
    select_current_pricing,
    start_decision,
    summarize_pricing,
    validate_limits,
)

logger = logging.getLogger(__name__)

_STATUSES = {status.value for status in ApifyRunStatus}

ACTIVE_STATUSES = {
    ApifyRunStatus.READY.value,
    ApifyRunStatus.RUNNING.value,
    ApifyRunStatus.TIMING_OUT.value,
    ApifyRunStatus.ABORTING.value,
}
TERMINAL_STATUSES = {
    ApifyRunStatus.SUCCEEDED.value,
    ApifyRunStatus.FAILED.value,
    ApifyRunStatus.TIMED_OUT.value,
    ApifyRunStatus.ABORTED.value,
}
DATASET_PAGE_SIZE = 100
DATASET_PAGE_LIMIT = 40
SCHEMA_LOADED = "x-schema-loaded"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class ApifyService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        client: ApifyClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.client = client

    def overview(self) -> ApifyOverview:
        owns_client = self.client is None
        try:
            return self._overview()
        finally:
            if owns_client and self.client is not None:
                self.client.close()
                self.client = None

    def _overview(self) -> ApifyOverview:
        token_error = self._refresh_active_runs()
        remote_last, sync_error = self._sync_account()
        if token_error is None:
            token_error = sync_error
        connectors = list(self.session.scalars(select(ApifyConnector)))
        runs = list(
            self.session.scalars(
                select(ApifyRun).order_by(ApifyRun.started_at.desc()).limit(50)
            )
        )
        latest = self._latest_by_connector()
        active = set(
            self.session.scalars(
                select(ApifyRun.connector_id).where(ApifyRun.status.in_(tuple(ACTIVE_STATUSES)))
            )
        )
        names = {connector.id: connector.display_name for connector in connectors}
        actor_ids = {connector.id: connector.actor_id for connector in connectors}
        connectors.sort(
            key=lambda connector: _sort_stamp(connector, latest, remote_last),
            reverse=True,
        )
        return ApifyOverview(
            token_configured=bool(self.settings.apify_token),
            token_error=token_error,
            connectors=[
                self._connector_read(
                    connector,
                    latest.get(connector.id),
                    connector.id in active,
                    remote_last.get(connector.actor_id),
                )
                for connector in connectors
            ],
            runs=[
                self._run_read(
                    run,
                    names.get(run.connector_id, "Removed connector"),
                    actor_ids.get(run.connector_id, ""),
                )
                for run in runs
            ],
        )

    def create_connector(self, data: ApifyConnectorCreate) -> ApifyConnectorRead:
        client = self._require_client()
        actor_ref = normalize_actor_ref(data.actor_id)
        actor = client.get_actor(actor_ref)
        actor_id = actor.get("id")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise AppError(
                code="APIFY_ERROR",
                message="Apify returned an unexpected actor record.",
                status_code=502,
            )
        try:
            schema = extract_input_schema(client.get_default_build(actor_id))
        except AppError as exc:
            if exc.status_code != 404:
                raise
            schema = {"type": "object", "properties": {}}
        existing = self.session.scalar(
            select(ApifyConnector).where(ApifyConnector.actor_id == actor_id)
        )
        if existing is not None:
            raise AppError(
                code="CONNECTOR_EXISTS",
                message="That actor is already connected.",
                status_code=409,
            )
        _title, source, description = connector_identity(actor)
        self._clear_dismissed(actor_id)
        connector = ApifyConnector(
            display_name=data.display_name,
            actor_id=actor_id,
            source=source,
            description=description,
            input_schema=_loaded_schema(schema),
            pricing=select_current_pricing(actor.get("pricingInfos")),
        )
        self.session.add(connector)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise AppError(
                code="CONNECTOR_EXISTS",
                message="That actor is already connected.",
                status_code=409,
            ) from exc
        return self._connector_read(connector, None, False, None)

    def delete_connector(self, connector_id: UUID) -> None:
        connector = self._require_connector(connector_id)
        active = self.session.scalar(
            select(ApifyRun.id).where(
                ApifyRun.connector_id == connector.id,
                ApifyRun.status.in_(tuple(ACTIVE_STATUSES)),
            )
        )
        if active is not None:
            raise AppError(
                code="RUN_IN_PROGRESS",
                message="Wait until the current run finishes before removing this connector.",
                status_code=409,
            )
        self._remember_dismissed(connector.actor_id)
        self.session.delete(connector)

    def start_run(self, connector_id: UUID, data: ApifyRunCreate) -> ApifyRunRead:
        connector = self._require_connector(connector_id)
        self.session.execute(
            select(ApifyConnector).where(ApifyConnector.id == connector.id).with_for_update()
        )
        existing = self._run_for_request(connector.id, data.client_request_id)
        active = self.session.scalar(
            select(ApifyRun.id).where(
                ApifyRun.connector_id == connector.id,
                ApifyRun.status.in_(tuple(ACTIVE_STATUSES)),
            )
        )
        decision = start_decision(
            existing_request=existing is not None,
            active_run=active is not None,
        )
        if decision == "replay" and existing is not None:
            return self._run_read(existing, connector.display_name, connector.actor_id)
        if decision == "blocked":
            raise AppError(
                code="RUN_IN_PROGRESS",
                message="This actor already has a run in progress.",
                status_code=409,
            )
        self._ensure_input_schema(connector)
        pricing = summarize_pricing(connector.pricing)
        validate_limits(pricing, data.max_items, data.max_total_charge_usd)
        run_input = coerce_input(connector.input_schema, data.input)
        remote = self._require_client().start_run(
            connector.actor_id,
            run_input,
            max_items=data.max_items if pricing.supports_max_items else None,
            max_total_charge_usd=(
                data.max_total_charge_usd if pricing.supports_max_charge else None
            ),
        )
        run = self._run_from_remote(
            connector,
            remote,
            run_input=run_input,
            max_items=data.max_items,
            max_total_charge_usd=data.max_total_charge_usd,
            client_request_id=data.client_request_id,
        )
        self.session.add(run)
        self.session.flush()
        return self._run_read(run, connector.display_name, connector.actor_id)

    def refresh_run(self, run_id: UUID) -> ApifyRunRead:
        run = self._require_run(run_id)
        if run.status in ACTIVE_STATUSES:
            self._refresh(run)
        return self._run_read(run, run.connector.display_name, run.connector.actor_id)

    def abort_run(self, run_id: UUID) -> ApifyRunRead:
        run = self._require_run(run_id)
        if run.status not in {ApifyRunStatus.READY.value, ApifyRunStatus.RUNNING.value}:
            raise AppError(
                code="RUN_NOT_ACTIVE",
                message="Only a starting or running actor can be aborted.",
                status_code=409,
            )
        remote = self._require_client().abort_run(run.apify_run_id)
        self._apply_remote(run, remote)
        return self._run_read(run, run.connector.display_name, run.connector.actor_id)

    def list_items(self, run_id: UUID, *, offset: int, limit: int) -> DatasetPageRead:
        run = self._require_run(run_id)
        if run.status not in TERMINAL_STATUSES:
            raise AppError(
                code="RUN_NOT_READY",
                message="Results are available after the run finishes.",
                status_code=409,
            )
        items, total = self._require_client().dataset_items(
            run.apify_run_id,
            offset=offset,
            limit=limit,
        )
        run.result_count = total
        fallback = run.finished_at or run.started_at
        reads: list[DatasetItemRead] = []
        for index, item in enumerate(items):
            prepared = self._remember_item(
                run,
                item,
                position=offset + index,
                fallback=fallback,
            )
            reads.append(_item_read(prepared, item))
        return DatasetPageRead(
            items=reads,
            offset=offset,
            limit=limit,
            total=total,
            has_next=offset + len(items) < total,
        )

    def import_items(self, run_id: UUID, data: ApifyImportRequest) -> ApifyImportResult:
        run = self._require_run(run_id)
        if run.status not in TERMINAL_STATUSES:
            raise AppError(
                code="RUN_NOT_READY",
                message="Wait until the run finishes before importing.",
                status_code=409,
            )
        payloads = self._payloads_for_keys(run, set(data.item_keys))
        created = 0
        skipped = 0
        seen: set[str] = set()
        for key in data.item_keys:
            payload = payloads.get(key)
            if payload is None or key in seen:
                skipped += 1
                continue
            seen.add(key)
            prepared = prepare_item(
                payload,
                actor_id=run.connector.actor_id,
                collected_at=item_collected_at(payload, run.finished_at or run.started_at),
            )
            if prepared.source_key != key:
                skipped += 1
                continue
            outcome = self._save_import(run, prepared)
            if outcome == "create":
                created += 1
            else:
                skipped += 1
        return ApifyImportResult(created=created, skipped=skipped)

    def _save_import(self, run: ApifyRun, prepared: PreparedLead) -> str:
        provenance = self.session.scalar(
            select(ApifyImport).where(ApifyImport.source_key == prepared.source_key)
        )
        lead = self._matching_lead(prepared)
        action = classify_import(
            provenance_exists=provenance is not None,
            lead_exists=lead is not None,
        )
        if action == "skip":
            return "skip"
        if action == "attach" and lead is not None:
            try:
                with self.session.begin_nested():
                    self._add_provenance(run, lead, prepared)
                    self._add_activity(lead, prepared, run, matched=True)
                    self.session.flush()
            except IntegrityError:
                logger.warning("apify_import_attached_skipped source_key=%s", prepared.source_key)
            return "skip"
        lead = Lead(
            business_name=prepared.business_name,
            slug=slugify(prepared.business_name),
            industry=prepared.industry,
            description=prepared.description,
            country=prepared.country,
            city=prepared.city,
            website_url=prepared.website_url,
            email=prepared.email,
            phone=prepared.phone,
            linkedin_url=prepared.linkedin_url,
            instagram_url=prepared.instagram_url,
            facebook_url=prepared.facebook_url,
            google_maps_url=prepared.google_maps_url,
            lead_status=LeadStatus.NEW.value,
            source="apify",
            source_key=prepared.source_key,
            tags=["apify"],
        )
        try:
            with self.session.begin_nested():
                self.session.add(lead)
                self.session.flush()
                self._add_provenance(run, lead, prepared)
                self._add_activity(lead, prepared, run, matched=False)
                self.session.flush()
        except IntegrityError:
            logger.warning("apify_import_skipped source_key=%s", prepared.source_key)
            return "skip"
        return "create"

    def _matching_lead(self, prepared: PreparedLead) -> Lead | None:
        by_key = self.session.scalar(select(Lead).where(Lead.source_key == prepared.source_key))
        if by_key is not None:
            return by_key
        if prepared.website_url:
            by_site = self.session.scalar(
                select(Lead).where(Lead.website_url == prepared.website_url)
            )
            if by_site is not None and same_business(
                prepared.source_key,
                prepared.website_url,
                prepared.google_maps_url,
                existing_source_key=by_site.source_key,
                existing_website_url=by_site.website_url,
                existing_google_maps_url=by_site.google_maps_url,
            ):
                return by_site
        if prepared.google_maps_url:
            by_maps = self.session.scalar(
                select(Lead).where(Lead.google_maps_url == prepared.google_maps_url)
            )
            if by_maps is not None:
                return by_maps
        return None

    def _add_provenance(self, run: ApifyRun, lead: Lead, prepared: PreparedLead) -> None:
        self.session.add(
            ApifyImport(
                lead_id=lead.id,
                run_id=run.id,
                actor_id=run.connector.actor_id,
                apify_run_id=run.apify_run_id,
                source_url=prepared.source_url,
                source_key=prepared.source_key,
                collected_at=prepared.collected_at,
            )
        )

    def _add_activity(
        self,
        lead: Lead,
        prepared: PreparedLead,
        run: ApifyRun,
        *,
        matched: bool,
    ) -> None:
        collected = prepared.collected_at.date().isoformat()
        source = prepared.source_url or "no source URL"
        ActivityRepository(self.session).add(
            lead.id,
            "lead_imported",
            "Matched an Apify record" if matched else "Imported from Apify",
            description=(
                f"Collected {collected} from {source}. "
                f"Actor {run.connector.actor_id}, run {run.apify_run_id}."
            ),
            details={
                "actor_id": run.connector.actor_id,
                "apify_run_id": run.apify_run_id,
                "source_url": prepared.source_url,
                "collected_at": prepared.collected_at.isoformat(),
            },
        )

    def _payloads_for_keys(
        self,
        run: ApifyRun,
        keys: set[str],
    ) -> dict[str, dict[str, object]]:
        rows = self.session.scalars(
            select(ApifyDatasetItem).where(
                ApifyDatasetItem.run_id == run.id,
                ApifyDatasetItem.item_key.in_(keys),
            )
        )
        found: dict[str, dict[str, object]] = {}
        for row in rows:
            if isinstance(row.payload, dict):
                found[row.item_key] = row.payload
        missing = keys - set(found)
        if not missing:
            return found
        client = self._require_client()
        offset = 0
        fallback = run.finished_at or run.started_at
        for _ in range(DATASET_PAGE_LIMIT):
            items, total = client.dataset_items(
                run.apify_run_id,
                offset=offset,
                limit=DATASET_PAGE_SIZE,
            )
            run.result_count = total
            if not items:
                break
            for index, item in enumerate(items):
                prepared = self._remember_item(
                    run,
                    item,
                    position=offset + index,
                    fallback=fallback,
                )
                if prepared.source_key in missing:
                    found[prepared.source_key] = item
                    missing.discard(prepared.source_key)
            if not missing or offset + len(items) >= total:
                break
            offset += DATASET_PAGE_SIZE
        return found

    def _remember_item(
        self,
        run: ApifyRun,
        item: dict[str, object],
        *,
        position: int,
        fallback: datetime,
    ) -> PreparedLead:
        prepared = prepare_item(
            item,
            actor_id=run.connector.actor_id,
            collected_at=item_collected_at(item, fallback),
        )
        existing = self.session.scalar(
            select(ApifyDatasetItem).where(
                ApifyDatasetItem.run_id == run.id,
                ApifyDatasetItem.item_key == prepared.source_key,
            )
        )
        if existing is None:
            try:
                with self.session.begin_nested():
                    self.session.add(
                        ApifyDatasetItem(
                            run_id=run.id,
                            item_key=prepared.source_key,
                            position=position,
                            source_url=prepared.source_url,
                            collected_at=prepared.collected_at,
                            payload=item,
                        )
                    )
                    self.session.flush()
            except IntegrityError:
                logger.warning("apify_item_duplicate run_id=%s", run.id)
        return prepared

    def _refresh_active_runs(self) -> str | None:
        if not self.settings.apify_token and self.client is None:
            return None
        runs = list(
            self.session.scalars(select(ApifyRun).where(ApifyRun.status.in_(tuple(ACTIVE_STATUSES))))
        )
        if not runs:
            return None
        try:
            client = self._require_client()
        except AppError as exc:
            return exc.message
        token_error: str | None = None
        for run in runs:
            try:
                self._refresh(run, client)
            except AppError as exc:
                if exc.code == "APIFY_UNAUTHORIZED":
                    token_error = exc.message
                    break
                logger.warning("apify_refresh_failed run_id=%s code=%s", run.id, exc.code)
        return token_error

    def _refresh(self, run: ApifyRun, client: ApifyClient | None = None) -> None:
        remote = (client or self._require_client()).get_run(run.apify_run_id)
        was_active = run.status in ACTIVE_STATUSES
        self._apply_remote(run, remote)
        if was_active and run.status in TERMINAL_STATUSES and run.result_count is None:
            try:
                _items, total = (client or self._require_client()).dataset_items(
                    run.apify_run_id,
                    offset=0,
                    limit=1,
                )
            except AppError:
                logger.warning("apify_result_count_failed run_id=%s", run.id)
                return
            run.result_count = total

    def _apply_remote(self, run: ApifyRun, remote: dict[str, object]) -> None:
        status = remote.get("status")
        if isinstance(status, str) and status in _STATUSES:
            run.status = status
        message = remote.get("statusMessage")
        if isinstance(message, str):
            run.status_message = message[:4000] or None
        finished = parse_timestamp(remote.get("finishedAt"))
        if finished is not None:
            run.finished_at = finished
        started = parse_timestamp(remote.get("startedAt"))
        if started is not None:
            run.started_at = started
        usage = remote.get("usageTotalUsd")
        if isinstance(usage, (int, float)) and not isinstance(usage, bool):
            run.usage_total_usd = Decimal(str(usage))
        dataset_id = remote.get("defaultDatasetId")
        if isinstance(dataset_id, str):
            run.default_dataset_id = dataset_id

    def _run_from_remote(
        self,
        connector: ApifyConnector,
        remote: dict[str, object],
        *,
        run_input: dict[str, object],
        max_items: int | None,
        max_total_charge_usd: float | None,
        client_request_id: str | None,
    ) -> ApifyRun:
        apify_run_id = remote.get("id")
        if not isinstance(apify_run_id, str) or not apify_run_id.strip():
            raise AppError(
                code="APIFY_ERROR",
                message="Apify returned an unexpected run record.",
                status_code=502,
            )
        status = remote.get("status")
        if not isinstance(status, str) or status not in _STATUSES:
            status = ApifyRunStatus.RUNNING.value
        started = parse_timestamp(remote.get("startedAt")) or datetime.now(UTC)
        usage = remote.get("usageTotalUsd")
        return ApifyRun(
            connector_id=connector.id,
            apify_run_id=apify_run_id,
            client_request_id=client_request_id,
            status=status,
            status_message=(
                remote["statusMessage"][:4000]
                if isinstance(remote.get("statusMessage"), str)
                else None
            ),
            run_input=run_input,
            max_items=max_items,
            max_total_charge_usd=(
                None if max_total_charge_usd is None else Decimal(str(max_total_charge_usd))
            ),
            started_at=started,
            finished_at=parse_timestamp(remote.get("finishedAt")),
            usage_total_usd=(
                Decimal(str(usage))
                if isinstance(usage, (int, float)) and not isinstance(usage, bool)
                else None
            ),
            default_dataset_id=(
                remote["defaultDatasetId"]
                if isinstance(remote.get("defaultDatasetId"), str)
                else None
            ),
        )

    def _latest_by_connector(self) -> dict[UUID, ApifyRun]:
        started = (
            select(
                ApifyRun.connector_id,
                func.max(ApifyRun.started_at).label("started_at"),
            )
            .group_by(ApifyRun.connector_id)
            .subquery()
        )
        rows = self.session.scalars(
            select(ApifyRun).join(
                started,
                (ApifyRun.connector_id == started.c.connector_id)
                & (ApifyRun.started_at == started.c.started_at),
            )
        )
        return {row.connector_id: row for row in rows}

    def _run_for_request(self, connector_id: UUID, request_id: str | None) -> ApifyRun | None:
        if not request_id:
            return None
        return self.session.scalar(
            select(ApifyRun).where(
                ApifyRun.connector_id == connector_id,
                ApifyRun.client_request_id == request_id,
            )
        )

    def _require_connector(self, connector_id: UUID) -> ApifyConnector:
        connector = self.session.get(ApifyConnector, connector_id)
        if connector is None:
            raise AppError(
                code="CONNECTOR_NOT_FOUND",
                message="That connector could not be found.",
                status_code=404,
            )
        return connector

    def _require_run(self, run_id: UUID) -> ApifyRun:
        run = self.session.get(ApifyRun, run_id)
        if run is None:
            raise AppError(
                code="RUN_NOT_FOUND",
                message="That run could not be found.",
                status_code=404,
            )
        return run

    def _require_client(self) -> ApifyClient:
        if self.client is not None:
            return self.client
        if not self.settings.apify_token:
            raise AppError(
                code="APIFY_NOT_CONFIGURED",
                message="Set APIFY_TOKEN on the server before using Apify.",
                status_code=503,
            )
        self.client = ApifyClient(self.settings.apify_token, base_url=self.settings.apify_api_base)
        return self.client

    def _sync_account(self) -> tuple[dict[str, datetime], str | None]:
        if not self.settings.apify_token and self.client is None:
            return {}, None
        try:
            client = self._require_client()
            summaries = client.list_actors()
        except AppError as exc:
            return {}, exc.message
        remote_last: dict[str, datetime] = {}
        dismissed = set(self.session.scalars(select(ApifyDismissedActor.actor_id)))
        for summary in summaries:
            actor_id = summary.get("id")
            if not isinstance(actor_id, str) or not actor_id.strip():
                continue
            started = parse_timestamp(last_run_started_at(summary))
            if started is not None:
                remote_last[actor_id] = started
            if actor_id in dismissed:
                continue
            try:
                self._ensure_account_connector(client, actor_id)
            except AppError as exc:
                if exc.code == "APIFY_UNAUTHORIZED":
                    return remote_last, exc.message
                logger.warning("apify_actor_sync_failed actor_id=%s code=%s", actor_id, exc.code)
        try:
            self._import_account_runs(client)
        except AppError as exc:
            return remote_last, exc.message
        return remote_last, None

    def _ensure_account_connector(self, client: ApifyClient, actor_id: str) -> None:
        existing = self.session.scalar(
            select(ApifyConnector.id).where(ApifyConnector.actor_id == actor_id)
        )
        if existing is not None:
            return
        actor = client.get_actor(actor_id)
        canonical_id = actor.get("id")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            return
        if self.session.scalar(
            select(ApifyConnector.id).where(ApifyConnector.actor_id == canonical_id)
        ):
            return
        if self.session.scalar(
            select(ApifyDismissedActor.id).where(ApifyDismissedActor.actor_id == canonical_id)
        ):
            return
        try:
            schema = extract_input_schema(client.get_default_build(canonical_id))
        except AppError as exc:
            if exc.status_code != 404:
                raise
            schema = {"type": "object", "properties": {}}
        display_name, source, description = connector_identity(actor)
        try:
            with self.session.begin_nested():
                self.session.add(
                    ApifyConnector(
                        display_name=display_name,
                        actor_id=canonical_id,
                        source=source or canonical_id,
                        description=description,
                        input_schema=_loaded_schema(schema),
                        pricing=select_current_pricing(actor.get("pricingInfos")),
                    )
                )
                self.session.flush()
        except IntegrityError:
            logger.warning("apify_connector_exists actor_id=%s", canonical_id)

    def _import_account_runs(self, client: ApifyClient) -> None:
        for remote in client.list_runs(limit=50):
            apify_run_id = remote.get("id")
            act_id = remote.get("actId")
            if not isinstance(apify_run_id, str) or not isinstance(act_id, str):
                continue
            if self.session.scalar(
                select(ApifyRun.id).where(ApifyRun.apify_run_id == apify_run_id)
            ):
                continue
            connector = self.session.scalar(
                select(ApifyConnector).where(ApifyConnector.actor_id == act_id)
            )
            if connector is None:
                continue
            run = self._run_from_remote(
                connector,
                remote,
                run_input={},
                max_items=None,
                max_total_charge_usd=None,
                client_request_id=None,
            )
            if run.status in TERMINAL_STATUSES:
                try:
                    _items, total = client.dataset_items(apify_run_id, offset=0, limit=1)
                except AppError:
                    logger.warning("apify_result_count_failed run_id=%s", apify_run_id)
                else:
                    run.result_count = total
            try:
                with self.session.begin_nested():
                    self.session.add(run)
                    self.session.flush()
            except IntegrityError:
                logger.warning("apify_run_exists apify_run_id=%s", apify_run_id)

    def _ensure_input_schema(self, connector: ApifyConnector) -> None:
        schema = connector.input_schema if isinstance(connector.input_schema, dict) else {}
        if schema.get(SCHEMA_LOADED) is True:
            return
        try:
            loaded = extract_input_schema(
                self._require_client().get_default_build(connector.actor_id)
            )
        except AppError as exc:
            if exc.status_code != 404:
                raise
            loaded = {"type": "object", "properties": {}}
        connector.input_schema = _loaded_schema(loaded)
        self.session.flush()

    def _remember_dismissed(self, actor_id: str) -> None:
        exists = self.session.scalar(
            select(ApifyDismissedActor.id).where(ApifyDismissedActor.actor_id == actor_id)
        )
        if exists is None:
            self.session.add(ApifyDismissedActor(actor_id=actor_id))

    def _clear_dismissed(self, actor_id: str) -> None:
        dismissed = self.session.scalar(
            select(ApifyDismissedActor).where(ApifyDismissedActor.actor_id == actor_id)
        )
        if dismissed is not None:
            self.session.delete(dismissed)

    def _connector_read(
        self,
        connector: ApifyConnector,
        last_run: ApifyRun | None,
        has_active_run: bool,
        remote_last_run_at: datetime | None,
    ) -> ApifyConnectorRead:
        schema = connector.input_schema if isinstance(connector.input_schema, dict) else {}
        pricing = connector.pricing if isinstance(connector.pricing, dict) else None
        last_run_at = last_run.started_at if last_run else remote_last_run_at
        return ApifyConnectorRead(
            id=connector.id,
            display_name=connector.display_name,
            source=connector.source,
            description=connector.description,
            actor_id=connector.actor_id,
            last_run_at=last_run_at,
            last_run_status=last_run.status if last_run else None,
            has_active_run=has_active_run,
            pricing=summarize_pricing(pricing),
            fields=[
                field
                for field in build_fields(schema)
                if field.field_type != "hidden"
            ],
        )

    def _run_read(self, run: ApifyRun, connector_name: str, actor_id: str) -> ApifyRunRead:
        return ApifyRunRead(
            id=run.id,
            connector_id=run.connector_id,
            connector_name=connector_name,
            actor_id=actor_id,
            apify_run_id=run.apify_run_id,
            status=run.status,
            status_message=run.status_message,
            started_at=run.started_at,
            finished_at=run.finished_at,
            result_count=run.result_count,
            usage_total_usd=_money(run.usage_total_usd),
            max_items=run.max_items,
            max_total_charge_usd=_money(run.max_total_charge_usd),
        )


def _item_read(prepared: PreparedLead, item: dict[str, object]) -> DatasetItemRead:
    return DatasetItemRead(
        item_key=prepared.source_key,
        title=prepared.business_name,
        source_url=prepared.source_url,
        detail=prepared.detail,
        collected_at=prepared.collected_at,
        fields=[PreviewField(label=label, value=value) for label, value in preview_fields(item)],
    )


def _loaded_schema(schema: dict[str, object]) -> dict[str, object]:
    return {**schema, SCHEMA_LOADED: True}


def _sort_stamp(
    connector: ApifyConnector,
    latest: dict[UUID, ApifyRun],
    remote_last: dict[str, datetime],
) -> datetime:
    stamps: list[datetime] = []
    last_run = latest.get(connector.id)
    if last_run is not None:
        stamps.append(last_run.started_at)
    remote = remote_last.get(connector.actor_id)
    if remote is not None:
        stamps.append(remote)
    return max(stamps) if stamps else _EPOCH


def _money(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)
