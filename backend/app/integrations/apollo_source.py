import logging
import httpx

from app.core.config import Settings
from app.integrations.source_errors import PlaceSourceError
from app.services.discovery_markets import is_anywhere
from app.services.email_finder import find_business_email
from app.services.place_listings import FoundBusiness, category_label

logger = logging.getLogger(__name__)

APOLLO_SEARCH_URL = "https://api.apollo.io/api/v1/organizations/search"


def fetch_apollo(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], str]:
    api_key = settings.apollo_api_key.strip()
    if not api_key:
        return [], "Apollo.io was skipped because APOLLO_API_KEY is not set."

    label = category_label(category)
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }

    locations: list[str] = []
    if not is_anywhere(city, country):
        loc_parts = [p for p in (city, country) if p and p.strip()]
        if loc_parts:
            locations.append(", ".join(loc_parts))

    payload: dict[str, object] = {
        "q_organization_name": label,
        "page": 1,
        "per_page": 25,
    }
    if locations:
        payload["organization_locations"] = locations

    try:
        response = client.post(APOLLO_SEARCH_URL, headers=headers, json=payload, timeout=20.0)
    except httpx.HTTPError as exc:
        logger.warning("apollo_fetch_failed error=%s", exc)
        raise PlaceSourceError("Apollo.io request failed. Check network or API key.") from None

    if response.status_code != 200:
        logger.warning("apollo_status_error status=%s body=%s", response.status_code, response.text[:200])
        return [], f"Apollo.io returned status {response.status_code}."

    data = response.json()
    organizations = data.get("organizations", [])
    listings: list[FoundBusiness] = []

    for org in organizations:
        name = (org.get("name") or "").strip()
        if not name:
            continue
        website = (org.get("website_url") or "").strip() or None
        phone = (org.get("phone") or org.get("primary_phone") or "").strip() or None
        org_city = (org.get("city") or "").strip() or city
        org_country = (org.get("country") or "").strip() or country
        industry = (org.get("industry") or label).strip()
        description = (
            org.get("short_description")
            or f"{name} is a {industry} company based in {org_city}, {org_country}."
        ).strip()
        org_id = str(org.get("id") or name)

        email = find_business_email(website, client=client, settings=settings) if website else None

        listings.append(
            FoundBusiness(
                source_key=f"apollo:{org_id}",
                source="apollo",
                name=name,
                industry=industry,
                phone=phone,
                email=email,
                website_url=website,
                facebook_url=org.get("facebook_url"),
                instagram_url=None,
                google_maps_url=None,
                city=org_city,
                country=org_country,
                website_status="present" if website else "missing",
                lead_score=50,
                description=description[:280],
                notes=f"Discovered via Apollo.io organization search.",
                tags=["discovered", "apollo"],
            )
        )

    return listings, f"Apollo.io returned {len(listings)} businesses."
