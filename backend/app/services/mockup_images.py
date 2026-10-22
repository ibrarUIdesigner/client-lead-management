"""Stock image retrieval for website mockups via Unsplash and Pixabay."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.core.config import Settings, get_settings
from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.website_audit import WebsiteAudit

logger = logging.getLogger(__name__)

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/"

_ROLES = (
    ("hero", "hero-banner.jpg", "Homepage hero banner image"),
    ("service_1", "service-primary.jpg", "Primary service showcase image"),
    ("service_2", "service-secondary.jpg", "Secondary service feature image"),
    ("about", "team-about.jpg", "About business and professional team image"),
)

_COMMON_INDUSTRY_MAP = {
    "dental": "modern dental clinic",
    "dentist": "dentist dental care",
    "doctor": "medical clinic healthcare",
    "medical": "modern medical healthcare clinic",
    "roofing": "roofing contractor house construction",
    "plumbing": "professional plumbing repair",
    "plumber": "plumbing service repair",
    "electrician": "electrician electrical service",
    "hvac": "hvac air conditioning repair",
    "restaurant": "fine dining restaurant food",
    "cafe": "cozy coffee shop cafe",
    "bar": "modern bar lounge cocktail",
    "bakery": "artisan bakery fresh bread pastries",
    "law": "professional law firm office",
    "attorney": "attorney legal consultation",
    "legal": "lawyer corporate legal office",
    "accounting": "accounting finance professional office",
    "finance": "financial planning corporate office",
    "real estate": "luxury real estate modern home architecture",
    "realtor": "modern real estate architecture home",
    "construction": "construction commercial architecture",
    "contractor": "general contractor building renovation",
    "fitness": "fitness gym workout training",
    "gym": "modern gym fitness equipment",
    "yoga": "yoga studio wellness meditation",
    "salon": "beauty salon hair styling",
    "spa": "luxury wellness spa massage",
    "auto": "auto repair automotive workshop",
    "mechanic": "car mechanic automotive garage",
    "cleaning": "commercial cleaning janitorial service",
    "landscaping": "landscaping garden lawn care",
    "photography": "professional photography studio",
    "marketing": "modern digital marketing creative agency",
    "design": "modern creative design studio",
    "software": "modern technology software office",
    "technology": "modern high tech digital workplace",
    "hotel": "luxury boutique hotel lobby",
}


def is_allowed_stock_image_url(url: str | None) -> bool:
    """Return True if the URL points to a permitted Unsplash or Pixabay host."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        hostname = (parsed.hostname or "").lower()
        return (
            hostname == "images.unsplash.com"
            or hostname == "plus.unsplash.com"
            or hostname == "unsplash.com"
            or hostname.endswith(".unsplash.com")
            or hostname == "pixabay.com"
            or hostname == "cdn.pixabay.com"
            or hostname.endswith(".pixabay.com")
        )
    except Exception:
        return False


def derive_search_queries(
    lead: Lead,
    audit: WebsiteAudit | None = None,
    research: LeadResearch | None = None,
) -> tuple[str, str]:
    """Derive primary and secondary search queries from lead, audit, and research data."""
    industry = (lead.industry or "").strip().lower()
    name = (lead.business_name or "").strip().lower()
    description = (lead.description or "").strip().lower()

    # 1. Match from industry map
    primary_query: str | None = None
    for key, mapped in _COMMON_INDUSTRY_MAP.items():
        if key in industry or key in name:
            primary_query = mapped
            break

    # 2. Check research data for specific service offerings
    services_text = ""
    if research and isinstance(research.research_data, dict):
        raw_services = research.research_data.get("services_and_offerings") or ""
        if isinstance(raw_services, str) and raw_services.strip():
            services_text = raw_services.strip().lower()
        elif isinstance(raw_services, list):
            services_text = " ".join(str(s) for s in raw_services).lower()

    if not primary_query and services_text:
        for key, mapped in _COMMON_INDUSTRY_MAP.items():
            if key in services_text:
                primary_query = mapped
                break

    # 3. Fallback based on raw industry or business name
    if not primary_query:
        cleaned_industry = re.sub(r"[^a-zA-Z0-9\s]", " ", industry).strip()
        cleaned_industry = re.sub(r"\s+", " ", cleaned_industry)
        if cleaned_industry and len(cleaned_industry) > 2:
            primary_query = f"{cleaned_industry} business"
        else:
            cleaned_name = re.sub(r"[^a-zA-Z0-9\s]", " ", name).strip()
            tokens = [t for t in cleaned_name.split() if len(t) > 2 and t not in {"inc", "llc", "ltd", "corp", "the", "and"}]
            primary_query = " ".join(tokens[:2]) if tokens else "professional local business"

    # Secondary query for services/team
    secondary_query = f"{primary_query} professional service"
    if services_text:
        # Extract first key phrase
        words = [w for w in re.sub(r"[^a-zA-Z\s]", " ", services_text).split() if len(w) > 3][:3]
        if words:
            secondary_query = " ".join(words)
    elif description:
        words = [w for w in re.sub(r"[^a-zA-Z\s]", " ", description).split() if len(w) > 3][:3]
        if words:
            secondary_query = f"{primary_query} " + " ".join(words[:2])

    return primary_query.strip(), secondary_query.strip()


def search_unsplash(
    query: str,
    access_key: str,
    *,
    count: int = 8,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Search Unsplash for landscape photos matching query."""
    if not access_key.strip():
        return []
    per_page = min(max(count, 3), 30)
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "landscape",
        "content_filter": "high",
    }
    headers = {
        "Authorization": f"Client-ID {access_key.strip()}",
        "Accept-Version": "v1",
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=10.0)
    try:
        response = http.get(UNSPLASH_SEARCH_URL, params=params, headers=headers)
        if response.status_code != 200:
            logger.warning("unsplash_search_failed status=%d body=%s", response.status_code, response.text[:200])
            return []
        data = response.json()
        results = data.get("results", [])
        photos: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            urls = item.get("urls") or {}
            regular_url = urls.get("regular") or urls.get("small")
            if not regular_url:
                continue
            alt = (
                item.get("alt_description")
                or item.get("description")
                or f"{query} photo"
            )
            photos.append(
                {
                    "url": regular_url,
                    "alt": str(alt)[:160],
                    "source": "unsplash",
                    "id": str(item.get("id") or uuid4()),
                }
            )
        return photos
    except Exception as exc:
        logger.warning("unsplash_search_error: %s", exc)
        return []
    finally:
        if owns_client:
            http.close()


def search_pixabay(
    query: str,
    api_key: str,
    *,
    count: int = 8,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Search Pixabay for horizontal photos matching query."""
    if not api_key.strip():
        return []
    per_page = min(max(count, 3), 200)
    params = {
        "key": api_key.strip(),
        "q": query,
        "per_page": per_page,
        "orientation": "horizontal",
        "image_type": "photo",
        "safesearch": "true",
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=10.0)
    try:
        response = http.get(PIXABAY_SEARCH_URL, params=params)
        if response.status_code != 200:
            logger.warning("pixabay_search_failed status=%d body=%s", response.status_code, response.text[:200])
            return []
        data = response.json()
        hits = data.get("hits", [])
        photos: list[dict[str, Any]] = []
        for item in hits:
            if not isinstance(item, dict):
                continue
            url = item.get("largeImageURL") or item.get("webformatURL")
            if not url:
                continue
            tags = item.get("tags") or f"{query} photo"
            photos.append(
                {
                    "url": url,
                    "alt": str(tags)[:160],
                    "source": "pixabay",
                    "id": str(item.get("id") or uuid4()),
                }
            )
        return photos
    except Exception as exc:
        logger.warning("pixabay_search_error: %s", exc)
        return []
    finally:
        if owns_client:
            http.close()


def fetch_relevant_mockup_images(
    lead: Lead,
    audit: WebsiteAudit | None = None,
    research: LeadResearch | None = None,
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch 4 curated, role-assigned stock images for mockup generation with Unsplash -> Pixabay fallback."""
    cfg = settings or get_settings()
    has_unsplash = bool(cfg.unsplash_access_key.strip())
    has_pixabay = bool(cfg.pixabay_api_key.strip())

    if not has_unsplash and not has_pixabay:
        logger.info("Neither Unsplash nor Pixabay keys configured; skipping stock image retrieval.")
        return []

    primary_q, secondary_q = derive_search_queries(lead, audit, research)
    logger.info("Mockup stock image search queries: primary='%s', secondary='%s'", primary_q, secondary_q)

    raw_photos: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # Try Unsplash first
    if has_unsplash:
        try:
            results = search_unsplash(primary_q, cfg.unsplash_access_key, count=8, client=client)
            for photo in results:
                url = photo.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    raw_photos.append(photo)

            if len(raw_photos) < 4 and secondary_q and secondary_q != primary_q:
                extra = search_unsplash(secondary_q, cfg.unsplash_access_key, count=4, client=client)
                for photo in extra:
                    url = photo.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        raw_photos.append(photo)
        except Exception as exc:
            logger.warning("unsplash_retrieval_failed: %s", exc)

    # Fallback to Pixabay if fewer than 4 photos
    if len(raw_photos) < 4 and has_pixabay:
        logger.info(
            "Unsplash provided %d photos. Falling back to Pixabay for query '%s'...",
            len(raw_photos),
            primary_q,
        )
        try:
            pix_results = search_pixabay(primary_q, cfg.pixabay_api_key, count=8, client=client)
            for photo in pix_results:
                url = photo.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    raw_photos.append(photo)

            if len(raw_photos) < 4 and secondary_q and secondary_q != primary_q:
                extra_pix = search_pixabay(secondary_q, cfg.pixabay_api_key, count=6, client=client)
                for photo in extra_pix:
                    url = photo.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        raw_photos.append(photo)
        except Exception as exc:
            logger.warning("pixabay_retrieval_failed: %s", exc)

    if not raw_photos:
        logger.warning("No stock images found from Unsplash or Pixabay for '%s'", primary_q)
        return []

    # Assign curated roles to the top 4 images
    assets: list[dict[str, Any]] = []
    for index, (role, filename, default_desc) in enumerate(_ROLES):
        if index >= len(raw_photos):
            break
        photo = raw_photos[index]
        alt_text = photo.get("alt") or default_desc
        assets.append(
            {
                "id": str(uuid4()),
                "filename": filename,
                "role": role,
                "url": photo["url"],
                "alt": alt_text,
                "source": photo.get("source", "stock"),
                "content_type": "image/jpeg",
            }
        )

    logger.info("Successfully curated %d stock images for lead '%s'", len(assets), lead.business_name)
    return assets
