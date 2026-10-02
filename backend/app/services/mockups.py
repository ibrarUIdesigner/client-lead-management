"""Homepage mockup generation: brief, AI HTML, validation, screenshots, versions."""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.design_guide import DesignGuide
from app.models.enums import AuditStatus, MockupStatus
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.website_audit import WebsiteAudit
from app.schemas.design_guides import (
    MockupCreate,
    MockupCreated,
    MockupDetail,
    MockupGuideRead,
    MockupRefine,
    MockupRetry,
)
from app.services.design_markdown import (
    parse_markdown,
    snapshot_choice,
    verified_finding_lines,
)
from app.services.mockup_ai import (
    MockupGoal,
    MockupProvider,
    build_generation_brief,
    generate_homepage_html,
    resolve_mockup_provider,
)
from app.services.mockup_capture import MockupCaptureError, capture_mockup_html
from app.services.mockup_eligibility import evaluate_mockup_eligibility, require_mockup_eligibility
from app.services.mockup_html import wrap_for_srcdoc
from app.services.storage import (
    mockup_asset_key,
    mockup_screenshot_key,
    read_storage_file,
    save_bytes,
    save_screenshot,
)

logger = logging.getLogger(__name__)

MAX_ASSET_BYTES = 1_500_000
MAX_ASSETS = 4
_ALLOWED_ASSET_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class MockupService:
    def __init__(self, session: Session, settings: Settings, storage_dir: Path | None = None) -> None:
        self.session = session
        self.settings = settings
        self.storage_dir = storage_dir or settings.storage_dir

    def create(
        self,
        data: MockupCreate,
        *,
        assets: list[tuple[str, bytes, str | None]] | None = None,
    ) -> MockupCreated:
        if data.provider not in {"gemini", "groq"}:
            raise AppError(
                code="VALIDATION_ERROR",
                message="Choose Gemini or Groq.",
                status_code=422,
            )
        lead = self._lead(data.lead_id)
        source = self._source(data.source_mockup_id, data.lead_id, required_for_keep=data.guide_mode == "keep")
        guide_id, guide_name, snapshot = self._resolve_guide(data, source)
        audit, findings = self._latest_findings(lead.id)
        eligibility = require_mockup_eligibility(lead, audit)
        version = self._next_version(lead.id)
        brief = self._brief_for_lead(
            lead=lead,
            findings=findings,
            requirements=data.requirements,
            guidance=snapshot,
            goal=data.goal,  # type: ignore[arg-type]
            asset_labels=[],
            scenario=eligibility.scenario,
            design_score=eligibility.design_score,
        )
        mockup = Mockup(
            lead_id=lead.id,
            audit_id=audit.id if audit is not None else None,
            title="Homepage concept",
            status=MockupStatus.GENERATING.value,
            prompt=brief,
            provider=data.provider,
            goal=data.goal,
            version=version,
            notes="Generating homepage…",
            design_guide_id=guide_id,
            design_guide_name=guide_name,
            design_guide_snapshot=snapshot,
            source_mockup_id=source.id if source is not None else None,
            screenshot_status="PENDING",
            asset_refs=[],
        )
        self.session.add(mockup)
        self.session.flush()
        if assets:
            mockup.asset_refs = self._store_assets(lead.id, mockup.id, assets)
            mockup.prompt = self._brief_for_lead(
                lead=lead,
                findings=findings,
                requirements=data.requirements,
                guidance=snapshot,
                goal=data.goal,  # type: ignore[arg-type]
                asset_labels=self._asset_labels(mockup.asset_refs),
                scenario=eligibility.scenario,
                design_score=eligibility.design_score,
            )
            self.session.flush()
        return MockupCreated.from_mockup(mockup)

    def refine(self, mockup_id: UUID, data: MockupRefine) -> MockupCreated:
        source = self._get(mockup_id)
        if source.status != MockupStatus.READY.value or not source.html_content:
            raise AppError(
                code="MOCKUP_NOT_READY",
                message="Only a ready mockup can be refined.",
                status_code=409,
            )
        provider: MockupProvider = (  # type: ignore[assignment]
            data.provider or source.provider or "gemini"
        )
        resolve_mockup_provider(self.settings, provider)
        lead = self._lead(source.lead_id)
        audit, findings = self._latest_findings(lead.id)
        eligibility = evaluate_mockup_eligibility(lead, audit)
        goal: MockupGoal = (source.goal or "calls")  # type: ignore[assignment]
        brief = self._brief_for_lead(
            lead=lead,
            findings=findings,
            requirements=None,
            guidance=source.design_guide_snapshot,
            goal=goal,
            asset_labels=self._asset_labels(source.asset_refs),
            scenario=eligibility.scenario if eligibility.allowed else (
                "redesign" if eligibility.has_website else "new_site"
            ),
            design_score=eligibility.design_score or (
                audit.design_score if audit is not None else None
            ),
            previous_html=source.html_content,
            refine_instructions=data.instructions,
        )
        mockup = Mockup(
            lead_id=lead.id,
            audit_id=audit.id if audit is not None else source.audit_id,
            title=source.title or "Homepage concept",
            status=MockupStatus.GENERATING.value,
            prompt=brief,
            provider=provider,
            goal=goal,
            version=self._next_version(lead.id),
            notes="Refining homepage…",
            design_guide_id=source.design_guide_id,
            design_guide_name=source.design_guide_name,
            design_guide_snapshot=source.design_guide_snapshot,
            source_mockup_id=source.id,
            screenshot_status="PENDING",
            asset_refs=list(source.asset_refs or []),
        )
        self.session.add(mockup)
        self.session.flush()
        return MockupCreated.from_mockup(mockup)

    def eligibility(self, lead_id: UUID) -> dict[str, object]:
        lead = self._lead(lead_id)
        audit, _findings = self._latest_findings(lead.id)
        result = evaluate_mockup_eligibility(lead, audit)
        return {
            "lead_id": lead.id,
            "allowed": result.allowed,
            "reason": result.reason,
            "message": result.message,
            "design_score": result.design_score,
            "has_website": result.has_website,
            "limit": 50,
            "scenario": result.scenario if result.allowed else None,
        }

    def _brief_for_lead(
        self,
        *,
        lead: Lead,
        findings: list[str],
        requirements: str | None,
        guidance: str | None,
        goal: MockupGoal,
        asset_labels: list[str],
        scenario: str,
        design_score: int | None,
        previous_html: str | None = None,
        refine_instructions: str | None = None,
    ) -> str:
        social = [
            value
            for value in (
                lead.google_maps_url,
                lead.facebook_url,
                lead.instagram_url,
                lead.linkedin_url,
            )
            if value
        ]
        tags = lead.tags if isinstance(lead.tags, list) else []
        return build_generation_brief(
            business_name=lead.business_name,
            city=lead.city,
            country=lead.country,
            industry=lead.industry,
            website_url=lead.website_url,
            description=lead.description,
            email=lead.email,
            phone=lead.phone,
            findings=findings,
            requirements=requirements,
            guidance=guidance,
            goal=goal,
            asset_labels=asset_labels,
            scenario=scenario,  # type: ignore[arg-type]
            design_score=design_score,
            tags=[str(tag) for tag in tags],
            social_links=social,
            notes=lead.notes,
            previous_html=previous_html,
            refine_instructions=refine_instructions,
        )

    def retry(self, mockup_id: UUID, data: MockupRetry) -> MockupCreated:
        mockup = self._get(mockup_id)
        if mockup.status not in {MockupStatus.FAILED.value, MockupStatus.READY.value}:
            raise AppError(
                code="MOCKUP_BUSY",
                message="Wait for the current generation to finish before retrying.",
                status_code=409,
            )
        resolve_mockup_provider(self.settings, data.provider)
        if mockup.status == MockupStatus.READY.value and mockup.html_content:
            # Explicit switch/retry after success creates a new version.
            return self.refine(
                mockup_id,
                MockupRefine(instructions="Regenerate with the same brief.", provider=data.provider),
            )
        mockup.provider = data.provider
        mockup.status = MockupStatus.GENERATING.value
        mockup.error_code = None
        mockup.notes = "Retrying homepage generation…"
        mockup.screenshot_status = "PENDING"
        mockup.html_content = None
        mockup.desktop_image_url = None
        mockup.mobile_image_url = None
        mockup.image_url = None
        mockup.thumbnail_url = None
        mockup.completed_at = None
        self.session.flush()
        return MockupCreated.from_mockup(mockup)

    def retry_screenshots(self, mockup_id: UUID) -> MockupDetail:
        mockup = self._get(mockup_id)
        if not mockup.html_content:
            raise AppError(
                code="MOCKUP_NOT_READY",
                message="Generate the homepage before capturing screenshots.",
                status_code=409,
            )
        mockup.screenshot_status = "PENDING"
        mockup.notes = (mockup.notes or "") + "\nRetrying screenshots…"
        self.session.flush()
        return self.detail(mockup_id)

    async def execute(
        self,
        mockup_id: UUID,
        *,
        client: httpx.Client | None = None,
        capture: Callable[[str], tuple[bytes, bytes]] | None = None,
    ) -> None:
        mockup = self.session.get(Mockup, mockup_id)
        if mockup is None:
            return
        if mockup.status not in {MockupStatus.GENERATING.value, MockupStatus.PENDING.value}:
            if mockup.screenshot_status == "PENDING" and mockup.html_content:
                await self._capture_only(mockup, capture=capture)
            return
        lead = self.session.get(Lead, mockup.lead_id)
        if lead is None:
            mockup.status = MockupStatus.FAILED.value
            mockup.error_code = "LEAD_NOT_FOUND"
            mockup.notes = "That lead could not be found."
            return
        provider: MockupProvider = (mockup.provider or "gemini")  # type: ignore[assignment]
        try:
            resolve_mockup_provider(self.settings, provider)
            asset_uris = self._asset_data_uris(mockup)
            html, model_name = generate_homepage_html(
                brief=mockup.prompt or "",
                settings=self.settings,
                provider=provider,
                asset_data_uris=asset_uris,
                client=client,
            )
            mockup.html_content = html
            mockup.model_name = model_name
            mockup.error_code = None
            mockup.status = MockupStatus.READY.value
            mockup.screenshot_status = "PENDING"
            mockup.completed_at = datetime.now(UTC)
            mockup.notes = "Homepage HTML ready. Capturing screenshots…"
            # Persist HTML before screenshots so a serverless timeout cannot lose the page.
            self.session.commit()

            # Chromium pack download can exhaust Vercel maxDuration; capture on a follow-up /process.
            if os.environ.get("VERCEL") == "1":
                mockup.notes = (
                    "Homepage HTML is ready. Screenshots will finish on the next process pass."
                )
                self.session.flush()
                return

            await self._capture_only(mockup, capture=capture)
            if mockup.screenshot_status == "READY":
                mockup.notes = "Homepage ready for review. Nothing was emailed or published."
            else:
                mockup.notes = (
                    "Homepage HTML is ready, but screenshots failed. "
                    "You can retry capture without regenerating."
                )
        except AppError as exc:
            logger.warning("mockup_execute_failed code=%s", exc.code)
            mockup.status = MockupStatus.FAILED.value
            mockup.error_code = exc.code
            mockup.notes = exc.message
            mockup.screenshot_status = "FAILED"
        except Exception:
            logger.exception("mockup_execute_unexpected")
            mockup.status = MockupStatus.FAILED.value
            mockup.error_code = "AI_MOCKUP_FAILED"
            mockup.notes = "Homepage generation failed. Retry or switch provider."
            mockup.screenshot_status = "FAILED"
        self.session.flush()

    async def execute_screenshots(
        self,
        mockup_id: UUID,
        *,
        capture: Callable[[str], tuple[bytes, bytes]] | None = None,
    ) -> None:
        mockup = self.session.get(Mockup, mockup_id)
        if mockup is None or not mockup.html_content:
            return
        await self._capture_only(mockup, capture=capture)
        if mockup.status == MockupStatus.READY.value and mockup.screenshot_status == "READY":
            mockup.notes = "Homepage ready for review. Nothing was emailed or published."
        self.session.flush()

    def detail(self, mockup_id: UUID, *, include_html: bool = True) -> MockupDetail:
        mockup = self._get(mockup_id)
        lead = self.session.get(Lead, mockup.lead_id)
        return MockupDetail.from_mockup(
            mockup,
            business_name=lead.business_name if lead else None,
            include_html=include_html,
        )

    def guide_snapshot(self, mockup_id: UUID) -> MockupGuideRead:
        mockup = self._get(mockup_id)
        snapshot = mockup.design_guide_snapshot or ""
        return MockupGuideRead(
            id=mockup.id,
            design_guide_id=mockup.design_guide_id,
            design_guide_name=mockup.design_guide_name,
            design_guide_snapshot=mockup.design_guide_snapshot,
            blocks=parse_markdown(snapshot) if snapshot else [],
        )

    def read_html(self, mockup_id: UUID) -> str:
        mockup = self._get(mockup_id)
        if not mockup.html_content:
            raise AppError(
                code="NOT_FOUND",
                message="That mockup HTML could not be found.",
                status_code=404,
            )
        return mockup.html_content

    def read_preview_html(self, mockup_id: UUID) -> str:
        return wrap_for_srcdoc(self.read_html(mockup_id))

    def read_screenshot(self, mockup_id: UUID, variant: str) -> bytes:
        mockup = self._get(mockup_id)
        relative = None
        if variant == "desktop":
            relative = mockup.desktop_image_url or mockup.image_url
        elif variant == "mobile":
            relative = mockup.mobile_image_url
        elif variant == "thumb":
            relative = mockup.thumbnail_url or mockup.desktop_image_url or mockup.image_url
        data = read_storage_file(self.storage_dir, relative)
        if data is None:
            raise AppError(
                code="NOT_FOUND",
                message="That screenshot could not be found.",
                status_code=404,
            )
        return data

    async def _capture_only(
        self,
        mockup: Mockup,
        *,
        capture: Callable[[str], tuple[bytes, bytes]] | None = None,
    ) -> None:
        assert mockup.html_content
        try:
            if capture is not None:
                desktop, mobile = capture(mockup.html_content)
            else:
                desktop, mobile = await capture_mockup_html(mockup.html_content)
            desktop_key = mockup_screenshot_key(str(mockup.lead_id), str(mockup.id), "desktop")
            mobile_key = mockup_screenshot_key(str(mockup.lead_id), str(mockup.id), "mobile")
            mockup.desktop_image_url = save_screenshot(self.storage_dir, desktop_key, desktop)
            mockup.mobile_image_url = save_screenshot(self.storage_dir, mobile_key, mobile)
            mockup.image_url = mockup.desktop_image_url
            mockup.thumbnail_url = mockup.desktop_image_url
            mockup.screenshot_status = "READY"
        except (MockupCaptureError, AppError) as exc:
            message = getattr(exc, "message", str(exc))
            logger.warning("mockup_screenshot_failed mockup_id=%s", mockup.id)
            mockup.screenshot_status = "FAILED"
            mockup.notes = (
                f"Homepage HTML was saved, but screenshots failed: {message} "
                "Retry capture when ready."
            )

    def _store_assets(
        self,
        lead_id: UUID,
        mockup_id: UUID,
        assets: list[tuple[str, bytes, str | None]],
    ) -> list[dict[str, object]]:
        if len(assets) > MAX_ASSETS:
            raise AppError(
                code="VALIDATION_ERROR",
                message=f"Upload at most {MAX_ASSETS} images.",
                status_code=422,
            )
        refs: list[dict[str, object]] = []
        for index, (filename, payload, content_type) in enumerate(assets):
            if len(payload) > MAX_ASSET_BYTES:
                raise AppError(
                    code="VALIDATION_ERROR",
                    message="Each image must be 1.5 MB or smaller.",
                    status_code=422,
                )
            mime = (content_type or "").split(";")[0].strip().lower()
            if mime not in _ALLOWED_ASSET_TYPES and not _looks_like_image(payload):
                raise AppError(
                    code="VALIDATION_ERROR",
                    message="Upload PNG, JPEG, WebP, or GIF images only.",
                    status_code=422,
                )
            ext = _ALLOWED_ASSET_TYPES.get(mime) or _ext_from_bytes(payload)
            name = f"asset-{index + 1}{ext}"
            relative = mockup_asset_key(str(lead_id), str(mockup_id), name)
            save_bytes(self.storage_dir, relative, payload)
            refs.append(
                {
                    "id": str(uuid4()),
                    "filename": filename or name,
                    "path": relative,
                    "content_type": mime or "image/png",
                }
            )
        return refs

    def _asset_data_uris(self, mockup: Mockup) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for index, item in enumerate(mockup.asset_refs or []):
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            filename = item.get("filename")
            content_type = item.get("content_type") if isinstance(item.get("content_type"), str) else "image/png"
            data_uri = item.get("data_uri") if isinstance(item.get("data_uri"), str) else None
            if data_uri is None and isinstance(path, str):
                raw = read_storage_file(self.storage_dir, path)
                if raw:
                    data_uri = (
                        f"data:{content_type};base64,{base64.b64encode(raw).decode('ascii')}"
                    )
            if not isinstance(data_uri, str):
                continue
            mapping[str(index)] = data_uri
            mapping[f"asset:{index}"] = data_uri
            if isinstance(path, str):
                mapping[path] = data_uri
            if isinstance(filename, str):
                mapping[filename] = data_uri
        return mapping

    @staticmethod
    def _asset_labels(refs: list[dict[str, object]] | None) -> list[str]:
        labels: list[str] = []
        for index, item in enumerate(refs or []):
            if not isinstance(item, dict):
                continue
            name = item.get("filename") or item.get("id") or f"asset-{index + 1}"
            labels.append(f'{name} — use src="asset:{index}" (approved local asset only)')
        return labels

    def _resolve_guide(
        self,
        data: MockupCreate,
        source: Mockup | None,
    ) -> tuple[UUID | None, str | None, str | None]:
        try:
            mode = snapshot_choice(
                mode=data.guide_mode,
                has_saved_snapshot=bool(source and source.design_guide_snapshot),
                has_selected_guide=data.design_guide_id is not None,
            )
        except ValueError as exc:
            raise AppError(code="VALIDATION_ERROR", message=str(exc), status_code=422) from exc
        if mode == "keep" and source is not None:
            return source.design_guide_id, source.design_guide_name, source.design_guide_snapshot
        if mode == "selected" and data.design_guide_id is not None:
            guide = self.session.get(DesignGuide, data.design_guide_id)
            if guide is None:
                raise AppError(
                    code="GUIDE_NOT_FOUND",
                    message="That design guide could not be found.",
                    status_code=404,
                )
            return guide.id, guide.name, guide.content
        return None, None, None

    def _latest_findings(self, lead_id: UUID) -> tuple[WebsiteAudit | None, list[str]]:
        audit = self.session.scalar(
            select(WebsiteAudit)
            .where(
                WebsiteAudit.lead_id == lead_id,
                WebsiteAudit.status == AuditStatus.COMPLETED.value,
            )
            .order_by(WebsiteAudit.completed_at.desc())
        )
        findings = verified_finding_lines(
            audit.raw_analysis if audit is not None else None,
            completed=audit is not None,
        )
        return audit, findings

    def _next_version(self, lead_id: UUID) -> int:
        current = int(
            self.session.scalar(select(func.max(Mockup.version)).where(Mockup.lead_id == lead_id))
            or 0
        )
        return current + 1

    def _lead(self, lead_id: UUID) -> Lead:
        lead = self.session.get(Lead, lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )
        return lead

    def _get(self, mockup_id: UUID) -> Mockup:
        mockup = self.session.get(Mockup, mockup_id)
        if mockup is None:
            raise AppError(
                code="MOCKUP_NOT_FOUND",
                message="That mockup could not be found.",
                status_code=404,
            )
        return mockup

    def _source(
        self,
        source_mockup_id: UUID | None,
        lead_id: UUID,
        *,
        required_for_keep: bool,
    ) -> Mockup | None:
        if source_mockup_id is None:
            if required_for_keep:
                raise AppError(
                    code="VALIDATION_ERROR",
                    message="Choose the mockup whose saved design guide should be kept.",
                    status_code=422,
                )
            return None
        source = self.session.get(Mockup, source_mockup_id)
        if source is None or source.lead_id != lead_id:
            raise AppError(
                code="MOCKUP_NOT_FOUND",
                message="That mockup could not be found.",
                status_code=404,
            )
        return source


def _looks_like_image(payload: bytes) -> bool:
    return (
        payload.startswith(b"\x89PNG\r\n\x1a\n")
        or payload.startswith(b"\xff\xd8\xff")
        or payload.startswith(b"GIF87a")
        or payload.startswith(b"GIF89a")
        or payload.startswith(b"RIFF")
    )


def _ext_from_bytes(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG"):
        return ".png"
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith(b"GIF8"):
        return ".gif"
    if payload.startswith(b"RIFF"):
        return ".webp"
    return ".bin"
