import logging
import httpx

from app.core.config import Settings
from app.integrations.source_errors import PlaceSourceError
from app.services.discovery_markets import is_anywhere
from app.services.email_finder import find_business_email
from app.services.place_listings import FoundBusiness, category_label

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"


def fetch_serpapi(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], str]:
    api_key = settings.serpapi_api_key.strip()
    if not api_key:
        return [], "SerpApi was skipped because SERPAPI_API_KEY is not set."

    label = category_label(category)
    if is_anywhere(city, country):
        query = label
    else:
        loc = ", ".join(p for p in (city, country) if p and p.strip())
        query = f"{label} in {loc}"

    params = {
        "engine": "google_maps",
        "q": query,
        "api_key": api_key,
        "hl": "en",
    }

    try:
        response = client.get(SERPAPI_URL, params=params, timeout=25.0)
    except httpx.HTTPError as exc:
        logger.warning("serpapi_fetch_failed error=%s", exc)
        raise PlaceSourceError("SerpApi request failed. Check network or API key.") from None

    if response.status_code != 200:
        logger.warning("serpapi_status_error status=%s body=%s", response.status_code, response.text[:200])
        return [], f"SerpApi returned status {response.status_code}."

    data = response.json()
    results = data.get("local_results", [])
    listings: list[FoundBusiness] = []

    for item in results:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        website = (item.get("website") or "").strip() or None
        phone = (item.get("phone") or "").strip() or None
        address = (item.get("address") or "").strip()
        rating = item.get("rating")
        reviews = item.get("reviews")
        place_id = str(item.get("place_id") or item.get("cid") or item.get("data_id") or title)

        desc_parts = [item.get("type") or label]
        if rating:
            desc_parts.append(f"Rated {rating} ({reviews or 0} reviews)")
        if address:
            desc_parts.append(f"Located at {address}")
        description = " · ".join(desc_parts)

        email = find_business_email(website, client=client, settings=settings) if website else None

        listings.append(
            FoundBusiness(
                source_key=f"serpapi:{place_id}",
                source="serpapi",
                name=title,
                industry=label,
                phone=phone,
                email=email,
                website_url=website,
                facebook_url=None,
                instagram_url=None,
                google_maps_url=item.get("links", {}).get("directions") if isinstance(item.get("links"), dict) else None,
                city=city,
                country=country,
                website_status="present" if website else "missing",
                lead_score=50,
                description=description[:280],
                notes="Discovered via SerpApi Google Maps search.",
                tags=["discovered", "serpapi"],
            )
        )

    return listings, f"SerpApi returned {len(listings)} businesses."
