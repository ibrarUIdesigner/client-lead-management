"""Opportunity Analysis & Explainable Opportunity Scoring Engine.

Synthesizes:
- Technical findings from WebsiteAudit
- Commercial context from LeadResearch
- Behavioral and trigger events from SignalDetector

Produces structured, prioritized Opportunities and a fully transparent
additive Opportunity Score (0–100) with a factor-by-factor breakdown.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit
from app.services.signals import HIGH_VALUE_INDUSTRIES, Signal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Opportunity:
    problem: str
    evidence: str
    source: str
    recommended_solution: str
    impact: str  # "high" | "medium" | "low"
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem": self.problem,
            "evidence": self.evidence,
            "source": self.source,
            "recommended_solution": self.recommended_solution,
            "impact": self.impact,
            "confidence": round(self.confidence, 2),
        }


@dataclass(frozen=True)
class ScoreFactor:
    label: str
    points: int
    category: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "points": self.points,
            "category": self.category,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OpportunityScoreResult:
    total_score: int
    tier: str  # "high" | "medium" | "low"
    tier_label: str  # "🔥 High Opportunity" | "⚡ Medium Opportunity" | "○ Low Opportunity"
    breakdown: list[ScoreFactor]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "tier": self.tier,
            "tier_label": self.tier_label,
            "breakdown": [f.to_dict() for f in self.breakdown],
        }


class OpportunityEngine:
    """Orchestrates Opportunity extraction and explainable scoring."""

    def analyze_opportunities(
        self,
        lead: Lead,
        signals: list[Signal],
        audit: WebsiteAudit | None = None,
        research: LeadResearch | None = None,
    ) -> list[Opportunity]:
        opportunities: list[Opportunity] = []
        sig_map = {s.name: s for s in signals}

        # Opportunity: No Website -> Build Digital Foundation
        if "NO_WEBSITE" in sig_map:
            opportunities.append(
                Opportunity(
                    problem="Business operates without an official digital presence.",
                    evidence=sig_map["NO_WEBSITE"].evidence,
                    source="Lead Discovery",
                    recommended_solution=(
                        "Design and launch a modern, single-page responsive website featuring services, "
                        "credibility indicators, and clear contact capture."
                    ),
                    impact="high",
                    confidence=0.98,
                )
            )

        # Opportunity: Missing Booking CTA
        if "MISSING_BOOKING" in sig_map:
            opportunities.append(
                Opportunity(
                    problem="Appointment-driven business has no direct online booking mechanism.",
                    evidence=sig_map["MISSING_BOOKING"].evidence,
                    source="Website Audit",
                    recommended_solution=(
                        "Implement an appointment request section with a high-contrast booking button "
                        "sticky in the header and hero."
                    ),
                    impact="high",
                    confidence=0.94,
                )
            )

        # Opportunity: Mobile UX & Speed Friction
        if "SLOW_WEBSITE" in sig_map or "POOR_MOBILE_UX" in sig_map:
            slow_sig = sig_map.get("SLOW_WEBSITE")
            mob_sig = sig_map.get("POOR_MOBILE_UX")
            evidence_parts = [s.evidence for s in (slow_sig, mob_sig) if s]
            opportunities.append(
                Opportunity(
                    problem="Mobile visitors encounter excessive load times or layout overflow.",
                    evidence=" ".join(evidence_parts),
                    source="Website Audit",
                    recommended_solution=(
                        "Re-architect page using lightweight modern CSS, compress imagery, "
                        "and ensure responsive viewport scaling."
                    ),
                    impact="high",
                    confidence=0.91,
                )
            )

        # Opportunity: Missing Contact Form
        if "MISSING_CONTACT_FORM" in sig_map:
            opportunities.append(
                Opportunity(
                    problem="Lack of lead capture forms forces prospective clients to call manually.",
                    evidence=sig_map["MISSING_CONTACT_FORM"].evidence,
                    source="Website Audit",
                    recommended_solution=(
                        "Add a streamlined 3-field quick estimate form above the pre-footer section."
                    ),
                    impact="medium",
                    confidence=0.90,
                )
            )

        # Opportunity: Research-driven pain points
        if research and isinstance(research.research_data, dict):
            rdata = research.research_data
            proactive_solutions = rdata.get("proactive_solutions") or []
            pain_points = rdata.get("pain_points_and_gaps") or []

            for idx, sol in enumerate(proactive_solutions[:2]):
                pp = pain_points[idx] if idx < len(pain_points) else "Operational gap identified in market analysis."
                opportunities.append(
                    Opportunity(
                        problem=str(pp),
                        evidence=f"Identified in market research synthesis for {lead.business_name}.",
                        source="Market Research",
                        recommended_solution=str(sol),
                        impact="medium",
                        confidence=0.85,
                    )
                )

        return opportunities

    def calculate_score(
        self,
        lead: Lead,
        signals: list[Signal],
        audit: WebsiteAudit | None = None,
        research: LeadResearch | None = None,
    ) -> OpportunityScoreResult:
        factors: list[ScoreFactor] = []
        sig_map = {s.name: s for s in signals}

        # 1. Dimension: Website Opportunity (max 25 pts)
        if not lead.website_url or "NO_WEBSITE" in sig_map:
            factors.append(
                ScoreFactor(
                    label="Website opportunity",
                    points=25,
                    category="website",
                    reason="Business has no website; prime candidate for a brand-new digital presence.",
                )
            )
        elif "SLOW_WEBSITE" in sig_map and "POOR_MOBILE_UX" in sig_map:
            factors.append(
                ScoreFactor(
                    label="Website opportunity",
                    points=20,
                    category="website",
                    reason="Critical mobile speed and layout friction verified by audit.",
                )
            )
        elif "SLOW_WEBSITE" in sig_map or "POOR_MOBILE_UX" in sig_map or "NO_CLEAR_CTA" in sig_map:
            factors.append(
                ScoreFactor(
                    label="Website opportunity",
                    points=15,
                    category="website",
                    reason="Notable usability, speed, or CTA bottlenecks found in website audit.",
                )
            )
        elif audit and audit.overall_score is not None and audit.overall_score < 75:
            factors.append(
                ScoreFactor(
                    label="Website opportunity",
                    points=8,
                    category="website",
                    reason="Moderate visual and technical modernization headroom.",
                )
            )

        # 2. Dimension: Business & Industry Fit (max 25 pts)
        ind = (lead.industry or "").lower()
        if any(hv in ind for hv in HIGH_VALUE_INDUSTRIES):
            factors.append(
                ScoreFactor(
                    label="Strong business fit",
                    points=22,
                    category="business",
                    reason=f"High-ticket commercial vertical ({lead.industry}) with high lifetime customer value.",
                )
            )
        elif lead.industry:
            factors.append(
                ScoreFactor(
                    label="Strong business fit",
                    points=15,
                    category="business",
                    reason=f"Established local service vertical ({lead.industry}).",
                )
            )

        # 3. Dimension: Intent & Service Value (max 20 pts)
        if "HIGH_INTENT" in sig_map:
            factors.append(
                ScoreFactor(
                    label="High conversion intent",
                    points=18,
                    category="intent",
                    reason="Direct decision channel and high-urgency market signals.",
                )
            )
        elif "MEDIUM_INTENT" in sig_map:
            factors.append(
                ScoreFactor(
                    label="Moderate conversion intent",
                    points=10,
                    category="intent",
                    reason="Viable prospect profile with actionable design opportunities.",
                )
            )

        # 4. Dimension: Research & Market Signals (max 15 pts)
        if "STRONG_REPUTATION" in sig_map:
            factors.append(
                ScoreFactor(
                    label="Strong research signals",
                    points=10,
                    category="research",
                    reason="High positive customer reviews and community goodwill to feature in redesign.",
                )
            )
        elif research and research.status == "COMPLETED":
            factors.append(
                ScoreFactor(
                    label="Strong research signals",
                    points=8,
                    category="research",
                    reason="Comprehensive market intelligence and competitor analysis gathered.",
                )
            )

        # 5. Dimension: Conversion Opportunities (max 10 pts)
        if "MISSING_BOOKING" in sig_map or "MISSING_CONTACT_FORM" in sig_map:
            factors.append(
                ScoreFactor(
                    label="Clear conversion opportunity",
                    points=10,
                    category="conversion",
                    reason="Direct customer acquisition blocker (booking or form) readily solvable.",
                )
            )

        # 6. Dimension: Data Completeness & Reachability (max 5 pts)
        if lead.email and "@" in lead.email:
            factors.append(
                ScoreFactor(
                    label="Direct outreach ready",
                    points=5,
                    category="data",
                    reason="Direct email address confirmed and reachable.",
                )
            )

        total = sum(f.points for f in factors)
        total = min(100, max(0, total))

        if total >= 75:
            tier = "high"
            tier_label = "🔥 High Opportunity"
        elif total >= 50:
            tier = "medium"
            tier_label = "⚡ Medium Opportunity"
        else:
            tier = "low"
            tier_label = "○ Low Opportunity"

        return OpportunityScoreResult(
            total_score=total,
            tier=tier,
            tier_label=tier_label,
            breakdown=factors,
        )
