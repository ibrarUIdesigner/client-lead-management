import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.schemas.values import EMAIL_RE, normalize_tags, slugify

MAX_LISTINGS = 30
_CATEGORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &'./-]{1,79}$")


@dataclass(frozen=True)
class Category:
    value: str
    label: str
    osm: tuple[tuple[str, str], ...]


CATEGORIES: tuple[Category, ...] = (
    Category("dentist", "Dentist", (("amenity", "dentist"),)),
    Category("clinic", "Doctor or clinic", (("amenity", "clinic"), ("amenity", "doctors"))),
    Category("restaurant", "Restaurant", (("amenity", "restaurant"),)),
    Category("cafe", "Cafe", (("amenity", "cafe"),)),
    Category("bakery", "Bakery", (("shop", "bakery"),)),
    Category("hotel", "Hotel", (("tourism", "hotel"),)),
    Category("gym", "Gym", (("leisure", "fitness_centre"),)),
    Category("salon", "Salon", (("shop", "hairdresser"), ("shop", "beauty"))),
    Category("plumber", "Plumber", (("craft", "plumber"),)),
    Category("electrician", "Electrician", (("craft", "electrician"),)),
    Category("lawyer", "Lawyer", (("office", "lawyer"),)),
    Category("accountant", "Accountant", (("office", "accountant"),)),
    Category("real_estate", "Real estate", (("office", "estate_agent"),)),
    Category("pharmacy", "Pharmacy", (("amenity", "pharmacy"),)),
    Category("car_repair", "Car repair", (("shop", "car_repair"),)),
    Category("photographer", "Photographer", (("craft", "photographer"),)),
    Category("veterinary", "Veterinary", (("amenity", "veterinary"),)),
)

_BY_VALUE = {item.value: item for item in CATEGORIES}


@dataclass(frozen=True)
class BBox:
    south: float
    west: float
    north: float
    east: float
    clamped: bool


@dataclass(frozen=True)
class FoundBusiness:
    source_key: str
    source: str
    name: str
    industry: str
    phone: str | None
    email: str | None
    website_url: str | None
    facebook_url: str | None
    instagram_url: str | None
    google_maps_url: str | None
    city: str
    country: str
    website_status: str
    lead_score: int
    description: str
    notes: str
    tags: list[str]


def category_label(value: str) -> str:
    known = _BY_VALUE.get(value.strip().lower())
    if known:
        return known.label
    return value.strip().title()


def category_is_valid(value: str) -> bool:
    return _CATEGORY_RE.fullmatch(value.strip()) is not None


def clamp_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    max_span: float = 0.45,
) -> BBox:
    lat_span = north - south
    lon_span = east - west
    if lat_span <= max_span and lon_span <= max_span:
        return BBox(south, west, north, east, False)
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2
    half = max_span / 2
    return BBox(
        center_lat - half,
        center_lon - half,
        center_lat + half,
        center_lon + half,
        True,
    )


def overpass_query(category: str, bbox: BBox) -> str:
    box = f"({bbox.south},{bbox.west},{bbox.north},{bbox.east})"
    known = _BY_VALUE.get(category.strip().lower())
    if known:
        clauses = [f'nwr["{key}"="{value}"]{box};' for key, value in known.osm]
    else:
        pattern = re.sub(r"[^a-z0-9 -]", "", category.lower()).strip()[:40]
        pattern = re.escape(pattern).replace(r"\ ", " ")
        clauses = [
            f'nwr["shop"~"{pattern}",i]{box};',
            f'nwr["amenity"~"{pattern}",i]{box};',
            f'nwr["craft"~"{pattern}",i]{box};',
            f'nwr["office"~"{pattern}",i]{box};',
            f'nwr["tourism"~"{pattern}",i]{box};',
        ]
    body = "\n".join(clauses)
    return f"[out:json][timeout:25];\n(\n{body}\n);\nout center tags {MAX_LISTINGS};"


def listings_from_overpass(
    payload: dict[str, object],
    *,
    category: str,
    city: str,
    country: str,
) -> list[FoundBusiness]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        return []
    found: list[FoundBusiness] = []
    seen: set[str] = set()
    for element in elements:
        if not isinstance(element, dict):
            continue
        business = _from_osm_element(element, category=category, city=city, country=country)
        if business is None or business.source_key in seen:
            continue
        seen.add(business.source_key)
        found.append(business)
        if len(found) == MAX_LISTINGS:
            break
    return found


def listings_from_google(
    payload: dict[str, object],
    *,
    category: str,
    city: str,
    country: str,
) -> list[FoundBusiness]:
    places = payload.get("places")
    if not isinstance(places, list):
        return []
    found: list[FoundBusiness] = []
    seen: set[str] = set()
    for place in places:
        if not isinstance(place, dict):
            continue
        if place.get("businessStatus") == "CLOSED_PERMANENTLY":
            continue
        business = _from_google_place(place, category=category, city=city, country=country)
        if business is None or business.source_key in seen:
            continue
        seen.add(business.source_key)
        found.append(business)
        if len(found) == MAX_LISTINGS:
            break
    return found


def _from_osm_element(
    element: dict[str, object],
    *,
    category: str,
    city: str,
    country: str,
) -> FoundBusiness | None:
    tags = element.get("tags")
    if not isinstance(tags, dict):
        return None
    name = _text(tags.get("name"))
    if name is None:
        return None
    element_type = _text(element.get("type")) or "node"
    element_id = element.get("id")
    if not isinstance(element_id, int):
        return None
    lat, lon = _osm_point(element)
    website = _first_text(tags, "website", "contact:website", "url")
    facebook = _first_text(tags, "contact:facebook", "facebook")
    instagram = _first_text(tags, "contact:instagram", "instagram")
    phone = _clip_phone(_first_text(tags, "phone", "contact:phone", "contact:mobile"))
    raw_email = _first_text(tags, "email", "contact:email")
    email = _email(raw_email)
    address = _osm_address(tags, city)
    hours = _text(tags.get("opening_hours"))
    industry = _osm_industry(tags, category)
    maps = _google_maps_link(lat, lon, name, city)
    osm_url = f"https://www.openstreetmap.org/{element_type}/{element_id}"
    extra = [f"OpenStreetMap: {osm_url}"]
    if hours:
        extra.append(f"Hours: {hours}")
    if raw_email and email is None:
        extra.append("An email on the listing was left out because it was not valid.")
    return _assemble(
        source_key=f"osm:{element_type}:{element_id}",
        source="openstreetmap",
        name=name,
        industry=industry,
        phone=phone,
        email=email,
        website=website,
        facebook=facebook,
        instagram=instagram,
        maps=maps,
        city=_text(tags.get("addr:city")) or city,
        country=country,
        address=address,
        category=category,
        extra_lines=extra,
    )


def _from_google_place(
    place: dict[str, object],
    *,
    category: str,
    city: str,
    country: str,
) -> FoundBusiness | None:
    place_id = _text(place.get("id"))
    display = place.get("displayName")
    name = _text(display.get("text")) if isinstance(display, dict) else None
    if place_id is None or name is None:
        return None
    location = place.get("location")
    lat = lon = None
    if isinstance(location, dict):
        lat = _float(location.get("latitude"))
        lon = _float(location.get("longitude"))
    type_name = place.get("primaryTypeDisplayName")
    industry = _text(type_name.get("text")) if isinstance(type_name, dict) else None
    phone = _clip_phone(
        _text(place.get("nationalPhoneNumber")) or _text(place.get("internationalPhoneNumber"))
    )
    return _assemble(
        source_key=f"google:{place_id}"[:300],
        source="google_places",
        name=name,
        industry=industry or category_label(category),
        phone=phone,
        email=None,
        website=_text(place.get("websiteUri")),
        facebook=None,
        instagram=None,
        maps=_text(place.get("googleMapsUri")) or _google_maps_link(lat, lon, name, city),
        city=city,
        country=country,
        address=_text(place.get("formattedAddress")),
        category=category,
        extra_lines=["Listed on: Google Places"],
    )


def build_listing(
    *,
    source_key: str,
    source: str,
    name: str,
    industry: str,
    phone: str | None,
    email: str | None,
    website: str | None,
    facebook: str | None,
    instagram: str | None,
    maps: str | None,
    city: str,
    country: str,
    address: str | None,
    category: str,
    extra_lines: list[str],
    directory_website: bool = False,
) -> FoundBusiness:
    return _assemble(
        source_key=source_key,
        source=source,
        name=name,
        industry=industry,
        phone=_clip_phone(phone),
        email=_email(email),
        website=website,
        facebook=facebook,
        instagram=instagram,
        maps=maps,
        city=city,
        country=country,
        address=address,
        category=category,
        extra_lines=extra_lines,
        directory_website=directory_website,
    )


def _assemble(
    *,
    source_key: str,
    source: str,
    name: str,
    industry: str,
    phone: str | None,
    email: str | None,
    website: str | None,
    facebook: str | None,
    instagram: str | None,
    maps: str | None,
    city: str,
    country: str,
    address: str | None,
    category: str,
    extra_lines: list[str],
    directory_website: bool = False,
) -> FoundBusiness:
    website_url, facebook_url, instagram_url, status = _classify_web(website, facebook, instagram)
    claimed_website = directory_website and status == "missing" and website_url is None
    if claimed_website:
        extra_lines = [
            *extra_lines,
            "The directory shows a website, but it does not publish the URL.",
        ]
    score, pitch = _pitch(status, name, industry, claimed_website=claimed_website)
    notes = _notes(address=address, pitch=pitch, extra_lines=extra_lines)
    tag = slugify(category)[:50] or "discovered"
    return FoundBusiness(
        source_key=source_key[:300],
        source=source,
        name=name[:255],
        industry=industry[:120],
        phone=phone,
        email=email,
        website_url=website_url,
        facebook_url=facebook_url,
        instagram_url=instagram_url,
        google_maps_url=maps if maps and maps.lower().startswith(("http://", "https://")) else None,
        city=city[:120],
        country=country[:120],
        website_status=status,
        lead_score=score,
        description=pitch,
        notes=notes,
        tags=normalize_tags(["discovered", tag]),
    )


def _classify_web(
    website: str | None,
    facebook: str | None,
    instagram: str | None,
) -> tuple[str | None, str | None, str | None, str]:
    website_url = _normalize_url(website)
    facebook_url = _social_url(facebook, "facebook")
    instagram_url = _social_url(instagram, "instagram")
    if website_url and _host_is(website_url, "facebook.com", "fb.com", "fb.me"):
        facebook_url = facebook_url or website_url
        website_url = None
    if website_url and _host_is(website_url, "instagram.com", "instagr.am"):
        instagram_url = instagram_url or website_url
        website_url = None
    if website_url:
        return website_url, facebook_url, instagram_url, "present"
    if facebook_url or instagram_url:
        return None, facebook_url, instagram_url, "social_only"
    return None, facebook_url, instagram_url, "missing"


def _pitch(
    status: str, name: str, industry: str, *, claimed_website: bool = False
) -> tuple[int, str]:
    label = industry.strip() or "business"
    if claimed_website:
        return (
            70,
            f"{name} is listed with a website in the directory, but the URL is not public. "
            f"Add the address before auditing, or pitch a new site if none exists for this "
            f"{label.lower()}.",
        )
    if status == "missing":
        return (
            85,
            f"{name} has no website listed. A short site with services, hours, and a "
            f"contact form is a concrete offer for this {label.lower()}.",
        )
    if status == "social_only":
        return (
            72,
            f"{name} is easy to find on social media, but no website is listed. "
            f"A simple site would give this {label.lower()} a page to send customers.",
        )
    return (
        48,
        f"{name} already has a website. Check it for an outdated design, a weak mobile "
        f"layout, or a missing way to get in touch before pitching a redesign.",
    )


def _notes(*, address: str | None, pitch: str, extra_lines: list[str]) -> str:
    lines = [pitch]
    if address:
        lines.append(f"Address: {address}")
    lines.extend(extra_lines)
    return "\n".join(lines)[:4000]


def _osm_address(tags: dict[str, object], city: str) -> str | None:
    house = _text(tags.get("addr:housenumber"))
    street = _text(tags.get("addr:street"))
    line = " ".join(part for part in (house, street) if part)
    locality = _text(tags.get("addr:city")) or city
    postcode = _text(tags.get("addr:postcode"))
    parts = [part for part in (line, locality, postcode) if part]
    if not line:
        return None
    return ", ".join(parts)


def _osm_industry(tags: dict[str, object], category: str) -> str:
    for key in ("craft", "shop", "amenity", "office", "tourism", "leisure"):
        value = _text(tags.get(key))
        if value and value not in {"yes", "no"}:
            return value.replace("_", " ").title()
    return category_label(category)


def _osm_point(element: dict[str, object]) -> tuple[float | None, float | None]:
    lat = _float(element.get("lat"))
    lon = _float(element.get("lon"))
    if lat is not None and lon is not None:
        return lat, lon
    center = element.get("center")
    if isinstance(center, dict):
        return _float(center.get("lat")), _float(center.get("lon"))
    return None, None


def _google_maps_link(lat: float | None, lon: float | None, name: str, city: str) -> str:
    if lat is not None and lon is not None:
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    query = f"{name}, {city}".replace(" ", "+")
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _normalize_url(value: str | None) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if text.startswith("//"):
        text = f"https:{text}"
    if not text.lower().startswith(("http://", "https://")):
        if " " in text or "." not in text:
            return None
        text = f"https://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text[:2000]


def _social_url(value: str | None, kind: str) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if text.startswith("@"):
        handle = text[1:].strip().strip("/")
        if not handle or " " in handle:
            return None
        host = "instagram.com" if kind == "instagram" else "facebook.com"
        return f"https://{host}/{handle}"
    return _normalize_url(text)


def _host_is(url: str, *hosts: str) -> bool:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == item or host.endswith(f".{item}") for item in hosts)


def _email(value: str | None) -> str | None:
    text = _text(value)
    if text is None or len(text) > 320 or EMAIL_RE.fullmatch(text) is None:
        return None
    return text


def _clip_phone(value: str | None) -> str | None:
    text = _text(value)
    if text is None:
        return None
    compact = re.sub(r"\s+", " ", text)
    return compact[:40]


def _first_text(tags: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        found = _text(tags.get(key))
        if found:
            return found
    return None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
