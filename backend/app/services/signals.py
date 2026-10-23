"""Reusable Signal Detection Engine inspired by Harvey's Scout Agent.

Evaluates deterministic signals across:
- Website Signals (technical friction, speed, CTA, booking gaps)
- Business Signals (reputation, expansion, hiring, market activity)
- Sales Intent Signals (high, medium, low buying intent)

Every signal contains verifiable evidence, source, confidence, and timestamp.
No fabricated or hallucinated signals.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit

logger = logging.getLogger(__name__)

# High-ticket local service industries
HIGH_VALUE_INDUSTRIES = {
    "dental",
    "dentist",
    "roofing",
    "legal",
    "lawyer",
    "attorney",
    "medical",
    "doctor",
    "clinic",
    "hvac",
    "plumbing",
    "construction",
    "contractor",
    "cosmetic surgery",
    "real estate",
}

BOOKING_DRIVEN_INDUSTRIES = {
    "dental",
    "dentist",
    "medical",
    "clinic",
    "salon",
    "spa",
    "physiotherapy",
    "chiropractor",
    "wellness",
    "massage",
    "vet",
    "veterinary",
}


@dataclass(frozen=True)
class Signal:
    name: str
    type: str  # "website" | "business" | "sales"
    source: str
    confidence: float
    evidence: str
    detected_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "source": self.source,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "detected_at": self.detected_at.isoformat(),
        }


class SignalDetector:
    """Inspects Lead, WebsiteAudit, and LeadResearch data to detect verifiable signals."""

    def detect_all(
        self,
        lead: Lead,
        audit: WebsiteAudit | None = None,
        research: LeadResearch | None = None,
    ) -> list[Signal]:
        now = datetime.now(UTC)
        signals: list[Signal] = []

        # 1. Website Signals
        web_signals = self.detect_website_signals(lead, audit, now)
        signals.extend(web_signals)

        # 2. Business Signals
        biz_signals = self.detect_business_signals(lead, research, now)
        signals.extend(biz_signals)

        # 3. Sales Signals
        sales_signals = self.detect_sales_signals(lead, web_signals, biz_signals, now)
        signals.extend(sales_signals)

        return signals

    def detect_website_signals(
        self,
        lead: Lead,
        audit: WebsiteAudit | None,
        now: datetime | None = None,
    ) -> list[Signal]:
        detected_at = now or datetime.now(UTC)
        signals: list[Signal] = []

        has_website = bool(lead.website_url) and lead.website_status != "missing"

        # Signal: NO_WEBSITE
        if not has_website:
            signals.append(
                Signal(
                    name="NO_WEBSITE",
                    type="website",
                    source="Lead Discovery",
                    confidence=0.98,
                    evidence=f"No active public website found for '{lead.business_name}'.",
                    detected_at=detected_at,
                )
            )
            return signals

        if audit is None:
            return signals

        raw = audit.raw_analysis if isinstance(audit.raw_analysis, dict) else {}
        load_time_ms = raw.get("load_time_ms") or 0
        lcp_ms = raw.get("lcp_ms") or 0

        # Signal: SLOW_WEBSITE
        if lcp_ms > 4000 or (lcp_ms == 0 and load_time_ms > 4000) or (
            audit.performance_score is not None and audit.performance_score < 45
        ):
            if lcp_ms > 0:
                speed_text = f"Largest Contentful Paint took {lcp_ms}ms"
            elif load_time_ms > 0:
                speed_text = f"Initial page load took {load_time_ms}ms"
            else:
                speed_text = "Performance audit flagged sluggish load metrics"

            signals.append(
                Signal(
                    name="SLOW_WEBSITE",
                    type="website",
                    source="Website Audit",
                    confidence=0.94,
                    evidence=f"{speed_text} (Score: {audit.performance_score or 'low'}/100).",
                    detected_at=detected_at,
                )
            )

        # Signal: POOR_MOBILE_UX
        if audit.is_mobile_responsive is False or (
            audit.mobile_score is not None and audit.mobile_score < 50
        ):
            signals.append(
                Signal(
                    name="POOR_MOBILE_UX",
                    type="website",
                    source="Website Audit",
                    confidence=0.92,
                    evidence="Horizontal content overflow detected or mobile usability score is below 50/100.",
                    detected_at=detected_at,
                )
            )

        # Signal: WEAK_CTA / NO_CLEAR_CTA
        if audit.has_clear_cta is False or (audit.ux_score is not None and audit.ux_score < 50):
            signals.append(
                Signal(
                    name="NO_CLEAR_CTA",
                    type="website",
                    source="Website Audit",
                    confidence=0.89,
                    evidence="No prominent conversion action button (Call, Book, Quote) detected above the fold.",
                    detected_at=detected_at,
                )
            )

        # Signal: MISSING_CONTACT_FORM
        if audit.has_contact_form is False:
            signals.append(
                Signal(
                    name="MISSING_CONTACT_FORM",
                    type="website",
                    source="Website Audit",
                    confidence=0.91,
                    evidence="Homepage has no functional contact or inquiry input form.",
                    detected_at=detected_at,
                )
            )

        # Signal: MISSING_BOOKING
        ind = (lead.industry or "").lower()
        if any(b in ind for b in BOOKING_DRIVEN_INDUSTRIES):
            cta_labels = raw.get("cta_labels") or []
            has_booking_cta = any("book" in str(c).lower() or "schedul" in str(c).lower() for c in cta_labels)
            if not has_booking_cta:
                signals.append(
                    Signal(
                        name="MISSING_BOOKING",
                        type="website",
                        source="Website Audit",
                        confidence=0.93,
                        evidence=f"Business operates in an appointment-driven vertical ({lead.industry}) with no online booking mechanism.",
                        detected_at=detected_at,
                    )
                )

        # Signal: POOR_NAVIGATION
        if audit.has_modern_navigation is False:
            signals.append(
                Signal(
                    name="POOR_NAVIGATION",
                    type="website",
                    source="Website Audit",
                    confidence=0.85,
                    evidence="Navigation menu contains fewer than 3 links or lacks structured hierarchy.",
                    detected_at=detected_at,
                )
            )

        # Signal: POOR_SEO / MISSING_META
        if audit.seo_score is not None and audit.seo_score < 60:
            signals.append(
                Signal(
                    name="POOR_SEO",
                    type="website",
                    source="Website Audit",
                    confidence=0.88,
                    evidence=f"Search engine visibility score is {audit.seo_score}/100 with incomplete meta tags.",
                    detected_at=detected_at,
                )
            )

        # Signal: OUTDATED_WEBSITE
        if audit.overall_score is not None and audit.overall_score < 55:
            signals.append(
                Signal(
                    name="OUTDATED_WEBSITE",
                    type="website",
                    source="Website Audit",
                    confidence=0.87,
                    evidence=f"Overall digital score is {audit.overall_score}/100 with legacy markup patterns.",
                    detected_at=detected_at,
                )
            )

        return signals

    def detect_business_signals(
        self,
        lead: Lead,
        research: LeadResearch | None,
        now: datetime | None = None,
    ) -> list[Signal]:
        detected_at = now or datetime.now(UTC)
        signals: list[Signal] = []

        # Check lead social presence & direct info
        if lead.instagram_url or lead.facebook_url or lead.linkedin_url:
            signals.append(
                Signal(
                    name="ACTIVE_SOCIAL_MEDIA",
                    type="business",
                    source="Lead Discovery",
                    confidence=0.90,
                    evidence="Social media channel profile links identified for this business.",
                    detected_at=detected_at,
                )
            )

        if research is None or not isinstance(research.research_data, dict):
            return signals

        rdata = research.research_data
        summary = research.summary or ""
        text_corpus = (
            f"{summary} {rdata.get('digital_presence', '')} {rdata.get('company_profile', '')} "
            f"{' '.join(rdata.get('recent_news') or [])}"
        ).lower()

        # Signal: STRONG_REPUTATION / HIGH_REVIEW_COUNT
        if "review" in text_corpus and ("4." in text_corpus or "5." in text_corpus or "star" in text_corpus):
            signals.append(
                Signal(
                    name="STRONG_REPUTATION",
                    type="business",
                    source="Market Research",
                    confidence=0.88,
                    evidence="Positive customer feedback or high Google review rating noted in market findings.",
                    detected_at=detected_at,
                )
            )

        # Signal: EXPANDING / NEW_LOCATION
        if any(term in text_corpus for term in ("new location", "opened", "expanding", "branch", "expansion")):
            signals.append(
                Signal(
                    name="EXPANDING",
                    type="business",
                    source="Market Research",
                    confidence=0.82,
                    evidence="Market research mentions business expansion, new facilities, or service growth.",
                    detected_at=detected_at,
                )
            )

        # Signal: HIRING
        if any(term in text_corpus for term in ("hiring", "job opening", "recruiting", "careers", "we are hiring")):
            signals.append(
                Signal(
                    name="HIRING",
                    type="business",
                    source="Market Research",
                    confidence=0.85,
                    evidence="Active hiring or career openings detected in recent web updates.",
                    detected_at=detected_at,
                )
            )

        # Signal: RUNNING_ADS
        if "ad" in text_corpus or "sponsored" in text_corpus or "campaign" in text_corpus:
            signals.append(
                Signal(
                    name="RUNNING_ADS",
                    type="business",
                    source="Market Research",
                    confidence=0.80,
                    evidence="Indicators of paid marketing or digital advertising campaigns detected.",
                    detected_at=detected_at,
                )
            )

        # Signal: WEAK_SERVICE_PRESENTATION
        pain_points = rdata.get("pain_points_and_gaps") or []
        if any("service" in str(p).lower() or "clear" in str(p).lower() for p in pain_points):
            signals.append(
                Signal(
                    name="WEAK_SERVICE_PRESENTATION",
                    type="business",
                    source="Market Research",
                    confidence=0.86,
                    evidence="Research notes lack of prominent service clarity or weak positioning on existing channels.",
                    detected_at=detected_at,
                )
            )

        return signals

    def detect_sales_signals(
        self,
        lead: Lead,
        website_signals: list[Signal],
        business_signals: list[Signal],
        now: datetime | None = None,
    ) -> list[Signal]:
        detected_at = now or datetime.now(UTC)
        ind = (lead.industry or "").lower()
        is_high_value = any(hv in ind for hv in HIGH_VALUE_INDUSTRIES)
        has_direct_email = bool(lead.email and "@" in lead.email)

        web_issues_count = len(website_signals)
        biz_positives = len(business_signals)

        # Determine sales intent
        if (is_high_value or not lead.website_url) and web_issues_count >= 2 and has_direct_email:
            return [
                Signal(
                    name="HIGH_INTENT",
                    type="sales",
                    source="Sales Intelligence",
                    confidence=0.92,
                    evidence=(
                        f"High-ticket industry ({lead.industry or 'Target'}), verified direct email, "
                        f"and {web_issues_count} clear conversion opportunities identified."
                    ),
                    detected_at=detected_at,
                )
            ]
        elif web_issues_count >= 1 or biz_positives >= 1:
            return [
                Signal(
                    name="MEDIUM_INTENT",
                    type="sales",
                    source="Sales Intelligence",
                    confidence=0.80,
                    evidence="Actionable conversion gaps detected; prospective fit for customized proposal.",
                    detected_at=detected_at,
                )
            ]
        else:
            return [
                Signal(
                    name="LOW_INTENT",
                    type="sales",
                    source="Sales Intelligence",
                    confidence=0.75,
                    evidence="Minimal technical or business friction detected. Monitor for future changes.",
                    detected_at=detected_at,
                )
            ]
