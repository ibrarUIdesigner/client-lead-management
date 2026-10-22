"""Intelligent Image Planner & Ranking Service for website mockups.

Plans specific image slots (Hero, Core Services, Facility/About) with tailored
search queries, composition guidelines, and Unsplash -> Pixabay ranking.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings, get_settings
from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit
from app.services.mockup_images import (
    search_pixabay,
    search_unsplash,
)
from app.services.mockup_section_planner import PlannedSection, detect_business_archetype

logger = logging.getLogger(__name__)


@dataclass
class ImageSlotRequirement:
    slot_index: int
    role: str
    filename: str
    section_id: str
    purpose: str
    subject: str
    style: str
    orientation: str
    composition: str
    search_queries: list[str]


def plan_image_requirements(
    lead: Lead,
    audit: WebsiteAudit | None = None,
    research: LeadResearch | None = None,
    planned_sections: list[PlannedSection] | None = None,
) -> list[ImageSlotRequirement]:
    """Create a structured 4-image requirement plan based on lead niche and research."""
    archetype = detect_business_archetype(lead, research)
    industry = (lead.industry or "").strip().lower()
    name = (lead.business_name or "").strip()

    # Extract specific service offerings from research
    research_services = ""
    if research and isinstance(research.research_data, dict):
        raw = research.research_data.get("services_and_offerings") or ""
        if isinstance(raw, str):
            research_services = raw
        elif isinstance(raw, list):
            research_services = " ".join(str(item) for item in raw)

    first_words = [w for w in re.sub(r"[^a-zA-Z\s]", "", research_services).split() if len(w) > 3][:3]
    service_highlight = " ".join(first_words) if first_words else "professional services"

    if archetype == "dental":
        return [
            ImageSlotRequirement(
                slot_index=0,
                role="hero",
                filename="hero-banner.jpg",
                section_id="hero",
                purpose="Establish an ultra-clean, welcoming, and high-trust medical first impression.",
                subject="Modern luxury dental clinic interior with clean dental chair and floor-to-ceiling windows.",
                style="Bright, clinical, architectural, calming, reassuring.",
                orientation="landscape",
                composition="Subject positioned on right with ample negative space on the left for the headline.",
                search_queries=[
                    "modern dental clinic interior",
                    "luxury dental office clinic",
                    "contemporary dentist office interior",
                ],
            ),
            ImageSlotRequirement(
                slot_index=1,
                role="service_1",
                filename="service-primary.jpg",
                section_id="treatments",
                purpose="Showcase advanced patient care and clinical precision.",
                subject="Dentist performing gentle examination or teeth cleaning with modern instruments.",
                style="Focused, friendly, professional, bright lighting.",
                orientation="landscape",
                composition="Centered patient-dentist interaction with shallow depth of field.",
                search_queries=[
                    "dentist patient care examination",
                    "cosmetic dentistry teeth whitening",
                    "dental doctor consultation",
                ],
            ),
            ImageSlotRequirement(
                slot_index=2,
                role="service_2",
                filename="service-secondary.jpg",
                section_id="treatments",
                purpose="Highlight cutting-edge dental technology and sterilized equipment.",
                subject="Modern orthodontic tools, digital 3D dental scanners, or clinic equipment.",
                style="High-tech, sterile, precise, modern.",
                orientation="landscape",
                composition="Crisp close-up of modern dental technology.",
                search_queries=[
                    "dental equipment modern clinic",
                    "orthodontic teeth care clinic",
                    "medical dental instruments clean",
                ],
            ),
            ImageSlotRequirement(
                slot_index=3,
                role="about",
                filename="team-about.jpg",
                section_id="why_us",
                purpose="Personalize the clinic with warm doctor and staff presence.",
                subject="Smiling, welcoming dentist or friendly clinic reception lounge.",
                style="Warm, approachable, professional healthcare.",
                orientation="landscape",
                composition="Friendly doctor portrait or welcoming clinic waiting lounge.",
                search_queries=[
                    "friendly dentist doctor smiling",
                    "modern clinic waiting lounge interior",
                    "dental team smiling healthcare",
                ],
            ),
        ]

    elif archetype == "restaurant":
        return [
            ImageSlotRequirement(
                slot_index=0,
                role="hero",
                filename="hero-banner.jpg",
                section_id="hero",
                purpose="Stimulate immediate appetite and showcase dining atmosphere.",
                subject="Elegantly plated signature gourmet dish or stylish restaurant interior at evening.",
                style="Moody, artisanal, mouthwatering, sophisticated lighting.",
                orientation="landscape",
                composition="Striking culinary focus with negative space on left for restaurant name and reservation CTA.",
                search_queries=[
                    f"artisan {industry or 'restaurant'} food plating",
                    "modern cozy restaurant interior dining",
                    "fine dining gourmet food plating",
                ],
            ),
            ImageSlotRequirement(
                slot_index=1,
                role="service_1",
                filename="service-primary.jpg",
                section_id="signature_dishes",
                purpose="Highlight specialty dish and culinary craftsmanship.",
                subject="Fresh chef-crafted specialty entree with vibrant ingredients.",
                style="Rich colors, warm natural light, food editorial photography.",
                orientation="landscape",
                composition="Overhead or 45-degree angle of fresh appetizing culinary creation.",
                search_queries=[
                    "chef signature dish gourmet",
                    "artisan bistro fresh entree dining",
                    "authentic culinary dish plate",
                ],
            ),
            ImageSlotRequirement(
                slot_index=2,
                role="service_2",
                filename="service-secondary.jpg",
                section_id="signature_dishes",
                purpose="Feature beverage pairing, cocktails, or artisanal bakery/dessert.",
                subject="Craft cocktail on polished bar counter or freshly baked artisan goods.",
                style="Artisanal, refreshing, crafted, elegant bar ambiance.",
                orientation="landscape",
                composition="Close up of cocktail with citrus garnish or bakery selection.",
                search_queries=[
                    "craft cocktail modern bar lounge",
                    "artisan pastry dessert bakery",
                    "wine glass fine dining table",
                ],
            ),
            ImageSlotRequirement(
                slot_index=3,
                role="about",
                filename="team-about.jpg",
                section_id="about_story",
                purpose="Convey warmth of hospitality and chef passion.",
                subject="Chef prepping in kitchen or inviting dining table arrangement.",
                style="Warm, candid, authentic hospitality.",
                orientation="landscape",
                composition="Action shot of chef finishing plate or warm dining ambiance.",
                search_queries=[
                    "chef cooking kitchen authentic",
                    "restaurant table setting ambiance",
                    "cozy cafe barista coffee",
                ],
            ),
        ]

    elif archetype == "contractor":
        return [
            ImageSlotRequirement(
                slot_index=0,
                role="hero",
                filename="hero-banner.jpg",
                section_id="hero",
                purpose="Demonstrate precision craftsmanship and pristine home transformation.",
                subject="Beautiful finished modern residential exterior or luxury remodel.",
                style="Bright daylight, high-end architecture, clean lines.",
                orientation="landscape",
                composition="Wide shot of finished building/roof with negative space for headline.",
                search_queries=[
                    f"modern {industry or 'roofing construction'} residential",
                    "luxury home exterior renovation",
                    "modern architecture residential house",
                ],
            ),
            ImageSlotRequirement(
                slot_index=1,
                role="service_1",
                filename="service-primary.jpg",
                section_id="services",
                purpose="Illustrate skilled technicians actively executing high-standard work.",
                subject="Professional contractor inspecting blueprints or installing materials.",
                style="Active, diligent, safety-compliant, professional.",
                orientation="landscape",
                composition="Technician in uniform working with precision tools.",
                search_queries=[
                    f"professional {industry or 'contractor'} installing",
                    "electrician contractor working tools",
                    "roofing contractor working roof",
                ],
            ),
            ImageSlotRequirement(
                slot_index=2,
                role="service_2",
                filename="service-secondary.jpg",
                section_id="projects",
                purpose="Showcase immaculate project results and durability.",
                subject="Newly renovated interior room, modern roofline, or clean plumbing installation.",
                style="Pristine, finished, high-craftsmanship.",
                orientation="landscape",
                composition="Finished project showcase highlighting durability and detail.",
                search_queries=[
                    "modern home remodel renovation",
                    "contractor finished project house",
                    "clean architectural building interior",
                ],
            ),
            ImageSlotRequirement(
                slot_index=3,
                role="about",
                filename="team-about.jpg",
                section_id="why_us",
                purpose="Reinforce trust, family ownership, and licensed professionalism.",
                subject="Friendly contractor team or contractor consulting warmly with homeowner.",
                style="Honest, trustworthy, licensed, reassuring.",
                orientation="landscape",
                composition="Contractor reviewing estimate with satisfied client.",
                search_queries=[
                    "contractor consulting homeowner smile",
                    "friendly construction team workers",
                    "professional trade contractor consultation",
                ],
            ),
        ]

    else:
        # General & Professional Businesses
        return [
            ImageSlotRequirement(
                slot_index=0,
                role="hero",
                filename="hero-banner.jpg",
                section_id="hero",
                purpose="Establish credibility, modern capability, and premium positioning.",
                subject=f"Modern stylish {industry or 'business'} environment or executive workspace.",
                style="Clean, bright, contemporary corporate editorial.",
                orientation="landscape",
                composition="Wide view with calm subject on right and negative space for value prop on left.",
                search_queries=[
                    f"modern {industry or 'corporate'} business office",
                    f"professional {industry or 'creative'} workspace",
                    "contemporary architecture office workplace",
                ],
            ),
            ImageSlotRequirement(
                slot_index=1,
                role="service_1",
                filename="service-primary.jpg",
                section_id="services",
                purpose="Feature core client collaboration or primary deliverable.",
                subject=f"Professional consultation, digital strategy, or {service_highlight}.",
                style="Sharp, focused, collaborative, energetic.",
                orientation="landscape",
                composition="Team collaborating around modern desk or screen.",
                search_queries=[
                    f"professional {industry or 'business'} consultation",
                    "business team collaboration strategy meeting",
                    "modern service team working",
                ],
            ),
            ImageSlotRequirement(
                slot_index=2,
                role="service_2",
                filename="service-secondary.jpg",
                section_id="services",
                purpose="Highlight specialized expertise and high-standard delivery.",
                subject="Detailed client deliverable, modern technology setup, or project execution.",
                style="Sleek, organized, high-resolution detail.",
                orientation="landscape",
                composition="Focused detail of project delivery or technology workflow.",
                search_queries=[
                    "modern business technology workflow",
                    "creative design workspace desk",
                    "corporate strategy planning detail",
                ],
            ),
            ImageSlotRequirement(
                slot_index=3,
                role="about",
                filename="team-about.jpg",
                section_id="about",
                purpose="Foster client trust and personal rapport.",
                subject="Friendly, confident business leadership team or welcoming office entrance.",
                style="Approachable, authentic, prestigious.",
                orientation="landscape",
                composition="Confident professional portrait or welcoming modern reception.",
                search_queries=[
                    "professional business team smiling office",
                    "confident business leader portrait",
                    "modern corporate office reception lounge",
                ],
            ),
        ]


def rank_and_fetch_stock_images(
    requirements: list[ImageSlotRequirement],
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Execute curated search queries per image slot with Unsplash -> Pixabay ranking."""
    cfg = settings or get_settings()
    has_unsplash = bool(cfg.unsplash_access_key.strip())
    has_pixabay = bool(cfg.pixabay_api_key.strip())

    if not has_unsplash and not has_pixabay:
        return []

    assets: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for req in requirements:
        slot_photo: dict[str, Any] | None = None

        # 1. Try Unsplash queries for this specific requirement
        if has_unsplash:
            for query in req.search_queries:
                try:
                    results = search_unsplash(query, cfg.unsplash_access_key, count=6, client=client)
                    for photo in results:
                        u = photo.get("url")
                        if u and u not in seen_urls:
                            seen_urls.add(u)
                            slot_photo = {
                                "id": str(uuid4()),
                                "filename": req.filename,
                                "role": req.role,
                                "url": u,
                                "alt": photo.get("alt") or req.purpose,
                                "source": "unsplash",
                                "query_used": query,
                                "content_type": "image/jpeg",
                            }
                            break
                    if slot_photo:
                        break
                except Exception as u_err:
                    logger.warning("unsplash_slot_error: %s", u_err)

        # 2. Fallback to Pixabay if slot wasn't filled
        if not slot_photo and has_pixabay:
            for query in req.search_queries:
                try:
                    results = search_pixabay(query, cfg.pixabay_api_key, count=6, client=client)
                    for photo in results:
                        u = photo.get("url")
                        if u and u not in seen_urls:
                            seen_urls.add(u)
                            slot_photo = {
                                "id": str(uuid4()),
                                "filename": req.filename,
                                "role": req.role,
                                "url": u,
                                "alt": photo.get("alt") or req.purpose,
                                "source": "pixabay",
                                "query_used": query,
                                "content_type": "image/jpeg",
                            }
                            break
                    if slot_photo:
                        break
                except Exception as p_err:
                    logger.warning("pixabay_slot_error: %s", p_err)

        if slot_photo:
            assets.append(slot_photo)

    return assets
