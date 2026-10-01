import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse

from app.core.errors import AppError
from app.schemas.apify import FieldOption, InputFieldRead, PricingRead
from app.schemas.values import EMAIL_RE

ACTOR_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.~/-]{0,199}$")
SEARCH_RE = re.compile(
    r"search|query|keyword|location|categor|country|city|filter|place|term",
    re.IGNORECASE,
)
LIMIT_RE = re.compile(r"max|limit|results|items|count", re.IGNORECASE)
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}
URL_KEYS = (
    "sourceUrl",
    "source_url",
    "url",
    "link",
    "pageUrl",
    "profileUrl",
    "googleMapsUrl",
    "mapsUrl",
    "website",
    "websiteUrl",
    "webSite",
)
NAME_KEYS = (
    "title",
    "name",
    "businessName",
    "companyName",
    "placeName",
    "fullName",
    "username",
)
STABLE_ID_KEYS = ("placeId", "place_id", "cid", "googleId", "businessId")
MODEL_LABELS = {
    "FREE": "Free",
    "PRICE_PER_DATASET_ITEM": "Pay per result",
    "PAY_PER_EVENT": "Pay per event",
    "FLAT_PRICE_PER_MONTH": "Monthly rental",
}


def connector_identity(actor: dict[str, object]) -> tuple[str, str, str | None]:
    actor_id = actor.get("id") if isinstance(actor.get("id"), str) else ""
    username = actor.get("username") if isinstance(actor.get("username"), str) else ""
    name = actor.get("name") if isinstance(actor.get("name"), str) else ""
    source = f"{username}/{name}" if username and name else actor_id
    title = actor.get("title").strip() if isinstance(actor.get("title"), str) else ""
    description = (
        actor.get("description").strip() if isinstance(actor.get("description"), str) else ""
    )
    display_name = title or source or actor_id or "Actor"
    summary = description[:2000] or None
    return display_name[:120], source[:255], summary


def last_run_started_at(actor: dict[str, object]) -> str | None:
    stats = actor.get("stats")
    if not isinstance(stats, dict):
        return None
    started = stats.get("lastRunStartedAt")
    return started if isinstance(started, str) and started.strip() else None


def normalize_actor_ref(value: str) -> str:
    cleaned = value.strip()
    if ACTOR_REF_RE.fullmatch(cleaned) is None or cleaned.count("/") > 1:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Enter an actor ID or owner/name.",
            status_code=422,
        )
    if "/" in cleaned:
        owner, _, name = cleaned.partition("/")
        if not owner or not name:
            raise AppError(
                code="VALIDATION_ERROR",
                message="Enter an actor ID or owner/name.",
                status_code=422,
            )
        return f"{owner}~{name}"
    return cleaned


def extract_input_schema(build: dict[str, object]) -> dict[str, object]:
    definition = build.get("actorDefinition")
    if isinstance(definition, dict):
        schema = definition.get("input")
        if isinstance(schema, dict):
            return schema
    raw = build.get("inputSchema")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"type": "object", "properties": {}}
        if isinstance(parsed, dict):
            return parsed
    return {"type": "object", "properties": {}}


def select_current_pricing(infos: object) -> dict[str, object] | None:
    if not isinstance(infos, list):
        return None
    records = [
        item
        for item in infos
        if isinstance(item, dict) and isinstance(item.get("pricingModel"), str)
    ]
    if not records:
        return None
    return max(records, key=lambda item: str(item.get("startedAt") or ""))


def summarize_pricing(info: dict[str, object] | None) -> PricingRead:
    # maxTotalChargeUsd caps every current pricing model. maxItems applies to
    # pay-per-result actors only. See the Run Actor query parameters.
    if not info:
        return PricingRead(
            model="UNKNOWN",
            label="Pricing unavailable",
            details=["Pricing information was not published for this actor."],
            supports_max_charge=True,
            supports_max_items=False,
            minimal_max_total_charge_usd=None,
        )
    model = str(info.get("pricingModel") or "UNKNOWN")
    details = _pricing_details(model, info)
    minimal = info.get("minimalMaxTotalChargeUsd")
    minimal_value = _number(minimal)
    return PricingRead(
        model=model,
        label=MODEL_LABELS.get(model, model.replace("_", " ").title()),
        details=details,
        supports_max_charge=True,
        supports_max_items=model == "PRICE_PER_DATASET_ITEM",
        minimal_max_total_charge_usd=minimal_value,
    )


def build_fields(schema: dict[str, object] | None) -> list[InputFieldRead]:
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    required = schema.get("required")
    required_keys = set(required) if isinstance(required, list) else set()
    fields: list[InputFieldRead] = []
    for key, spec in properties.items():
        if not isinstance(key, str) or not isinstance(spec, dict):
            continue
        label = spec.get("title") if isinstance(spec.get("title"), str) else humanize(key)
        description = spec.get("description") if isinstance(spec.get("description"), str) else None
        if description:
            description = description.strip()[:500] or None
        section_caption = spec.get("sectionCaption")
        section = (
            section_caption.strip()[:120]
            if isinstance(section_caption, str) and section_caption.strip()
            else None
        )
        field_type = _field_type(spec)
        options = _options(spec) if field_type == "enum" else None
        minimum = _number(spec.get("minimum")) if field_type in {"integer", "number"} else None
        maximum = _number(spec.get("maximum")) if field_type in {"integer", "number"} else None
        fields.append(
            InputFieldRead(
                key=key,
                label=label[:120],
                description=description,
                field_type=field_type,
                required=key in required_keys,
                default_value=_json_safe(spec.get("default", spec.get("prefill"))),
                options=options,
                minimum=minimum,
                maximum=maximum,
                section=section,
                group=_group(key, label, field_type),
            )
        )
    return fields


def coerce_input(
    schema: dict[str, object] | None,
    raw: dict[str, object] | None,
) -> dict[str, object]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise AppError(
            code="VALIDATION_ERROR",
            message="Actor input must be an object.",
            status_code=422,
        )
    errors: list[str] = []
    cleaned: dict[str, object] = {}
    for field in build_fields(schema):
        if field.field_type == "hidden":
            if field.default_value is not None:
                cleaned[field.key] = field.default_value
            continue
        value = raw[field.key] if field.key in raw else field.default_value
        if _empty(value):
            if field.required:
                errors.append(f"Enter {field.label}.")
            continue
        try:
            cleaned[field.key] = _coerce_value(field, value)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise AppError(
            code="VALIDATION_ERROR",
            message=errors[0],
            status_code=422,
            details={"errors": errors},
        )
    return cleaned


def validate_limits(
    pricing: PricingRead,
    max_items: int | None,
    max_total_charge_usd: float | None,
) -> None:
    if max_items is not None and not pricing.supports_max_items:
        raise AppError(
            code="VALIDATION_ERROR",
            message=(
                "This actor does not charge per result, so a charged result limit is not available."
            ),
            status_code=422,
        )
    if max_total_charge_usd is None:
        return
    if not pricing.supports_max_charge:
        raise AppError(
            code="VALIDATION_ERROR",
            message="This actor does not support a spending cap.",
            status_code=422,
        )
    minimum = pricing.minimal_max_total_charge_usd
    if minimum is not None and max_total_charge_usd < minimum:
        raise AppError(
            code="VALIDATION_ERROR",
            message=f"Enter a spending cap of at least ${minimum:.2f}.",
            status_code=422,
        )


def prepare_item(
    item: dict[str, object],
    *,
    actor_id: str,
    collected_at: datetime,
) -> "PreparedLead":
    source_url = _source_url(item)
    identity = _identity(item, source_url)
    website, maps_url, facebook, instagram, linkedin = _split_urls(item, source_url)
    city = _place_part(item, ("city", "town", "locality", "addressLocality"))
    country = _place_part(item, ("country", "countryCode", "addressCountry"))
    name = _first_str(item, NAME_KEYS) or "Untitled record"
    email = _first_str(item, ("email", "emails"))
    if email and EMAIL_RE.fullmatch(email) is None:
        email = None
    phone = _first_str(item, ("phone", "phoneNumber", "telephone", "phones"))
    if phone:
        phone = phone[:40]
    industry = _first_str(item, ("categoryName", "category", "industry"))
    if industry:
        industry = industry[:120]
    description = _first_str(item, ("description", "about"))
    if description:
        description = description[:2000]
    return PreparedLead(
        source_key=_source_key(actor_id, identity),
        business_name=name[:255],
        source_url=source_url,
        website_url=website,
        google_maps_url=maps_url,
        facebook_url=facebook,
        instagram_url=instagram,
        linkedin_url=linkedin,
        email=email[:320] if email else None,
        phone=phone,
        city=city[:120] if city else None,
        country=country[:120] if country else None,
        industry=industry,
        description=description,
        collected_at=item_collected_at(item, collected_at),
    )


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def item_collected_at(item: dict[str, object], fallback: datetime) -> datetime:
    for key in ("scrapedAt", "collectedAt", "createdAt", "date"):
        parsed = parse_timestamp(item.get(key))
        if parsed is not None:
            return parsed
    return _aware(fallback)


def classify_import(*, provenance_exists: bool, lead_exists: bool) -> str:
    if provenance_exists:
        return "skip"
    if lead_exists:
        return "attach"
    return "create"


def same_business(
    source_key: str,
    website_url: str | None,
    google_maps_url: str | None,
    *,
    existing_source_key: str | None,
    existing_website_url: str | None,
    existing_google_maps_url: str | None,
) -> bool:
    if existing_source_key and existing_source_key == source_key:
        return True
    if website_url and existing_website_url and website_url == existing_website_url:
        return True
    if google_maps_url and existing_google_maps_url and google_maps_url == existing_google_maps_url:
        return True
    return False


def preview_fields(item: dict[str, object]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, value in item.items():
        if key.startswith("#") or key in NAME_KEYS or key in URL_KEYS:
            continue
        if isinstance(value, (dict, list, bool)) or value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        rows.append((humanize(key), text[:160]))
        if len(rows) == 4:
            break
    return rows


def humanize(key: str) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", key).replace("_", " ").strip()
    if not spaced:
        return "Field"
    return spaced[:1].upper() + spaced[1:]


class PreparedLead:
    def __init__(
        self,
        *,
        source_key: str,
        business_name: str,
        source_url: str | None,
        website_url: str | None,
        google_maps_url: str | None,
        facebook_url: str | None,
        instagram_url: str | None,
        linkedin_url: str | None,
        email: str | None,
        phone: str | None,
        city: str | None,
        country: str | None,
        industry: str | None,
        description: str | None,
        collected_at: datetime,
    ) -> None:
        self.source_key = source_key
        self.business_name = business_name
        self.source_url = source_url
        self.website_url = website_url
        self.google_maps_url = google_maps_url
        self.facebook_url = facebook_url
        self.instagram_url = instagram_url
        self.linkedin_url = linkedin_url
        self.email = email
        self.phone = phone
        self.city = city
        self.country = country
        self.industry = industry
        self.description = description
        self.collected_at = collected_at

    @property
    def detail(self) -> str | None:
        parts = [part for part in (self.city, self.phone, self.email) if part]
        return " · ".join(parts) or None


def _pricing_details(model: str, info: dict[str, object]) -> list[str]:
    if model == "FREE":
        return ["No actor charge is published for this pricing record."]
    if model == "PRICE_PER_DATASET_ITEM":
        price = _number(info.get("pricePerUnitUsd"))
        unit = info.get("unitName") if isinstance(info.get("unitName"), str) else "result"
        if price is not None:
            return [f"${price:.4f} per {unit}"]
        return ["Pay per result"]
    if model == "PAY_PER_EVENT":
        return _event_prices(info.get("actorChargeEvents"))
    if model == "FLAT_PRICE_PER_MONTH":
        for key in ("pricePerMonthUsd", "monthlyPriceUsd"):
            price = _number(info.get(key))
            if price is not None:
                return [f"${price:.2f} per month"]
        return ["Flat monthly rental"]
    return ["Pricing information was not published for this actor."]


def _event_prices(events: object) -> list[str]:
    if not isinstance(events, dict):
        return ["Pay per event"]
    details: list[str] = []
    for event in events.values():
        if not isinstance(event, dict):
            continue
        title = event.get("eventTitle") if isinstance(event.get("eventTitle"), str) else "Event"
        price = _number(event.get("eventPriceUsd"))
        if price is None:
            details.append(f"{title}: tiered price")
        else:
            details.append(f"{title}: ${price:.4f} each")
        if len(details) == 6:
            break
    return details or ["Pay per event"]


def _field_type(spec: dict[str, object]) -> str:
    editor = spec.get("editor") if isinstance(spec.get("editor"), str) else ""
    if editor == "hidden":
        return "hidden"
    if editor == "requestListSources":
        return "url_list"
    json_type = _json_type(spec)
    if json_type == "boolean" or editor == "checkbox":
        return "boolean"
    if json_type == "integer":
        return "integer"
    if json_type == "number":
        return "number"
    if json_type == "array":
        items = spec.get("items")
        item_type = _json_type(items) if isinstance(items, dict) else ""
        if editor == "stringList" or item_type == "string":
            return "string_list"
        return "json"
    if json_type == "object" or editor == "json":
        return "json"
    if isinstance(spec.get("enum"), list) and spec.get("enum"):
        return "enum"
    if editor == "textarea":
        return "text"
    return "string"


def _json_type(spec: dict[str, object]) -> str:
    raw = spec.get("type")
    if isinstance(raw, list):
        raw = next((item for item in raw if item != "null"), "string")
    return raw if isinstance(raw, str) else "string"


def _options(spec: dict[str, object]) -> list[FieldOption] | None:
    enum = spec.get("enum")
    if not isinstance(enum, list) or not enum:
        return None
    titles = spec.get("enumTitles")
    options: list[FieldOption] = []
    for index, value in enumerate(enum):
        label = str(value)
        if isinstance(titles, list) and index < len(titles) and isinstance(titles[index], str):
            label = titles[index]
        options.append(FieldOption(value=str(value), label=label))
    return options


def _group(key: str, label: str, field_type: str) -> str:
    if field_type == "hidden":
        return "other"
    blob = f"{key} {label}"
    if field_type in {"integer", "number"} and LIMIT_RE.search(blob):
        return "limit"
    if SEARCH_RE.search(blob):
        return "search"
    return "other"


def _coerce_value(field: InputFieldRead, value: object) -> object:
    if field.field_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{field.label} must be yes or no.")
        return value
    if field.field_type == "integer":
        number = _strict_int(value, field.label)
        _check_bounds(field, number)
        return number
    if field.field_type == "number":
        number = _strict_float(value, field.label)
        _check_bounds(field, number)
        return number
    if field.field_type == "enum":
        text = str(value).strip()
        allowed = {option.value for option in field.options or []}
        if text not in allowed:
            raise ValueError(f"Choose a valid {field.label}.")
        return text
    if field.field_type == "string_list":
        return _string_list(value, field.label)
    if field.field_type == "url_list":
        return [{"url": url} for url in _url_list(value, field.label)]
    if field.field_type == "json":
        return _json_value(value, field.label)
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    if not text:
        raise ValueError(f"Enter {field.label}.")
    if len(text) > 4000:
        raise ValueError(f"{field.label} is too long.")
    return text


def _string_list(value: object, label: str) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip() for part in value.splitlines()]
    elif isinstance(value, list):
        parts = [str(part).strip() for part in value if not isinstance(part, (dict, list))]
    else:
        raise ValueError(f"Enter {label} as a list.")
    cleaned = [part[:500] for part in parts if part]
    if len(cleaned) > 100:
        raise ValueError(f"{label} has too many entries.")
    if not cleaned:
        raise ValueError(f"Enter {label}.")
    return cleaned


def _url_list(value: object, label: str) -> list[str]:
    raw_items: list[object]
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.splitlines()]
    elif isinstance(value, list):
        raw_items = value
    else:
        raise ValueError(f"Enter {label} as a list of URLs.")
    urls: list[str] = []
    for item in raw_items:
        if isinstance(item, dict):
            candidate = item.get("url")
            text = candidate.strip() if isinstance(candidate, str) else ""
        elif isinstance(item, str):
            text = item.strip()
        else:
            text = ""
        if not text:
            continue
        normalized = normalize_http_url(text)
        if normalized is None:
            raise ValueError(f"{label} must use http:// or https:// addresses.")
        urls.append(normalized)
    if not urls:
        raise ValueError(f"Enter {label}.")
    if len(urls) > 100:
        raise ValueError(f"{label} has too many entries.")
    return urls


def _json_value(value: object, label: str) -> object:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} must be valid JSON.") from exc
    if not isinstance(value, (dict, list)):
        raise ValueError(f"{label} must be a JSON object or list.")
    return value


def _strict_int(value: object, label: str) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"Enter a whole number for {label}.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    raise ValueError(f"Enter a whole number for {label}.")


def _strict_float(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Enter a number for {label}.")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise ValueError(f"Enter a number for {label}.") from exc
    raise ValueError(f"Enter a number for {label}.")


def _check_bounds(field: InputFieldRead, number: float) -> None:
    if field.minimum is not None and number < field.minimum:
        raise ValueError(f"{field.label} must be at least {field.minimum:g}.")
    if field.maximum is not None and number > field.maximum:
        raise ValueError(f"{field.label} must be at most {field.maximum:g}.")


def _empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _json_safe(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value[:100]]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in list(value.items())[:50]}
    return None


def _source_key(actor_id: str, identity: str) -> str:
    key = f"apify:{actor_id}:{identity}"
    if len(key) <= 300:
        return key
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return f"apify:{actor_id}:{digest}"[:300]


def _identity(item: dict[str, object], source_url: str | None) -> str:
    if source_url:
        return f"url:{source_url}"
    for key in STABLE_ID_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}:{value.strip()}"[:180]
    name = (_first_str(item, NAME_KEYS) or "").casefold()
    city = (_place_part(item, ("city", "town", "locality")) or "").casefold()
    phone = _first_str(item, ("phone", "phoneNumber", "telephone")) or ""
    if name:
        digest = hashlib.sha256(f"{name}|{city}|{phone}".encode()).hexdigest()[:24]
        return f"biz:{digest}"
    canonical = json.dumps(item, sort_keys=True, default=str)
    return "hash:" + hashlib.sha256(canonical.encode()).hexdigest()[:24]


def _source_url(item: dict[str, object]) -> str | None:
    for key in URL_KEYS:
        value = item.get(key)
        if isinstance(value, str):
            normalized = normalize_http_url(value)
            if normalized and not _looks_like_image(normalized):
                return normalized
    return None


def normalize_http_url(value: str) -> str | None:
    raw = value.strip()
    if "://" not in raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=False)
            if key.lower() not in TRACKING_PARAMS
        ]
    )
    path = parsed.path.rstrip("/")
    base = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    if query:
        return f"{base}?{query}"
    return base


def _split_urls(
    item: dict[str, object],
    source_url: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    website = _classified_url(item, ("website", "websiteUrl", "webSite"), "website")
    maps_url = _classified_url(item, ("googleMapsUrl", "mapsUrl"), "maps")
    facebook = _classified_url(item, ("facebook", "facebookUrl"), "facebook")
    instagram = _classified_url(item, ("instagram", "instagramUrl"), "instagram")
    linkedin = _classified_url(item, ("linkedin", "linkedinUrl"), "linkedin")
    if source_url:
        kind = _url_kind(source_url)
        if kind == "maps" and maps_url is None:
            maps_url = source_url
        elif kind == "facebook" and facebook is None:
            facebook = source_url
        elif kind == "instagram" and instagram is None:
            instagram = source_url
        elif kind == "linkedin" and linkedin is None:
            linkedin = source_url
        elif kind == "website" and website is None:
            website = source_url
    return website, maps_url, facebook, instagram, linkedin


def _classified_url(item: dict[str, object], keys: tuple[str, ...], kind: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if not isinstance(value, str):
            continue
        normalized = normalize_http_url(value)
        if normalized and _url_kind(normalized) == kind:
            return normalized
        if normalized and kind == "website" and _url_kind(normalized) == "website":
            return normalized
    return None


def _url_kind(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "google." in host and "maps" in url:
        return "maps"
    if host.endswith("facebook.com"):
        return "facebook"
    if host.endswith("instagram.com"):
        return "instagram"
    if "linkedin.com" in host:
        return "linkedin"
    return "website"


def _looks_like_image(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"))


def _first_str(item: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, str) and entry.strip():
                    return entry.strip()
    return None


def _place_part(item: dict[str, object], keys: tuple[str, ...]) -> str | None:
    direct = _first_str(item, keys)
    if direct:
        return direct
    for parent in ("address", "location"):
        nested = item.get(parent)
        if isinstance(nested, dict):
            found = _first_str(nested, keys)
            if found:
                return found
    return None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def start_decision(*, existing_request: bool, active_run: bool) -> str:
    if existing_request:
        return "replay"
    if active_run:
        return "blocked"
    return "start"
