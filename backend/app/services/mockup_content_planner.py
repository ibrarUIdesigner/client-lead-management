"""Content & Strategy Planner for data-driven website mockups.

Maps audit findings to UX solutions, research insights to business opportunities,
and enforces strict anti-fabrication guidelines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit
from app.services.mockup_section_planner import PlannedSection, detect_business_archetype

logger = logging.getLogger(__name__)


@dataclass
class AuditImprovement:
    finding: str
    ux_problem: str
    mockup_solution: str


@dataclass
class ResearchOpportunity:
    insight: str
    market_gap: str
    feature_solution: str


def plan_audit_improvements(
    audit: WebsiteAudit | None,
    findings: list[str] | None = None,
) -> list[AuditImprovement]:
    """Map technical audit findings to concrete UX/UI enhancements in the mockup."""
    improvements: list[AuditImprovement] = []
    findings_list = list(findings or [])
    if audit and isinstance(audit.raw_analysis, dict):
        report = audit.raw_analysis.get("report")
        if isinstance(report, list):
            for item in report:
                if isinstance(item, dict):
                    title = str(item.get("title") or "")
                    detail = str(item.get("detail") or "")
                    line = f"{title}: {detail}" if detail else title
                    if line and line not in findings_list:
                        findings_list.append(line)

    # If audit issues exist on the model
    if audit and isinstance(audit.issues, list):
        for issue in audit.issues:
            if isinstance(issue, dict):
                title = str(issue.get("title") or "")
                detail = str(issue.get("detail") or "")
                code = str(issue.get("code") or "")
                if code == "missing_cta" or "cta" in title.lower():
                    improvements.append(
                        AuditImprovement(
                            finding=title or "Call to action is weak or missing",
                            ux_problem="Visitors cannot immediately identify the next action, hurting conversion rates.",
                            mockup_solution="Design a high-contrast primary CTA button in the hero with clear benefit copy, repeated in sticky header and pre-footer.",
                        )
                    )
                elif code == "poor_mobile" or "mobile" in title.lower():
                    improvements.append(
                        AuditImprovement(
                            finding=title or "Poor mobile experience",
                            ux_problem="Layout overflows or is cramped on mobile viewports.",
                            mockup_solution="Implement a mobile-first responsive stacked grid with readable typography and thumb-friendly tap targets.",
                        )
                    )
                elif code == "missing_ssl" or "ssl" in title.lower():
                    improvements.append(
                        AuditImprovement(
                            finding=title or "Insecure or missing SSL",
                            ux_problem="Lack of security indicators drives cautious local visitors away.",
                            mockup_solution="Display prominent security, licensing, and privacy badges near contact forms and CTA blocks.",
                        )
                    )
                elif "nav" in title.lower():
                    improvements.append(
                        AuditImprovement(
                            finding=title or "Weak navigation architecture",
                            ux_problem="Visitors struggle to discover core pages, treatments, or services.",
                            mockup_solution="Build a clean, high-visibility desktop navigation bar with direct anchor links and mobile drawer trigger.",
                        )
                    )

    # Check raw findings lines
    for line in findings_list:
        lower = line.lower()
        if "cta" in lower or "call to action" in lower or "call-to-action" in lower:
            if not any("cta" in imp.finding.lower() for imp in improvements):
                improvements.append(
                    AuditImprovement(
                        finding=line,
                        ux_problem="Primary conversion step is unclear or absent.",
                        mockup_solution="Feature an unmistakable solid CTA button with clear action text in the hero and top navigation.",
                    )
                )
        elif "mobile" in lower or "viewport" in lower or "responsive" in lower:
            if not any("mobile" in imp.finding.lower() for imp in improvements):
                improvements.append(
                    AuditImprovement(
                        finding=line,
                        ux_problem="Mobile users experience awkward horizontal scroll or tiny text.",
                        mockup_solution="Structure fluid column stacks with generous touch target padding (min 44px).",
                    )
                )
        elif "social" in lower or "review" in lower or "trust" in lower:
            if not any("social" in imp.finding.lower() for imp in improvements):
                improvements.append(
                    AuditImprovement(
                        finding=line,
                        ux_problem="Prospective clients see no evidence of past customer satisfaction.",
                        mockup_solution="Include a dedicated Social Proof & Testimonials card section with verified ratings.",
                    )
                )
        elif "meta" in lower or "seo" in lower or "heading" in lower:
            if not any("meta" in imp.finding.lower() or "seo" in imp.finding.lower() for imp in improvements):
                improvements.append(
                    AuditImprovement(
                        finding=line,
                        ux_problem="Missing search metadata and structured headings weaken local discoverability.",
                        mockup_solution="Implement semantic H1/H2 tags with location keywords and clear structured card hierarchies.",
                    )
                )

    if not improvements:
        improvements.append(
            AuditImprovement(
                finding="Modern website presentation needed",
                ux_problem="Legacy visual layout fails to inspire confidence or convert modern visitors.",
                mockup_solution="Apply modern visual hierarchy, generous whitespace, clear service cards, and an immediate primary CTA.",
            )
        )

    return improvements[:5]


def plan_research_opportunities(
    research: LeadResearch | None,
) -> list[ResearchOpportunity]:
    """Extract market opportunities and strategic solutions from lead research data."""
    opportunities: list[ResearchOpportunity] = []
    if not research or not isinstance(research.research_data, dict):
        return [
            ResearchOpportunity(
                insight="Local customers prioritize clear services and rapid response.",
                market_gap="Competitors often have cluttered, confusing websites with slow contact forms.",
                feature_solution="Highlight direct communication channels and transparent service breakdowns upfront.",
            )
        ]

    data = research.research_data
    proactive = data.get("proactive_solutions") or []
    if isinstance(proactive, list) and proactive:
        for sol in proactive[:3]:
            opportunities.append(
                ResearchOpportunity(
                    insight=str(sol),
                    market_gap="Current online presence under-serves customer convenience in this area.",
                    feature_solution=f"Feature {str(sol).strip()} as a strategic value driver in the layout.",
                )
            )

    gaps = data.get("pain_points_and_gaps") or []
    if isinstance(gaps, list) and gaps:
        for gap in gaps[:2]:
            opportunities.append(
                ResearchOpportunity(
                    insight=f"Identified customer pain point: {str(gap)}",
                    market_gap="Bottleneck in visitor trust or inquiry submission.",
                    feature_solution="Counter this directly with transparent guarantees, clear pricing hints, or easy booking.",
                )
            )

    return opportunities[:5]


def infer_conversion_goal(
    lead: Lead,
    research: LeadResearch | None = None,
    requested_goal: str | None = None,
) -> tuple[str, str, str]:
    """Return (goal_key, cta_label, cta_directive) tailored to the lead's business archetype."""
    if requested_goal and requested_goal not in {"calls", ""}:
        key = requested_goal
    else:
        archetype = detect_business_archetype(lead, research)
        if archetype == "dental":
            key = "bookings"
        elif archetype == "restaurant":
            key = "reserve_table"
        elif archetype == "contractor":
            key = "quotes"
        elif archetype == "agency":
            key = "book_consultation"
        elif archetype == "professional":
            key = "book_consultation"
        elif archetype == "real_estate":
            key = "schedule_viewing"
        else:
            key = "calls"

    goal_specs: dict[str, tuple[str, str]] = {
        "bookings": (
            "Book Appointment",
            "Primary action: Online appointment scheduling. Use a prominent button (e.g. 'Book Your Visit' or 'Schedule Online').",
        ),
        "reserve_table": (
            "Reserve a Table",
            "Primary action: Table reservation. Use an appetizing CTA button (e.g. 'Reserve a Table' or 'Book a Table').",
        ),
        "quotes": (
            "Request a Quote",
            "Primary action: Free quote or estimate. Use high-contrast button (e.g. 'Get Free Estimate' or 'Request a Quote').",
        ),
        "book_consultation": (
            "Book Free Consultation",
            "Primary action: Private consultation. Use high-ticket CTA (e.g. 'Book Strategy Session' or 'Schedule Consultation').",
        ),
        "schedule_viewing": (
            "Schedule a Viewing",
            "Primary action: Property or facility viewing. Use clear tour CTA (e.g. 'Schedule Private Viewing').",
        ),
        "request_demo": (
            "Request a Demo",
            "Primary action: Product demonstration (e.g. 'Request a Demo' or 'Get Started Free').",
        ),
        "calls": (
            "Call Now",
            "Primary action: Direct telephone call. Display phone link prominently (tel: link) with 'Call Today'.",
        ),
        "whatsapp": (
            "Chat on WhatsApp",
            "Primary action: Direct WhatsApp chat enquiry with pre-filled message support.",
        ),
        "visit_location": (
            "Visit Us Today",
            "Primary action: Direct store or clinic visit. Prominently showcase address, map link, and opening hours.",
        ),
    }

    label, directive = goal_specs.get(
        key,
        ("Contact Us", "Primary action: Contact the business directly via call or message."),
    )
    return key, label, directive
