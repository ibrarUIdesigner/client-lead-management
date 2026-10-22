"""Intelligent, evidence-based section planner for website mockups.

Analyzes lead profile, audit findings, and research insights to select 7-10
high-converting, business-specific sections rather than a generic template.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit

logger = logging.getLogger(__name__)

SectionPriority = Literal["ESSENTIAL", "RECOMMENDED", "OPTIONAL"]


@dataclass
class PlannedSection:
    id: str
    name: str
    priority: SectionPriority
    rationale: str
    directive: str


def detect_business_archetype(
    lead: Lead,
    research: LeadResearch | None = None,
) -> str:
    """Classify the business into an archetype based on industry, name, and services."""
    industry = (lead.industry or "").lower()
    name = (lead.business_name or "").lower()
    desc = (lead.description or "").lower()
    research_text = ""
    if research and isinstance(research.research_data, dict):
        research_text = str(research.research_data.get("services_and_offerings") or "").lower()

    combined = f"{industry} {name} {desc} {research_text}"

    if any(k in combined for k in ("dental", "dentist", "orthodont", "teeth")):
        return "dental"
    if any(k in combined for k in ("restaurant", "cafe", "bistro", "bakery", "bar", "pizza", "dining", "food")):
        return "restaurant"
    if any(k in combined for k in ("roofing", "plumb", "electric", "hvac", "contractor", "construction", "remodel", "paint", "landscap")):
        return "contractor"
    if any(k in combined for k in ("agency", "marketing", "web design", "software", "development", "seo", "branding")):
        return "agency"
    if any(k in combined for k in ("law", "attorney", "legal", "accounting", "cpa", "tax", "financial", "consult")):
        return "professional"
    if any(k in combined for k in ("gym", "fitness", "yoga", "spa", "salon", "wellness", "massage", "chiro", "clinic", "health")):
        return "wellness"
    if any(k in combined for k in ("real estate", "realtor", "property", "brokerage")):
        return "real_estate"
    return "general"


def plan_sections(
    lead: Lead,
    audit: WebsiteAudit | None = None,
    findings: list[str] | None = None,
    research: LeadResearch | None = None,
    goal: str = "calls",
) -> list[PlannedSection]:
    """Plan an evidence-based list of 7-10 tailored sections for the mockup."""
    archetype = detect_business_archetype(lead, research)
    findings_list = findings or []
    has_audit = audit is not None or bool(findings_list)

    # Audit clues
    weak_cta = any("cta" in f.lower() or "call to action" in f.lower() for f in findings_list)
    poor_mobile = any("mobile" in f.lower() or "viewport" in f.lower() for f in findings_list)
    weak_trust = any("social" in f.lower() or "review" in f.lower() or "trust" in f.lower() for f in findings_list)
    weak_services = any("service" in f.lower() or "navigation" in f.lower() for f in findings_list)

    # Research clues
    proactive = []
    if research and isinstance(research.research_data, dict):
        proactive = research.research_data.get("proactive_solutions") or []
        if isinstance(proactive, list):
            proactive = [str(p).lower() for p in proactive]

    wants_booking = any("book" in p or "appointment" in p or "reserv" in p for p in proactive) or goal in {"bookings", "reserve_table"}
    wants_quotes = any("quote" in p or "estimate" in p for p in proactive) or goal in {"quotes"}

    sections: list[PlannedSection] = []

    # 1. Header (Universal)
    sections.append(
        PlannedSection(
            id="header",
            name="Navigation Header",
            priority="ESSENTIAL",
            rationale="Essential anchor for brand identity and direct navigation." + (
                " Redesigned mobile-first to solve audit navigation issues." if poor_mobile or weak_cta else ""
            ),
            directive="Clean horizontal bar with exact business name, concise section anchors, phone/contact info, and a distinct primary CTA button.",
        )
    )

    # 2. Hero Section (Universal)
    sections.append(
        PlannedSection(
            id="hero",
            name="Hero Showcase",
            priority="ESSENTIAL",
            rationale="Primary conversion focal point. Immediately answers what the business offers, location, and clear next action." + (
                " Solves audit finding of missing or weak primary CTA." if weak_cta else ""
            ),
            directive="High-impact hero with asset:0 imagery, verified business positioning headline, supporting subtitle, location badge, and primary conversion button.",
        )
    )

    # 3. Trust Bar / Credential Strip
    sections.append(
        PlannedSection(
            id="trust_bar",
            name="Trust & Credential Strip",
            priority="RECOMMENDED" if weak_trust or has_audit else "OPTIONAL",
            rationale="Addresses audit weakness in initial trust signals and reassures local customers immediately below the fold.",
            directive="Concise strip highlighting verified credentials, local reputation, licensing/cleanliness, or satisfied clientele badges without fabricating fake stats.",
        )
    )

    # 4. Archetype Specific Offerings & Proof
    if archetype == "dental":
        sections.extend([
            PlannedSection(
                id="treatments",
                name="Treatments & Services Grid",
                priority="ESSENTIAL",
                rationale="Audit and research emphasize patient need for clear treatment offerings and transparent care options.",
                directive="Feature core treatments (e.g. Preventative Care, Cosmetic Whitening, Implants, Orthodontics) using asset:1 and asset:2 with benefit bullet points.",
            ),
            PlannedSection(
                id="why_us",
                name="Why Choose Our Clinic",
                priority="RECOMMENDED",
                rationale="Differentiates practice against local competitors using comfort-first and modern technology messaging.",
                directive="Highlight gentle patient care, advanced diagnostics, flexible scheduling, and comforting clinic environment.",
            ),
            PlannedSection(
                id="patient_reviews",
                name="Patient Experiences & Testimonials",
                priority="RECOMMENDED",
                rationale="Social proof is the #1 decision driver for dental visits; closes audit gap on customer reassurance.",
                directive="Clean card grid with verified patient quotes or [Verified Patient Review] placeholders with star indicators.",
            ),
            PlannedSection(
                id="booking_cta",
                name="Online Appointment Booking",
                priority="ESSENTIAL",
                rationale="Primary conversion objective; fulfills research recommendation for streamlined digital scheduling.",
                directive="Prominent booking panel with straightforward date/time selector placeholder and 'Schedule Visit' button.",
            ),
            PlannedSection(
                id="location_hours",
                name="Clinic Location & Operating Hours",
                priority="ESSENTIAL",
                rationale="Patients require precise location, parking access, and office hours for local visits.",
                directive="Clear address card for the named city, emergency contact line, and weekday/weekend operating schedule.",
            ),
        ])

    elif archetype == "restaurant":
        sections.extend([
            PlannedSection(
                id="signature_dishes",
                name="Signature Dishes & Chef Highlights",
                priority="ESSENTIAL",
                rationale="Visual appetite appeal is crucial for dining decisions; showcases prime culinary offerings.",
                directive="Mouthwatering culinary cards using asset:1 and asset:2 with dish descriptions, seasonal ingredients, and dietary tags.",
            ),
            PlannedSection(
                id="menu_overview",
                name="Curated Menu Highlights",
                priority="RECOMMENDED",
                rationale="Solves audit issue where menu and dining options were obscured or difficult to navigate.",
                directive="Tabbed or categorized menu overview (Appetizers, Mains, Cocktails/Desserts) with clear typography and pricing placeholders.",
            ),
            PlannedSection(
                id="about_story",
                name="Culinary Heritage & Atmosphere",
                priority="RECOMMENDED",
                rationale="Builds brand warmth, highlighting fresh sourcing, craft ingredients, and dining atmosphere.",
                directive="Warm narrative using asset:3 highlighting authentic hospitality, chef background, and local neighborhood connection.",
            ),
            PlannedSection(
                id="reviews",
                name="Guest Impressions & Press",
                priority="RECOMMENDED",
                rationale="Reinforces dining quality and local reputation identified in lead research.",
                directive="Elegantly styled review quotes from patrons praising the hospitality, flavors, and ambiance.",
            ),
            PlannedSection(
                id="reservation_cta",
                name="Table Reservation & Private Events",
                priority="ESSENTIAL",
                rationale="Main conversion goal; makes reserving a table frictionless for dinner or lunch parties.",
                directive="Interactive reservation trigger with party size, date/time pickers, and 'Reserve a Table' CTA.",
            ),
            PlannedSection(
                id="location_hours",
                name="Dining Hours & Location Map",
                priority="ESSENTIAL",
                rationale="Direct logistical necessity for restaurant visitors; displays address, transit/parking, and service hours.",
                directive="Prominent location card, phone line, lunch/dinner hours, and neighborhood location info.",
            ),
        ])

    elif archetype == "contractor":
        sections.extend([
            PlannedSection(
                id="services",
                name="Core Trade Services",
                priority="ESSENTIAL",
                rationale="Solves audit gap where trade specialties and emergency repairs were unclear.",
                directive="Grid of specific services (residential, commercial, repairs, installations) with asset:1 and asset:2 imagery.",
            ),
            PlannedSection(
                id="projects",
                name="Featured Work & Recent Projects",
                priority="RECOMMENDED",
                rationale="Visual proof of quality and craftsmanship is the primary driver of homeowner contractor hires.",
                directive="Showcase cards of completed projects with project scope, materials used, and pristine finishing photos.",
            ),
            PlannedSection(
                id="process",
                name="Our 3-Step Work Process",
                priority="RECOMMENDED",
                rationale="Reduces homeowner anxiety by clarifying step-by-step progress from free estimate to final inspection.",
                directive="Clean numbered sequence: 1) On-Site Assessment, 2) Upfront Estimate & Planning, 3) Precision Execution & Warranty.",
            ),
            PlannedSection(
                id="reviews",
                name="Homeowner Reviews & Guarantees",
                priority="ESSENTIAL",
                rationale="Closes trust deficit identified in audit; highlights workmanship warranty and licensed status.",
                directive="Reviews with verified homeowner tags, satisfaction guarantee seal, and insurance/licensing badges.",
            ),
            PlannedSection(
                id="service_areas",
                name="Service Areas & Coverage",
                priority="RECOMMENDED",
                rationale="Research confirms customers need assurance that contractor serves their specific neighborhood or county.",
                directive="List of covered cities/neighborhoods surrounding the lead's location with rapid dispatch badge.",
            ),
            PlannedSection(
                id="quote_cta",
                name="Instant Quote Request & Emergency Call",
                priority="ESSENTIAL",
                rationale="Main conversion goal; provides dual action for urgent emergency calls or scheduled free quotes.",
                directive="High-contrast quote request form and click-to-call emergency badge with zero-obligation guarantee.",
            ),
        ])

    elif archetype == "agency":
        sections.extend([
            PlannedSection(
                id="services",
                name="Strategic Capabilities & Services",
                priority="ESSENTIAL",
                rationale="Closes audit issue of vague positioning; clearly defines core agency deliverables.",
                directive="Structured service columns (e.g. Design, Development, Growth, Brand Strategy) with clear outcomes.",
            ),
            PlannedSection(
                id="case_studies",
                name="Selected Work & Case Studies",
                priority="ESSENTIAL",
                rationale="Prospective clients evaluate agencies almost exclusively on portfolio caliber and measurable ROI.",
                directive="Editorial project showcases using asset:1 and asset:2 with client problem, strategy, and metric results.",
            ),
            PlannedSection(
                id="methodology",
                name="Our Strategic Process",
                priority="RECOMMENDED",
                rationale="Shows structured rigor and senior delivery capabilities, preventing commoditized pricing.",
                directive="Phased timeline: Discovery & Audit -> Strategy & Architecture -> Design & Build -> Optimization & Growth.",
            ),
            PlannedSection(
                id="testimonials",
                name="Client Partnerships & Testimonials",
                priority="RECOMMENDED",
                rationale="Reinforces credibility and executive endorsement as highlighted in research.",
                directive="Executive quotes focusing on business impact, communication transparency, and project success.",
            ),
            PlannedSection(
                id="consultation_cta",
                name="Strategy Consultation CTA",
                priority="ESSENTIAL",
                rationale="Primary high-ticket conversion funnel; invites qualified prospects to a private discovery call.",
                directive="Focused callout box with 'Book a 30-Minute Strategy Session' button and simple calendar placeholder.",
            ),
        ])

    elif archetype == "professional":
        sections.extend([
            PlannedSection(
                id="practice_areas",
                name="Practice Areas & Legal / Financial Advisory",
                priority="ESSENTIAL",
                rationale="Visitors require immediate confirmation that the firm handles their specific matter.",
                directive="Authoritative practice area grid with asset:1 and asset:2 detailing specialized advisory services.",
            ),
            PlannedSection(
                id="firm_overview",
                name="Firm Philosophy & Track Record",
                priority="RECOMMENDED",
                rationale="Addresses audit finding of impersonal branding; establishes prestige and integrity.",
                directive="Sophisticated overview using asset:3 highlighting partner attention, ethics, and rigorous representation.",
            ),
            PlannedSection(
                id="why_us",
                name="Why Choose Our Practice",
                priority="RECOMMENDED",
                rationale="Separates firm from competitors by highlighting responsiveness, clear fee structures, and dedicated counsel.",
                directive="Key pillars: Direct Partner Access, Transparent Pricing, Strategic Guidance, Proven Track Record.",
            ),
            PlannedSection(
                id="client_reviews",
                name="Client Testimonials & Recognition",
                priority="RECOMMENDED",
                rationale="High-stakes professional decisions depend heavily on peer and client validation.",
                directive="Subtle, distinguished testimonials and professional association/bar badges.",
            ),
            PlannedSection(
                id="consultation_cta",
                name="Confidential Consultation Request",
                priority="ESSENTIAL",
                rationale="Primary conversion goal; enables secure, confidential contact with the practice.",
                directive="Discreet, professional consultation form with encrypted disclaimer and direct office phone line.",
            ),
        ])

    else:
        # General Local Business Archetype
        sections.extend([
            PlannedSection(
                id="services",
                name="Services & Offerings",
                priority="ESSENTIAL",
                rationale="Directly solves audit finding regarding clear presentation of primary business offerings.",
                directive="Clear service cards using asset:1 and asset:2 with benefits and descriptive bullet points.",
            ),
            PlannedSection(
                id="why_choose_us",
                name="Why Choose Us / Benefits",
                priority="RECOMMENDED",
                rationale="Clarifies customer value proposition and competitive advantage identified in research.",
                directive="3-4 distinct value pillars highlighting quality, customer care, experience, and reliability.",
            ),
            PlannedSection(
                id="about",
                name="About Our Business",
                priority="RECOMMENDED",
                rationale="Establishes local roots, authentic mission, and personal connection to the community.",
                directive="Compelling story using asset:3 detailing passion for service, craftsmanship, and local pride.",
            ),
            PlannedSection(
                id="reviews",
                name="Customer Reviews & Social Proof",
                priority="RECOMMENDED",
                rationale="Provides evidence of satisfaction and addresses audit gaps in social proof.",
                directive="Customer review quotes with 5-star ratings and verified local customer badges.",
            ),
            PlannedSection(
                id="conversion_cta",
                name="Primary Call to Action",
                priority="ESSENTIAL",
                rationale="Primary conversion milestone ensuring prospective customers take immediate action.",
                directive="Prominent banner with high-contrast button tailored to the primary goal and direct phone access.",
            ),
            PlannedSection(
                id="contact_location",
                name="Contact & Location Information",
                priority="ESSENTIAL",
                rationale="Fulfills visitor requirement for location, business hours, and direct communication channels.",
                directive="Clean card with business address, phone, email, and weekly operating hours.",
            ),
        ])

    # Universal Closing: Footer
    sections.append(
        PlannedSection(
            id="footer",
            name="Website Footer",
            priority="ESSENTIAL",
            rationale="Professional closure with copyright, verified contact, social profiles, and legal links.",
            directive="Clean multi-column footer with business brand, quick section links, operating hours, phone, and copyright notice.",
        )
    )

    logger.info("Planned %d evidence-based sections for archetype '%s'", len(sections), archetype)
    return sections
