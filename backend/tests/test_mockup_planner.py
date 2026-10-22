from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit
from app.services.mockup_content_planner import (
    infer_conversion_goal,
    plan_audit_improvements,
    plan_research_opportunities,
)
from app.services.mockup_image_planner import plan_image_requirements
from app.services.mockup_planner import MockupPlanner
from app.services.mockup_section_planner import (
    detect_business_archetype,
    plan_sections,
)


def _make_lead(industry: str, name: str, website: str | None = None) -> Lead:
    return Lead(
        id=uuid4(),
        business_name=name,
        industry=industry,
        website_url=website,
    )


def test_detect_business_archetype():
    assert detect_business_archetype(_make_lead("Dental Clinic", "Smile Bright")) == "dental"
    assert detect_business_archetype(_make_lead("Dentist", "Downtown Orthodontics")) == "dental"
    assert detect_business_archetype(_make_lead("Restaurant", "Tartinery Cafe - Bar")) == "restaurant"
    assert detect_business_archetype(_make_lead("Italian Dining", "Luigi Trattoria")) == "restaurant"
    assert detect_business_archetype(_make_lead("Plumber", "Apex Plumbing & Heating")) == "contractor"
    assert detect_business_archetype(_make_lead("Roofing", "Highline Roofing Contractors")) == "contractor"
    assert detect_business_archetype(_make_lead("Digital Marketing Agency", "Pixel Craft")) == "agency"
    assert detect_business_archetype(_make_lead("Software Studio", "Nova SaaS")) == "agency"
    assert detect_business_archetype(_make_lead("Law Firm", "Smith & Associates Attorneys")) == "professional"
    assert detect_business_archetype(_make_lead("Accountant", "Apex Tax Advisors")) == "professional"
    assert detect_business_archetype(_make_lead("Retail", "Corner Store")) == "general"


def test_plan_sections_dental():
    lead = _make_lead("Dental Clinic", "Smile Dental", "https://smiledental.com")
    sections = plan_sections(lead)
    assert 7 <= len(sections) <= 10
    names = [s.name for s in sections]
    assert any("hero" in n.lower() for n in names)
    assert any("treatments" in n.lower() or "services" in n.lower() for n in names)
    assert any("booking" in n.lower() or "appointment" in n.lower() for n in names)
    assert any("location" in n.lower() or "hours" in n.lower() for n in names)


def test_plan_sections_restaurant():
    lead = _make_lead("Restaurant", "Tartinery Cafe")
    sections = plan_sections(lead)
    assert 7 <= len(sections) <= 10
    names = [s.name for s in sections]
    assert any("hero" in n.lower() for n in names)
    assert any("menu" in n.lower() or "dish" in n.lower() for n in names)
    assert any("reservation" in n.lower() for n in names)


def test_infer_conversion_goal():
    dental_lead = _make_lead("Dental Clinic", "Smile Dental")
    restaurant_lead = _make_lead("Restaurant", "Tartinery")
    contractor_lead = _make_lead("Roofing", "Summit Roofs")
    agency_lead = _make_lead("Agency", "Peak Design")

    goal, label, directive = infer_conversion_goal(dental_lead)
    assert goal == "bookings"
    assert "Appointment" in label

    goal, label, _ = infer_conversion_goal(restaurant_lead)
    assert goal == "reserve_table"
    assert "Table" in label

    goal, _, _ = infer_conversion_goal(contractor_lead)
    assert goal == "quotes"

    goal, _, _ = infer_conversion_goal(agency_lead)
    assert goal == "book_consultation"

    # When explicitly provided, user goal wins
    goal, _, _ = infer_conversion_goal(dental_lead, requested_goal="whatsapp")
    assert goal == "whatsapp"


def test_plan_audit_improvements():
    audit = WebsiteAudit(
        lead_id=uuid4(),
        status="COMPLETED",
        has_clear_cta=False,
        is_mobile_responsive=False,
    )
    findings = [
        "No clear call-to-action button found above the fold.",
        "Mobile navigation and viewport layout breaks on narrow screens.",
        "Missing meta description and search headings.",
    ]
    improvements = plan_audit_improvements(audit, findings)
    assert len(improvements) >= 3
    solutions = " ".join(imp.mockup_solution for imp in improvements)
    assert "CTA" in solutions or "call" in solutions or "navigation" in solutions


def test_plan_research_opportunities():
    research = LeadResearch(
        lead_id=uuid4(),
        status="COMPLETED",
        summary="Competitors in Manhattan fail to provide weekend hours. Patients value modern sedation dentistry.",
        research_data={
            "proactive_solutions": [
                "Highlight weekend emergency availability.",
                "Prominently feature pain-free sedation options.",
            ]
        },
    )
    opps = plan_research_opportunities(research)
    assert len(opps) >= 2
    assert any("weekend" in o.insight.lower() for o in opps)


def test_plan_image_requirements():
    lead = Lead(
        id=uuid4(),
        business_name="Gentle Dental Care",
        industry="Dental",
        city="Chicago",
    )
    sections = plan_sections(lead)
    reqs = plan_image_requirements(lead, None, None, sections)
    assert len(reqs) >= 3
    roles = [r.role for r in reqs]
    assert "hero" in roles
    assert any("service" in r for r in roles)


def test_mockup_planner_end_to_end():
    lead = Lead(
        id=uuid4(),
        business_name="Bistro Parisien",
        industry="French Restaurant",
        city="New York",
        country="USA",
        description="Authentic French bistro in downtown Soho.",
    )
    planner = MockupPlanner(settings=None)
    plan = planner.build_plan(lead=lead)

    assert plan.archetype == "restaurant"
    assert plan.goal_key == "reserve_table"
    assert "Reserve a Table" in plan.cta_label
    assert 7 <= len(plan.planned_sections) <= 10
    assert "Bistro Parisien" in plan.brief_text
    assert "EVIDENCE-BASED SECTION ARCHITECTURE" in plan.brief_text
    assert "PRIMARY CONVERSION OBJECTIVE" in plan.brief_text
