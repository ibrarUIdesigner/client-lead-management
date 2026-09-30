import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.brand_profile import BrandProfile
from app.models.enums import AuditStatus, LeadStatus
from app.models.lead import Lead
from app.models.website_audit import WebsiteAudit
from app.repositories.activities import ActivityRepository
from app.repositories.audits import AuditRepository
from app.services.audit_analysis import (
    AuditAnalysis,
    analyze_missing_website,
    analyze_page,
    apply_crawl,
    apply_pagespeed,
    build_report,
)
from app.services.audit_browser import AuditRunError, capture_website
from app.services.audit_crawl import crawl_site
from app.services.audit_crux import fetch_crux
from app.services.audit_pagespeed import fetch_pagespeed, pagespeed_tool
from app.services.storage import save_screenshot, screenshot_key
from app.services.url_safety import assert_public_http_url

logger = logging.getLogger(__name__)

_PROGRESS = {
    LeadStatus.NEW.value,
    LeadStatus.QUALIFIED.value,
    LeadStatus.AUDIT_PENDING.value,
    LeadStatus.AUDIT_COMPLETE.value,
}


class AuditService:
    def __init__(
        self,
        session: Session,
        storage_dir: Path,
        pagespeed_api_key: str = "",
        user_agent: str = "",
    ) -> None:
        self.session = session
        self.storage_dir = storage_dir
        self.pagespeed_api_key = pagespeed_api_key
        self.user_agent = user_agent
        self.audits = AuditRepository(session)
        self.activities = ActivityRepository(session)

    def prepare(self, lead_id: UUID) -> tuple[WebsiteAudit, bool]:
        lead = self._require_lead(lead_id)
        if self.audits.get_active(lead_id) is not None:
            raise AppError(
                code="AUDIT_IN_PROGRESS",
                message="This website is already being analyzed.",
                status_code=409,
            )
        audit = WebsiteAudit(
            lead_id=lead.id, url=lead.website_url, status=AuditStatus.PENDING.value
        )
        self.session.add(audit)
        return self._queue(lead, audit, created=True)

    def rerun(self, audit_id: UUID) -> tuple[WebsiteAudit, bool]:
        audit = self._require(audit_id)
        if audit.status == AuditStatus.RUNNING.value:
            raise AppError(
                code="AUDIT_IN_PROGRESS",
                message="This website is already being analyzed.",
                status_code=409,
            )
        lead = self._require_lead(audit.lead_id)
        active = self.audits.get_active(lead.id)
        if active is not None and active.id != audit.id:
            raise AppError(
                code="AUDIT_IN_PROGRESS",
                message="This website is already being analyzed.",
                status_code=409,
            )
        audit.url = lead.website_url
        return self._queue(lead, audit, created=False)

    def latest(self, lead_id: UUID) -> WebsiteAudit:
        self._require_lead(lead_id)
        audit = self.audits.latest(lead_id)
        if audit is None:
            raise AppError(
                code="AUDIT_NOT_FOUND",
                message="This lead has no website audit yet.",
                status_code=404,
            )
        return audit

    def list_for_lead(self, lead_id: UUID) -> list[WebsiteAudit]:
        self._require_lead(lead_id)
        return self.audits.list_for_lead(lead_id)

    def get(self, audit_id: UUID) -> WebsiteAudit:
        return self._require(audit_id)

    async def execute(self, audit_id: UUID) -> None:
        audit = self.audits.get(audit_id)
        if audit is None or audit.status != AuditStatus.PENDING.value:
            return
        if not audit.url:
            return
        audit.status = AuditStatus.RUNNING.value
        audit.desktop_screenshot_url = None
        audit.mobile_screenshot_url = None
        self.session.commit()
        try:
            captured, pagespeed, field_data = await asyncio.gather(
                capture_website(audit.url),
                fetch_pagespeed(audit.url, self.pagespeed_api_key),
                fetch_crux(audit.url, self.pagespeed_api_key),
            )
            analysis = analyze_page(captured)
            try:
                crawled = await crawl_site(captured.final_url, captured.links, self.user_agent)
                apply_crawl(analysis, crawled)
            except Exception:
                logger.warning("audit_crawl_failed")
                analysis.tools.append(
                    {
                        "name": "SEO crawler",
                        "status": "failed",
                        "detail": "Extra pages could not be checked. Homepage results were saved.",
                    }
                )
                analysis.report = build_report(analysis)
            if pagespeed.status == "ok" and pagespeed.report is not None:
                apply_pagespeed(analysis, pagespeed.report)
            else:
                analysis.tools.append(pagespeed_tool(pagespeed.status))
                analysis.report = build_report(analysis)
            analysis.field_data = field_data.as_dict()
            analysis.tools.append(field_data.tool())
            analysis.report = build_report(analysis)
            audit.desktop_screenshot_url = self._store(audit, "desktop", captured.desktop_png)
            audit.mobile_screenshot_url = self._store(audit, "mobile", captured.mobile_png)
            self._apply(audit, analysis, website_status="analyzed")
            self.activities.add(
                audit.lead_id,
                "audit_completed",
                "Website audit completed",
                description=analysis.title or audit.url,
            )
        except AuditRunError as exc:
            self._fail(audit, exc.message)
        except Exception:
            logger.warning("audit_failed")
            self._fail(audit, "The website could not be analyzed.")

    def _queue(
        self, lead: Lead, audit: WebsiteAudit, *, created: bool
    ) -> tuple[WebsiteAudit, bool]:
        if not lead.website_url:
            self._apply(audit, analyze_missing_website(), website_status="missing")
            self.activities.add(
                lead.id,
                "audit_completed",
                "Website audit completed",
                description="No website address",
            )
            self._touch_lead_status(lead, AuditStatus.COMPLETED.value)
            self.session.flush()
            self.session.refresh(audit)
            return audit, False

        assert_public_http_url(lead.website_url)
        audit.url = lead.website_url
        audit.status = AuditStatus.PENDING.value
        audit.completed_at = None
        audit.raw_analysis = None
        audit.issues = None
        audit.recommendations = None
        audit.desktop_screenshot_url = None
        audit.mobile_screenshot_url = None
        _clear_scores(audit)
        self._touch_lead_status(lead, AuditStatus.PENDING.value)
        lead.website_status = "pending"
        self.activities.add(
            lead.id, "audit_started", "Website audit started", description=lead.website_url
        )
        self.session.flush()
        self.session.refresh(audit)
        if not created:
            self.session.flush()
        return audit, True

    def _apply(self, audit: WebsiteAudit, analysis: AuditAnalysis, *, website_status: str) -> None:
        audit.status = AuditStatus.COMPLETED.value
        audit.performance_score = analysis.performance_score
        audit.design_score = analysis.design_score
        audit.mobile_score = analysis.mobile_score
        audit.ux_score = analysis.ux_score
        audit.seo_score = analysis.seo_score
        audit.overall_score = analysis.overall_score
        audit.has_ssl = analysis.has_ssl
        audit.is_mobile_responsive = analysis.is_mobile_responsive
        audit.has_clear_cta = analysis.has_clear_cta
        audit.has_contact_form = analysis.has_contact_form
        audit.has_social_proof = analysis.has_social_proof
        audit.has_modern_navigation = analysis.has_modern_navigation
        audit.issues = analysis.issues
        audit.recommendations = analysis.recommendations
        audit.raw_analysis = {
            "opportunity_score": analysis.opportunity_score,
            "opportunity_breakdown": analysis.opportunity_breakdown,
            "title": analysis.title,
            "final_url": analysis.final_url,
            "tools": analysis.tools,
            "report": analysis.report,
            "pages": analysis.pages,
            "field_data": analysis.field_data,
            "error": None,
            "brand": {
                "primary_color": analysis.brand.get("primary_color"),
                "secondary_color": analysis.brand.get("secondary_color"),
                "font_primary": analysis.brand.get("font_primary"),
                "brand_description": analysis.brand.get("brand_description"),
            },
        }
        audit.completed_at = datetime.now(UTC)
        lead = self._require_lead(audit.lead_id)
        lead.website_status = website_status
        lead.website_quality_score = analysis.overall_score
        lead.lead_score = analysis.opportunity_score
        self._touch_lead_status(lead, AuditStatus.COMPLETED.value)
        if analysis.brand:
            self._save_brand(lead.id, analysis.brand)

    def _fail(self, audit: WebsiteAudit, message: str) -> None:
        audit.status = AuditStatus.FAILED.value
        audit.completed_at = datetime.now(UTC)
        audit.raw_analysis = {
            "error": message,
            "opportunity_score": None,
            "opportunity_breakdown": [],
        }
        lead = self.session.get(Lead, audit.lead_id)
        if lead is not None:
            lead.website_status = "failed"
        self.activities.add(
            audit.lead_id, "audit_failed", "Website audit failed", description=message
        )

    def _save_brand(self, lead_id: UUID, brand: dict[str, object]) -> None:
        profile = self.session.scalar(select(BrandProfile).where(BrandProfile.lead_id == lead_id))
        if profile is None:
            profile = BrandProfile(lead_id=lead_id)
            self.session.add(profile)
        profile.logo_url = _text(brand.get("logo_url"), 2000)
        profile.primary_color = _text(brand.get("primary_color"), 32)
        profile.secondary_color = _text(brand.get("secondary_color"), 32)
        profile.font_primary = _text(brand.get("font_primary"), 120)
        profile.font_secondary = _text(brand.get("font_secondary"), 120)
        profile.brand_description = _text(brand.get("brand_description"), 2000)
        images = brand.get("extracted_images")
        profile.extracted_images = images if isinstance(images, list) else []
        content = brand.get("extracted_content")
        profile.extracted_content = content if isinstance(content, dict) else {}

    def _store(self, audit: WebsiteAudit, variant: str, data: bytes) -> str | None:
        if not data:
            return None
        try:
            key = screenshot_key(str(audit.lead_id), str(audit.id), variant)
            return save_screenshot(self.storage_dir, key, data)
        except AppError:
            logger.warning("audit_screenshot_rejected")
            return None

    def _touch_lead_status(self, lead: Lead, audit_status: str) -> None:
        if lead.lead_status not in _PROGRESS:
            return
        if audit_status == AuditStatus.COMPLETED.value:
            lead.lead_status = LeadStatus.AUDIT_COMPLETE.value
        else:
            lead.lead_status = LeadStatus.AUDIT_PENDING.value

    def _require_lead(self, lead_id: UUID) -> Lead:
        lead = self.session.get(Lead, lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )
        return lead

    def _require(self, audit_id: UUID) -> WebsiteAudit:
        audit = self.audits.get(audit_id)
        if audit is None:
            raise AppError(
                code="AUDIT_NOT_FOUND",
                message="That audit could not be found.",
                status_code=404,
            )
        return audit


def _clear_scores(audit: WebsiteAudit) -> None:
    audit.performance_score = None
    audit.design_score = None
    audit.mobile_score = None
    audit.ux_score = None
    audit.seo_score = None
    audit.overall_score = None
    audit.has_ssl = None
    audit.is_mobile_responsive = None
    audit.has_clear_cta = None
    audit.has_contact_form = None
    audit.has_social_proof = None
    audit.has_modern_navigation = None


def _text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:limit]
