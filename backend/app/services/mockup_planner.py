"""Unified Mockup Planner: Orchestrates Section, Content, and Image Planning.

Transforms generic mockup generation into an intelligent, data-driven agency proposal
specifically built for the selected lead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit
from app.services.mockup_content_planner import (
    AuditImprovement,
    ResearchOpportunity,
    infer_conversion_goal,
    plan_audit_improvements,
    plan_research_opportunities,
)
from app.services.mockup_image_planner import (
    ImageSlotRequirement,
    plan_image_requirements,
    rank_and_fetch_stock_images,
)
from app.services.mockup_section_planner import (
    PlannedSection,
    detect_business_archetype,
    plan_sections,
)

logger = logging.getLogger(__name__)


@dataclass
class MockupPlan:
    archetype: str
    goal_key: str
    cta_label: str
    cta_directive: str
    audit_improvements: list[AuditImprovement]
    research_opportunities: list[ResearchOpportunity]
    planned_sections: list[PlannedSection]
    image_requirements: list[ImageSlotRequirement]
    curated_assets: list[dict[str, Any]]
    brief_text: str


class MockupPlanner:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build_plan(
        self,
        lead: Lead,
        audit: WebsiteAudit | None = None,
        findings: list[str] | None = None,
        research: LeadResearch | None = None,
        goal: str = "calls",
        requirements: str | None = None,
        guidance: str | None = None,
        scenario: str = "new_site",
        design_score: int | None = None,
        asset_labels: list[str] | None = None,
        client: httpx.Client | None = None,
        signals: list[Any] | None = None,
        opportunities: list[Any] | None = None,
        mockup_focus: str | None = None,
        previous_html: str | None = None,
        refine_instructions: str | None = None,
    ) -> MockupPlan:
        """Run the full intelligent planning pipeline and construct the detailed brief."""
        archetype = detect_business_archetype(lead, research)
        goal_key, cta_label, cta_directive = infer_conversion_goal(lead, research, goal)

        # 1. Plan Sections
        planned_sections = plan_sections(lead, audit, findings, research, goal=goal_key)

        # 2. Plan Audit Improvements & Research Opportunities
        audit_improvements = plan_audit_improvements(audit, findings)
        research_opportunities = plan_research_opportunities(research)

        # 3. Plan Image Requirements & Fetch/Rank Curated Stock Photos
        image_reqs = plan_image_requirements(lead, audit, research, planned_sections)
        curated_assets = rank_and_fetch_stock_images(
            image_reqs,
            settings=self.settings,
            client=client,
        )

        # If asset_labels wasn't passed, build them from curated_assets
        resolved_labels: list[str] = list(asset_labels or [])
        if not resolved_labels and curated_assets:
            for idx, a in enumerate(curated_assets):
                role = a.get("role", "asset").upper()
                alt = a.get("alt", "")
                resolved_labels.append(
                    f'{a.get("filename", f"asset-{idx+1}.jpg")} [{role}] ({alt}) — use src="asset:{idx}"'
                )

        # 4. Construct the Comprehensive, Data-Driven Brief
        brief_lines: list[str] = [
            "# MOCKUP SPECIFICATION — DATA-DRIVEN BESPOKE HOMEPAGE",
            "Act as a Senior Agency UX/UI Designer, Product Architect, and Conversion Specialist.",
            "Generate one responsive, high-converting homepage as a single self-contained HTML5 document.",
            f"Business Name: {lead.business_name.strip()}",
            f"Business Archetype: {archetype.upper()} ({lead.industry or 'Local Business'})",
        ]

        loc = ", ".join(p for p in (lead.city, lead.country) if p and p.strip())
        if loc:
            brief_lines.append(f"Location: {loc}")
        if lead.description and lead.description.strip():
            brief_lines.append(f"Verified Services & About: {lead.description.strip()}")
        else:
            brief_lines.append("Verified Services: Not listed. Use verified industry offerings with [Services placeholder].")

        # Scenario
        if scenario == "redesign":
            score_txt = f"{design_score}/100" if design_score is not None else "below 50"
            brief_lines.append(
                f"Project Scenario: Redesign Concept (Current website design score: {score_txt}). "
                "The mockup MUST visibly solve the weaknesses of the existing website."
            )
        else:
            brief_lines.append(
                "Project Scenario: First Digital Homepage. "
                "Design a complete, trustworthy first impression that establishes immediate local credibility."
            )

        # Primary Conversion Goal
        brief_lines.extend([
            "",
            "## PRIMARY CONVERSION OBJECTIVE",
            f"Main Objective: {cta_label} ({goal_key})",
            f"Directive: {cta_directive}",
            "Make this primary CTA the unmistakable focal point of the Hero section and repeat it in the header navigation and pre-footer.",
        ])

        # Audit -> UX/UI Improvements
        if audit_improvements:
            brief_lines.extend([
                "",
                "## AUDIT-INFORMED UX/UI IMPROVEMENTS",
                "Your design MUST directly demonstrate solutions to these technical audit findings:",
            ])
            for imp in audit_improvements:
                brief_lines.append(f"- Issue: {imp.finding}")
                brief_lines.append(f"  * UX Problem: {imp.ux_problem}")
                brief_lines.append(f"  * Mockup Solution: {imp.mockup_solution}")

        # Research -> Market Opportunities
        if research_opportunities:
            brief_lines.extend([
                "",
                "## RESEARCH-INFORMED STRATEGIC OPPORTUNITIES",
                "Incorporate these market intelligence insights to differentiate the business from local competitors:",
            ])
            for opp in research_opportunities:
                brief_lines.append(f"- Insight: {opp.insight}")
                brief_lines.append(f"  * Strategic Opportunity: {opp.market_gap}")
                brief_lines.append(f"  * Website Implementation: {opp.feature_solution}")

        # Harvey Intelligence Signals & Opportunities
        if signals:
            brief_lines.extend([
                "",
                "## HARVEY SALES INTELLIGENCE SIGNALS & BOTTLENECK EVIDENCE",
                "Your design MUST visibly resolve these verified technical, business, and sales signals:",
            ])
            for s in signals:
                s_name = getattr(s, "name", str(s))
                s_evidence = getattr(s, "evidence", "")
                s_conf = getattr(s, "confidence", None)
                conf_txt = f" (Confidence: {int(s_conf * 100)}%)" if s_conf is not None else ""
                brief_lines.append(f"- Signal: {s_name}{conf_txt}")
                if s_evidence:
                    brief_lines.append(f"  * Evidence: {s_evidence}")

        if opportunities:
            brief_lines.extend([
                "",
                "## HIGH-IMPACT COMMERCIAL OPPORTUNITIES & RECOMMENDED SOLUTIONS",
            ])
            for opp in opportunities:
                prob = getattr(opp, "problem", str(opp))
                sol = getattr(opp, "recommended_solution", "")
                impact = getattr(opp, "impact", "HIGH")
                brief_lines.append(f"- Problem: {prob}")
                if sol:
                    brief_lines.append(f"  * Recommended Solution: {sol} [Impact: {impact}]")

        if mockup_focus:
            brief_lines.extend([
                "",
                "## BESPOKE MOCKUP STRATEGY FOCUS",
                f"Core Conversion Directive: {mockup_focus}",
            ])

        # Intelligent Section Blueprint
        brief_lines.extend([
            "",
            "## EVIDENCE-BASED SECTION ARCHITECTURE (7–10 SECTIONS)",
            "Do NOT use a generic cookie-cutter template. Build ONLY these planned sections in this exact conversion hierarchy:",
        ])
        for idx, sec in enumerate(planned_sections, 1):
            brief_lines.append(
                f"{idx:02d}. {sec.name} [{sec.priority}]"
            )
            brief_lines.append(f"    - Rationale: {sec.rationale}")
            brief_lines.append(f"    - Content Directive: {sec.directive}")

        # Curated Image Assets
        if resolved_labels:
            brief_lines.extend([
                "",
                "## CURATED IMAGE ASSETS (UNSPLASH & PIXABAY)",
                "Embed these curated stock images prominently into their designated section layouts:",
            ])
            for label in resolved_labels:
                brief_lines.append(f"- {label}")
            brief_lines.append(
                "Image Placement & Styling Directives:\n"
                "- Hero (asset:0): Use as wide landscape cover (or background-image). Style with subtle overlay for headline legibility.\n"
                "- Services / Showcase (asset:1 & asset:2): Place in primary service cards with object-fit: cover and rounded corners.\n"
                "- About / Facility (asset:3): Place in the story, trust, or team section.\n"
                "- Do NOT use any unauthorized remote image domains."
            )
        else:
            brief_lines.append(
                "No image assets provided. Use elegant CSS shapes, subtle gradients, and clean icon badges."
            )

        # Anti-Fabrication & Realistic Copy Directives
        brief_lines.extend([
            "",
            "## CONTENT RULES & ZERO FABRICATION POLICY",
            "- Write realistic, persuasive local-business copy. NEVER write generic AI filler ('We strive for excellence...').",
            "- NEVER invent fake testimonials, fake awards, fake years of experience, fake statistics, or fictional staff members.",
            "- If verified reviews are missing, use a clean placeholder like [Verified Customer Review].",
            "- Use the exact business name from the brief in the header and hero.",
            "- Contact info: Phone: " + (lead.phone or "[Phone placeholder]") + ", Email: " + (lead.email or "[Email placeholder]"),
        ])

        # Design.md Guide
        if guidance and guidance.strip():
            from app.services.design_markdown import fence_guidance
            brief_lines.extend([
                "",
                "## VISUAL DESIGN SYSTEM (DESIGN.MD)",
                fence_guidance(guidance),
            ])
        else:
            brief_lines.extend([
                "",
                "## VISUAL DESIGN SYSTEM",
                "Apply a modern, high-end agency aesthetic: generous section padding (80px+ desktop), clear typography scale, distinct primary brand color, subtle card borders (#e5e7eb), and crisp contrast.",
            ])

        # Additional user requirements
        if requirements and requirements.strip():
            brief_lines.extend([
                "",
                "## ADDITIONAL CUSTOMER INSTRUCTIONS",
                requirements.strip(),
            ])

        if previous_html and previous_html.strip():
            brief_lines.extend([
                "",
                "## PREVIOUS VERSION HTML TO REFINE",
                previous_html.strip()[:120_000],
            ])

        if refine_instructions and refine_instructions.strip():
            brief_lines.extend([
                "",
                "## REFINEMENT REQUEST",
                refine_instructions.strip(),
            ])

        brief_text = "\n".join(brief_lines)

        return MockupPlan(
            archetype=archetype,
            goal_key=goal_key,
            cta_label=cta_label,
            cta_directive=cta_directive,
            audit_improvements=audit_improvements,
            research_opportunities=research_opportunities,
            planned_sections=planned_sections,
            image_requirements=image_reqs,
            curated_assets=curated_assets,
            brief_text=brief_text,
        )
