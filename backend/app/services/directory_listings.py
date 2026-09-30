import html
import json
import re
from urllib.parse import urlparse

from app.schemas.values import slugify
from app.services.place_listings import FoundBusiness, build_listing, category_label

MAX_DIRECTORY_RESULTS = 20
MAX_PROFILE_FETCHES = 8

_TAG_RE = re.compile(r"<[^>]+>")
_YELP_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

BUSINESSLIST_SLUGS = {
    "dentist": "dentists",
    "clinic": "doctors",
    "restaurant": "restaurants",
    "cafe": "cafes",
    "bakery": "bakeries",
    "hotel": "hotels",
    "gym": "gyms",
    "salon": "beauty-salons",
    "plumber": "plumbers",
    "electrician": "electricians",
    "lawyer": "lawyers",
    "accountant": "accountants",
    "real_estate": "real-estate",
    "pharmacy": "pharmacies",
    "car_repair": "auto-repair",
    "photographer": "photographers",
    "veterinary": "veterinarians",
}

EPAGES_SLUGS = {
    "dentist": "doctors-and-clinics",
    "clinic": "doctors-and-clinics",
    "restaurant": "food-drink",
    "cafe": "food-drink",
    "bakery": "food-drink",
    "hotel": "tourism-accommodation",
    "gym": "health-care",
    "salon": "beauty-salons",
    "lawyer": "legal-services",
    "real_estate": "real-estate",
    "veterinary": "doctors-and-clinics",
}

YELL_SLUGS = {
    "dentist": "dentists",
    "clinic": "doctors",
    "restaurant": "restaurants",
    "cafe": "cafes",
    "bakery": "bakers",
    "hotel": "hotels",
    "gym": "gyms",
    "salon": "hairdressers",
    "plumber": "plumbers",
    "electrician": "electricians",
    "lawyer": "solicitors",
    "accountant": "accountants",
    "real_estate": "estate-agents",
    "pharmacy": "pharmacies",
    "car_repair": "garage-services",
    "photographer": "photographers",
    "veterinary": "vets",
}


def is_pakistan(country: str) -> bool:
    value = country.strip().casefold()
    return value in {"pakistan", "pk", "islamic republic of pakistan"}


def is_united_kingdom(country: str) -> bool:
    value = country.strip().casefold()
    return value in {
        "united kingdom",
        "uk",
        "u.k.",
        "great britain",
        "britain",
        "england",
        "scotland",
        "wales",
        "northern ireland",
        "gb",
    }


def businesslist_path(category: str, city: str) -> str:
    slug = BUSINESSLIST_SLUGS.get(category.strip().lower(), slugify(category_label(category)))
    place = slugify(city)
    return f"/category/{slug}/city:{place}"


def epages_city_path(city: str) -> str:
    return f"/listing_location/{slugify(city)}/"


def epages_category_path(category: str) -> str:
    slug = EPAGES_SLUGS.get(category.strip().lower(), slugify(category_label(category)))
    return f"/listing_category/{slug}/"


def yell_search_path(category: str, city: str) -> str:
    what = YELL_SLUGS.get(category.strip().lower(), slugify(category_label(category)))
    where = slugify(city)
    return f"/s/{what}-{where}.html"


def listings_from_businesslist(
    page: str,
    *,
    category: str,
    city: str,
    country: str,
) -> list[FoundBusiness]:
    found: list[FoundBusiness] = []
    seen: set[str] = set()
    for chunk in re.split(r'<div class="company ', page)[1:]:
        business = _businesslist_card(chunk, category=category, city=city, country=country)
        if business is None or business.source_key in seen:
            continue
        seen.add(business.source_key)
        found.append(business)
        if len(found) == MAX_DIRECTORY_RESULTS:
            break
    return found


def listings_from_epages_profile(
    payload: dict[str, object],
    *,
    category: str,
    city: str,
    country: str,
    profile_url: str,
) -> FoundBusiness | None:
    if payload.get("@type") != "LocalBusiness":
        return None
    name = _text(payload.get("name"))
    if name is None:
        return None
    same_as = _string_list(payload.get("sameAs"))
    website, facebook, instagram = _split_links(same_as)
    address = _text(payload.get("address"))
    if isinstance(payload.get("address"), dict):
        address = _join_address(payload["address"])
    hours = _hours_text(payload.get("openingHours"))
    geo = payload.get("geo")
    lat = lon = None
    if isinstance(geo, dict):
        lat = _float(geo.get("latitude"))
        lon = _float(geo.get("longitude"))
    maps = _text(payload.get("hasMap"))
    if maps is None and lat is not None and lon is not None:
        maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    slug = slugify(urlparse(profile_url).path.rstrip("/").split("/")[-1] or name)
    extra = [f"ePages: {profile_url}"]
    if hours:
        extra.append(f"Hours: {hours}")
    return build_listing(
        source_key=f"epages:{slug}"[:300],
        source="epages",
        name=html.unescape(name),
        industry=category_label(category),
        phone=_text(payload.get("telephone")),
        email=_text(payload.get("email")),
        website=website,
        facebook=facebook,
        instagram=instagram,
        maps=maps,
        city=city,
        country=country,
        address=address,
        category=category,
        extra_lines=extra,
    )


def epages_profile_matches(
    payload: dict[str, object],
    *,
    category: str,
    city: str,
    require_category: bool,
) -> bool:
    address = payload.get("address")
    address_text = address if isinstance(address, str) else _join_address(address)
    blob = " ".join(
        part
        for part in (
            address_text,
            _text(payload.get("name")),
            _structured_labels(payload.get("areaServed")),
        )
        if part
    )
    if city.strip().casefold() not in blob.casefold():
        return False
    if not require_category:
        return True
    description = " ".join(
        part
        for part in (
            _text(payload.get("name")),
            _text(payload.get("description")),
            _text(payload.get("additionalType")),
            " ".join(_string_list(payload.get("knowsAbout"))),
        )
        if part
    )
    return category_mentioned(category, description)


def item_list_links(page: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for block in re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        page,
        flags=re.S,
    ):
        try:
            payload = json.loads(html.unescape(block))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("@type") != "ItemList":
            continue
        elements = payload.get("itemListElement")
        if not isinstance(elements, list):
            continue
        for element in elements:
            if not isinstance(element, dict):
                continue
            url = _text(element.get("url"))
            name = _text(element.get("name")) or ""
            if url is None or "/business/" not in url or url in seen:
                continue
            seen.add(url)
            links.append((html.unescape(name), url))
    return links


def listings_from_yell(
    page: str,
    *,
    category: str,
    city: str,
    country: str,
) -> list[FoundBusiness]:
    structured = _yell_from_jsonld(page, category=category, city=city, country=country)
    if structured:
        return structured[:MAX_DIRECTORY_RESULTS]
    found: list[FoundBusiness] = []
    seen: set[str] = set()
    for chunk in re.split(r'class="[^"]*businessCapsule(?!--)', page)[1:]:
        business = _yell_capsule(chunk, category=category, city=city, country=country)
        if business is None or business.source_key in seen:
            continue
        seen.add(business.source_key)
        found.append(business)
        if len(found) == MAX_DIRECTORY_RESULTS:
            break
    return found


def listings_from_yelp(
    payload: dict[str, object],
    details_by_id: dict[str, dict[str, object]],
    *,
    category: str,
    city: str,
    country: str,
) -> list[FoundBusiness]:
    businesses = payload.get("businesses")
    if not isinstance(businesses, list):
        return []
    found: list[FoundBusiness] = []
    seen: set[str] = set()
    for place in businesses:
        if not isinstance(place, dict) or place.get("is_closed") is True:
            continue
        business_id = _text(place.get("id"))
        name = _text(place.get("name"))
        if business_id is None or name is None:
            continue
        details = details_by_id.get(business_id, {})
        location = place.get("location")
        address = None
        if isinstance(location, dict):
            display = location.get("display_address")
            if isinstance(display, list):
                address = ", ".join(str(part) for part in display if str(part).strip())
        coordinates = place.get("coordinates")
        lat = lon = None
        if isinstance(coordinates, dict):
            lat = _float(coordinates.get("latitude"))
            lon = _float(coordinates.get("longitude"))
        maps = None
        if lat is not None and lon is not None:
            maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        categories = place.get("categories")
        industry = category_label(category)
        if isinstance(categories, list) and categories and isinstance(categories[0], dict):
            industry = _text(categories[0].get("title")) or industry
        rating = place.get("rating")
        reviews = place.get("review_count")
        extra = ["Listed on: Yelp"]
        yelp_url = _text(place.get("url"))
        if yelp_url:
            extra.append(f"Yelp: {yelp_url}")
        if isinstance(rating, (int, float)) and isinstance(reviews, int):
            extra.append(f"Yelp rating {rating} from {reviews} reviews")
        hours = _yelp_hours(details.get("hours"))
        if hours:
            extra.append(f"Hours: {hours}")
        business = build_listing(
            source_key=f"yelp:{business_id}"[:300],
            source="yelp",
            name=name,
            industry=industry,
            phone=_text(place.get("display_phone")) or _text(place.get("phone")),
            email=None,
            website=None,
            facebook=None,
            instagram=None,
            maps=maps,
            city=city,
            country=country,
            address=address,
            category=category,
            extra_lines=extra,
        )
        if business.source_key in seen:
            continue
        seen.add(business.source_key)
        found.append(business)
        if len(found) == MAX_DIRECTORY_RESULTS:
            break
    return found


def jsonld_blocks(page: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for block in re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        page,
        flags=re.S,
    ):
        try:
            payload = json.loads(html.unescape(block))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            found.append(payload)
    return found


def local_business(payload: dict[str, object]) -> dict[str, object] | None:
    if payload.get("@type") == "LocalBusiness":
        return payload
    graph = payload.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            if isinstance(item, dict) and item.get("@type") == "LocalBusiness":
                return item
    return None


def _businesslist_card(
    chunk: str,
    *,
    category: str,
    city: str,
    country: str,
) -> FoundBusiness | None:
    company_id = _match(r'data-cmpid="(\d+)"', chunk)
    name = _plain(r"<h3>.*?<a [^>]*>(.*?)</a>", chunk)
    if company_id is None or name is None:
        return None
    address = _plain(r'<div class="address">(.*?)</div>', chunk)
    phone = _plain(r'aria-label="Phone number".*?<b>(.*?)</b>', chunk)
    lat = _match(r'data-ltd="([\d.-]+)"', chunk)
    lon = _match(r'data-lng="([\d.-]+)"', chunk)
    maps = None
    if lat and lon:
        maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    profile = _match(r'href="(/company/\d+/[^"]+)"', chunk)
    extra = ["Listed on: BusinessList.pk"]
    if profile:
        extra.append(f"BusinessList: https://www.businesslist.pk{profile}")
    return build_listing(
        source_key=f"businesslist:{company_id}",
        source="businesslist",
        name=name,
        industry=category_label(category),
        phone=phone,
        email=None,
        website=None,
        facebook=None,
        instagram=None,
        maps=maps,
        city=city,
        country=country,
        address=address,
        category=category,
        extra_lines=extra,
        directory_website='aria-label="Website"' in chunk,
    )


def _yell_from_jsonld(
    page: str,
    *,
    category: str,
    city: str,
    country: str,
) -> list[FoundBusiness]:
    found: list[FoundBusiness] = []
    for payload in jsonld_blocks(page):
        elements: list[object] = []
        if payload.get("@type") == "ItemList" and isinstance(payload.get("itemListElement"), list):
            elements = payload["itemListElement"]
        elif payload.get("@type") == "LocalBusiness":
            elements = [payload]
        for element in elements:
            if not isinstance(element, dict):
                continue
            item = element.get("item") if isinstance(element.get("item"), dict) else element
            if not isinstance(item, dict):
                continue
            business = _yell_structured(item, category=category, city=city, country=country)
            if business is not None:
                found.append(business)
    return found


def _yell_structured(
    item: dict[str, object],
    *,
    category: str,
    city: str,
    country: str,
) -> FoundBusiness | None:
    name = _text(item.get("name"))
    if name is None:
        return None
    url = _text(item.get("url")) or ""
    source_key = _yell_key(url, name, city)
    address = item.get("address")
    address_text = address if isinstance(address, str) else _join_address(address)
    return build_listing(
        source_key=source_key,
        source="yell",
        name=name,
        industry=category_label(category),
        phone=_text(item.get("telephone")),
        email=_text(item.get("email")),
        website=_text(item.get("url")) if "yell.com" not in (url or "") else None,
        facebook=None,
        instagram=None,
        maps=None,
        city=city,
        country=country,
        address=address_text,
        category=category,
        extra_lines=[f"Yell: {url}"] if "yell.com" in url else ["Listed on: Yell"],
    )


def _yell_capsule(
    chunk: str,
    *,
    category: str,
    city: str,
    country: str,
) -> FoundBusiness | None:
    name = _plain(r"businessCapsule--title[^>]*>(.*?)</a>", chunk)
    if name is None:
        name = _plain(r"businessCapsule--name[^>]*>.*?<a [^>]*>(.*?)</a>", chunk)
    if name is None:
        return None
    href = _match(r'href="([^"]*/biz/[^"]+)"', chunk) or ""
    phone = _plain(r"businessCapsule--telephone[^>]*>(.*?)</", chunk)
    address = _plain(r"businessCapsule--address[^>]*>(.*?)</span>", chunk)
    website = _match(r'businessCapsule--website[^>]*href="(https?://[^"]+)"', chunk)
    if website and "yell.com" in website:
        website = None
    extra = ["Listed on: Yell"]
    if href.startswith("http"):
        extra.append(f"Yell: {href}")
    elif href:
        extra.append(f"Yell: https://www.yell.com{href}")
    return build_listing(
        source_key=_yell_key(href, name, city),
        source="yell",
        name=name,
        industry=category_label(category),
        phone=phone,
        email=None,
        website=website,
        facebook=None,
        instagram=None,
        maps=None,
        city=city,
        country=country,
        address=address,
        category=category,
        extra_lines=extra,
    )


def _yell_key(url: str, name: str, city: str) -> str:
    match = re.search(r"/biz/([^/?#]+)", url)
    if match:
        return f"yell:{match.group(1)}"[:300]
    return f"yell:{slugify(name)}-{slugify(city)}"[:300]


def _yelp_hours(value: object) -> str | None:
    if not isinstance(value, list) or not value or not isinstance(value[0], dict):
        return None
    slots = value[0].get("open")
    if not isinstance(slots, list):
        return None
    parts: list[str] = []
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        day = slot.get("day")
        start = _text(slot.get("start"))
        end = _text(slot.get("end"))
        if not isinstance(day, int) or not 0 <= day <= 6 or start is None or end is None:
            continue
        if len(start) != 4 or len(end) != 4:
            continue
        parts.append(f"{_YELP_DAYS[day]} {start[:2]}:{start[2:]}-{end[:2]}:{end[2:]}")
        if len(parts) == 7:
            break
    return ", ".join(parts) or None


def _structured_labels(value: object) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
        else:
            return stripped
    labels: list[str] = []
    items = value if isinstance(value, list) else [value]
    for item in items:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            for key in ("name", "@id"):
                text = _text(item.get(key))
                if text:
                    labels.append(text)
    return " ".join(labels)


def category_mentioned(category: str, text: str) -> bool:
    label = category_label(category).casefold()
    haystack = text.casefold()
    tokens = [token for token in re.split(r"[^a-z0-9]+", label) if len(token) > 2]
    if not tokens:
        return True
    return any(token in haystack for token in tokens)


def _split_links(links: list[str]) -> tuple[str | None, str | None, str | None]:
    website = facebook = instagram = None
    for link in links:
        host = urlparse(link).netloc.casefold().removeprefix("www.")
        if host.endswith("facebook.com") or host.endswith("fb.com"):
            facebook = facebook or link
        elif host.endswith("instagram.com"):
            instagram = instagram or link
        elif website is None and host and "epages.pk" not in host:
            website = link
    return website, facebook, instagram


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return [stripped]
            value = parsed
        else:
            return [stripped] if stripped else []
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _hours_text(value: object) -> str | None:
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, list):
        parts = [_text(item) for item in value]
        joined = "; ".join(part for part in parts if part)
        return joined[:300] or None
    return None


def _join_address(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    parts = [
        _text(value.get(key))
        for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode")
    ]
    joined = ", ".join(part for part in parts if part)
    return joined or None


def _plain(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.S)
    if match is None:
        return None
    cleaned = _TAG_RE.sub(" ", match.group(1))
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" |")
    return cleaned or None


def _match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.S)
    if match is None:
        return None
    return match.group(1).strip() or None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = html.unescape(value).strip()
    return stripped or None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except ValueError:
        return None
