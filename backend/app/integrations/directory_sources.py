import logging
import time

import httpx

from app.core.config import Settings
from app.integrations.source_errors import PlaceSourceError
from app.services.directory_listings import (
    MAX_PROFILE_FETCHES,
    FoundBusiness,
    businesslist_path,
    category_mentioned,
    epages_category_path,
    epages_city_path,
    epages_profile_matches,
    is_pakistan,
    is_united_kingdom,
    item_list_links,
    jsonld_blocks,
    listings_from_businesslist,
    listings_from_epages_profile,
    listings_from_yell,
    listings_from_yelp,
    local_business,
    yell_search_path,
)
from app.services.place_listings import category_label

logger = logging.getLogger(__name__)

YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
YELP_BUSINESS_URL = "https://api.yelp.com/v3/businesses/{business_id}"
BUSINESSLIST_ORIGIN = "https://www.businesslist.pk"
EPAGES_ORIGIN = "https://epages.pk"
YELL_ORIGIN = "https://www.yell.com"


def fetch_businesslist(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], str]:
    if not is_pakistan(country):
        return [], "BusinessList.pk was skipped because it covers businesses in Pakistan."
    url = f"{BUSINESSLIST_ORIGIN}{businesslist_path(category, city)}"
    page = _public_page(client, url, settings, "BusinessList.pk")
    listings = listings_from_businesslist(page, category=category, city=city, country=country)
    return listings, f"BusinessList.pk returned {len(listings)} businesses."


def fetch_epages(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], str]:
    if not is_pakistan(country):
        return [], "ePages.pk was skipped because it covers businesses in Pakistan."
    candidates = _epages_candidates(category, city, settings, client)
    listings: list[FoundBusiness] = []
    seen: set[str] = set()
    for index, (_name, url, require_category) in enumerate(candidates[:MAX_PROFILE_FETCHES]):
        if index:
            time.sleep(0.6)
        try:
            page = _public_page(client, url, settings, "ePages.pk")
        except PlaceSourceError:
            logger.warning("epages_profile_unavailable")
            continue
        payload = _epages_business(page)
        if payload is None or not epages_profile_matches(
            payload,
            category=category,
            city=city,
            require_category=require_category,
        ):
            continue
        business = listings_from_epages_profile(
            payload,
            category=category,
            city=city,
            country=country,
            profile_url=url,
        )
        if business is None or business.source_key in seen:
            continue
        seen.add(business.source_key)
        listings.append(business)
    return listings, f"ePages.pk returned {len(listings)} businesses."


def fetch_yell(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], str]:
    if not is_united_kingdom(country):
        return [], "Yell was skipped because it covers businesses in the United Kingdom."
    url = f"{YELL_ORIGIN}{yell_search_path(category, city)}"
    try:
        response = client.get(url, headers=_headers(settings))
    except httpx.HTTPError as exc:
        logger.warning("yell_request_failed")
        raise PlaceSourceError("Yell is unavailable. The next daily run will try again.") from exc
    if response.status_code in {401, 403, 429, 503}:
        raise PlaceSourceError(
            "Yell declined the automated request. Its public search page could not be read."
        )
    if response.status_code == 404:
        return [], "Yell has no public results page for that search."
    try:
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("yell_request_failed status=%s", response.status_code)
        raise PlaceSourceError("Yell is unavailable. The next daily run will try again.") from exc
    listings = listings_from_yell(response.text, category=category, city=city, country=country)
    return listings, f"Yell returned {len(listings)} businesses."


def fetch_yelp(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], str]:
    api_key = settings.yelp_api_key.strip()
    if not api_key:
        return [], "Yelp was skipped because YELP_API_KEY is not set."
    location = ", ".join(part for part in (city.strip(), country.strip()) if part)
    headers = {
        **_headers(settings),
        "Authorization": f"Bearer {api_key}",
    }
    try:
        response = client.get(
            YELP_SEARCH_URL,
            params={"term": category_label(category), "location": location, "limit": 20},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("yelp_request_failed status=%s", exc.response.status_code)
        raise PlaceSourceError("Yelp rejected the request. Check YELP_API_KEY.") from exc
    except httpx.HTTPError as exc:
        logger.warning("yelp_request_failed")
        raise PlaceSourceError("Yelp is unavailable. The next daily run will try again.") from exc
    if not isinstance(payload, dict):
        raise PlaceSourceError("Yelp returned an unexpected response.")
    details = _yelp_details(payload, headers, client)
    listings = listings_from_yelp(
        payload,
        details,
        category=category,
        city=city,
        country=country,
    )
    return listings, f"Yelp returned {len(listings)} businesses."


def _epages_candidates(
    category: str,
    city: str,
    settings: Settings,
    client: httpx.Client,
) -> list[tuple[str, str, bool]]:
    chosen: list[tuple[str, str, bool]] = []
    seen: set[str] = set()
    # The category page is already the directory's industry. The city page mixes
    # industries, so only names that mention the search are worth opening.
    pages = (
        (f"{EPAGES_ORIGIN}{epages_category_path(category)}", False),
        (f"{EPAGES_ORIGIN}{epages_city_path(city)}", True),
    )
    for url, filter_by_name in pages:
        try:
            page = _public_page(client, url, settings, "ePages.pk")
        except PlaceSourceError:
            continue
        for name, profile_url in item_list_links(page):
            if profile_url in seen:
                continue
            if filter_by_name and not _name_matches(category, name):
                continue
            seen.add(profile_url)
            chosen.append((name, profile_url, False))
    return chosen


def _epages_business(page: str) -> dict[str, object] | None:
    for payload in jsonld_blocks(page):
        business = local_business(payload)
        if business is not None:
            return business
    return None


def _yelp_details(
    payload: dict[str, object],
    headers: dict[str, str],
    client: httpx.Client,
) -> dict[str, dict[str, object]]:
    businesses = payload.get("businesses")
    if not isinstance(businesses, list):
        return {}
    details: dict[str, dict[str, object]] = {}
    identifiers = [
        business.get("id")
        for business in businesses
        if isinstance(business, dict) and isinstance(business.get("id"), str)
    ]
    for index, business_id in enumerate(identifiers[:8]):
        if index:
            time.sleep(0.3)
        try:
            response = client.get(
                YELP_BUSINESS_URL.format(business_id=business_id),
                headers=headers,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("yelp_details_unavailable")
            continue
        if isinstance(body, dict):
            details[business_id] = body
    return details


def _public_page(client: httpx.Client, url: str, settings: Settings, source: str) -> str:
    try:
        response = client.get(url, headers=_headers(settings))
    except httpx.HTTPError as exc:
        logger.warning("directory_request_failed source=%s", source)
        raise PlaceSourceError(
            f"{source} is unavailable. The next daily run will try again."
        ) from exc
    if response.status_code == 404:
        raise PlaceSourceError(f"{source} has no public page for that search.")
    if response.status_code in {401, 403, 429}:
        raise PlaceSourceError(f"{source} declined the automated request.")
    try:
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("directory_request_failed source=%s status=%s", source, response.status_code)
        raise PlaceSourceError(
            f"{source} is unavailable. The next daily run will try again."
        ) from exc
    return response.text


def _name_matches(category: str, name: str) -> bool:
    return category_mentioned(category, name)


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.discovery_user_agent,
        "Accept": "text/html,application/json",
    }
