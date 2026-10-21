import logging
import httpx

from app.core.config import Settings
from app.integrations.source_errors import PlaceSourceError
from app.services.discovery_markets import is_anywhere
from app.services.email_finder import extract_clean_emails, find_business_email
from app.services.place_listings import FoundBusiness, category_label

logger = logging.getLogger(__name__)

SCRAPINGBEE_GOOGLE_URL = "https://app.scrapingbee.com/api/v1/store/google"


def fetch_scrapingbee(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], str]:
    api_key = settings.scrapingbee_api_key.strip()
    if not api_key:
        return [], "ScrapingBee was skipped because SCRAPINGBEE_API_KEY is not set."

    label = category_label(category)
    if is_anywhere(city, country):
        search_query = f"{label} contact email"
    else:
        loc = ", ".join(p for p in (city, country) if p and p.strip())
        search_query = f"{label} in {loc} contact email"

    params = {
        "api_key": api_key,
        "search": search_query,
    }

    try:
        response = client.get(SCRAPINGBEE_GOOGLE_URL, params=params, timeout=25.0)
    except httpx.HTTPError as exc:
        logger.warning("scrapingbee_fetch_failed error=%s", exc)
        raise PlaceSourceError("ScrapingBee request failed. Check network or API key.") from None

    if response.status_code != 200:
        logger.warning("scrapingbee_status_error status=%s body=%s", response.status_code, response.text[:200])
        return [], f"ScrapingBee returned status {response.status_code}."

    data = response.json()
    organic_results = data.get("organic_results", [])
    listings: list[FoundBusiness] = []

    for item in organic_results:
        raw_title = (item.get("title") or "").strip()
        if not raw_title:
            continue
        # Clean title e.g. "Dental Clinic - Best Dentists in Lahore" -> "Dental Clinic"
        clean_title = raw_title.split(" - ")[0].split(" | ")[0].split(" — ")[0].strip()
        url = (item.get("url") or "").strip() or None
        description = (item.get("description") or "").strip()
        domain = (item.get("domain") or "").strip()

        # Extract email from snippet first
        snippet_emails = extract_clean_emails(description) if description else []
        email = snippet_emails[0] if snippet_emails else None

        # If no snippet email but url is available, attempt to find email on site
        if not email and url:
            email = find_business_email(url, client=client, settings=settings)

        source_id = domain or clean_title

        listings.append(
            FoundBusiness(
                source_key=f"scrapingbee:{source_id}",
                source="scrapingbee",
                name=clean_title,
                industry=label,
                phone=None,
                email=email,
                website_url=url,
                facebook_url=None,
                instagram_url=None,
                google_maps_url=None,
                city=city,
                country=country,
                website_status="present" if url else "missing",
                lead_score=50,
                description=description[:280] or f"{clean_title} in {city}, {country}.",
                notes="Discovered via ScrapingBee Google Search.",
                tags=["discovered", "scrapingbee"],
            )
        )

    return listings, f"ScrapingBee returned {len(listings)} businesses."
