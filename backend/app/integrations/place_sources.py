import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.integrations.directory_sources import (
    fetch_businesslist,
    fetch_epages,
    fetch_yell,
    fetch_yelp,
)
from app.integrations.source_errors import PlaceSourceError
from app.services.place_listings import (
    BBox,
    FoundBusiness,
    category_label,
    clamp_bbox,
    listings_from_google,
    listings_from_overpass,
    overpass_query,
)

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.primaryTypeDisplayName",
        "places.location",
        "places.businessStatus",
    ]
)


@dataclass(frozen=True)
class SearchArea:
    bbox: BBox
    label: str


def collect_places(
    *,
    category: str,
    city: str,
    country: str,
    use_openstreetmap: bool,
    use_google: bool,
    use_yelp: bool,
    use_yell: bool,
    use_businesslist: bool,
    use_epages: bool,
    settings: Settings,
    client: httpx.Client,
) -> tuple[list[FoundBusiness], list[str]]:
    selected = (
        use_openstreetmap,
        use_google,
        use_yelp,
        use_yell,
        use_businesslist,
        use_epages,
    )
    if not any(selected):
        raise PlaceSourceError("Choose at least one source.")
    notes: list[str] = []
    found: list[FoundBusiness] = []
    errors: list[str] = []
    if use_openstreetmap:
        try:
            area = geocode_city(city, country, settings, client)
            osm_listings = fetch_openstreetmap(
                category=category,
                city=city,
                country=country,
                bbox=area.bbox,
                settings=settings,
                client=client,
            )
        except PlaceSourceError as exc:
            errors.append(exc.message)
        else:
            notes.append(area.label)
            found.extend(osm_listings)
            notes.append(f"OpenStreetMap returned {len(osm_listings)} businesses.")
    if use_google:
        _read_source(
            found,
            notes,
            errors,
            skipped=(
                None
                if settings.google_places_api_key.strip()
                else "Google Places was skipped because GOOGLE_PLACES_API_KEY is not set."
            ),
            load=lambda: fetch_google_places(
                category=category,
                city=city,
                country=country,
                settings=settings,
                client=client,
            ),
            label="Google Places",
        )
    if use_yelp:
        _read_directory(
            found,
            notes,
            errors,
            lambda: fetch_yelp(
                category=category,
                city=city,
                country=country,
                settings=settings,
                client=client,
            ),
        )
    if use_yell:
        _read_directory(
            found,
            notes,
            errors,
            lambda: fetch_yell(
                category=category,
                city=city,
                country=country,
                settings=settings,
                client=client,
            ),
        )
    if use_businesslist:
        _read_directory(
            found,
            notes,
            errors,
            lambda: fetch_businesslist(
                category=category,
                city=city,
                country=country,
                settings=settings,
                client=client,
            ),
        )
    if use_epages:
        _read_directory(
            found,
            notes,
            errors,
            lambda: fetch_epages(
                category=category,
                city=city,
                country=country,
                settings=settings,
                client=client,
            ),
        )
    if not found and errors:
        raise PlaceSourceError(" ".join([*errors, *notes]))
    return found, [*notes, *errors]


def _read_source(
    found: list[FoundBusiness],
    notes: list[str],
    errors: list[str],
    *,
    skipped: str | None,
    load,
    label: str,
) -> None:
    if skipped:
        notes.append(skipped)
        return
    try:
        listings = load()
    except PlaceSourceError as exc:
        errors.append(exc.message)
        return
    found.extend(listings)
    notes.append(f"{label} returned {len(listings)} businesses.")


def _read_directory(
    found: list[FoundBusiness],
    notes: list[str],
    errors: list[str],
    load,
) -> None:
    try:
        listings, note = load()
    except PlaceSourceError as exc:
        errors.append(exc.message)
        return
    found.extend(listings)
    if note:
        notes.append(note)


def geocode_city(city: str, country: str, settings: Settings, client: httpx.Client) -> SearchArea:
    query = ", ".join(part for part in (city.strip(), country.strip()) if part)
    missing = f"No map area matched {query}. Check the city and country."
    try:
        response = client.get(
            NOMINATIM_URL,
            params={"q": query, "format": "jsonv2", "limit": 1},
            headers=_headers(settings),
        )
        response.raise_for_status()
        rows = response.json()
    except httpx.HTTPError as exc:
        logger.warning("nominatim_request_failed")
        raise PlaceSourceError(f"The map search could not find {query}.") from exc
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise PlaceSourceError(missing)
    box = rows[0].get("boundingbox")
    if not isinstance(box, list) or len(box) != 4:
        raise PlaceSourceError(missing)
    try:
        south, north, west, east = (float(item) for item in box)
    except (TypeError, ValueError) as exc:
        raise PlaceSourceError(missing) from exc
    bbox = clamp_bbox(south, west, north, east)
    if bbox.clamped:
        label = "The search stayed near the city center."
    else:
        label = "The search used the city area."
    return SearchArea(bbox=bbox, label=label)


def fetch_openstreetmap(
    *,
    category: str,
    city: str,
    country: str,
    bbox: BBox,
    settings: Settings,
    client: httpx.Client,
) -> list[FoundBusiness]:
    query = overpass_query(category, bbox)
    try:
        response = client.post(
            OVERPASS_URL,
            data={"data": query},
            headers=_headers(settings),
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("overpass_request_failed")
        raise PlaceSourceError(
            "OpenStreetMap is busy or unavailable. The next daily run will try again."
        ) from exc
    if not isinstance(payload, dict):
        raise PlaceSourceError("OpenStreetMap returned an unexpected response.")
    return listings_from_overpass(payload, category=category, city=city, country=country)


def fetch_google_places(
    *,
    category: str,
    city: str,
    country: str,
    settings: Settings,
    client: httpx.Client,
) -> list[FoundBusiness]:
    label = category_label(category)
    text_query = ", ".join(part for part in (label, city, country) if part.strip())
    try:
        response = client.post(
            GOOGLE_PLACES_URL,
            headers={
                **_headers(settings),
                "X-Goog-Api-Key": settings.google_places_api_key.strip(),
                "X-Goog-FieldMask": GOOGLE_FIELD_MASK,
            },
            json={"textQuery": text_query, "pageSize": 20, "languageCode": "en"},
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("google_places_request_failed status=%s", exc.response.status_code)
        raise PlaceSourceError(
            "Google Places rejected the request. Check GOOGLE_PLACES_API_KEY."
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("google_places_request_failed")
        raise PlaceSourceError(
            "Google Places is unavailable. The next daily run will try again."
        ) from exc
    if not isinstance(payload, dict):
        raise PlaceSourceError("Google Places returned an unexpected response.")
    return listings_from_google(payload, category=category, city=city, country=country)


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.discovery_user_agent,
        "Accept": "application/json",
    }
