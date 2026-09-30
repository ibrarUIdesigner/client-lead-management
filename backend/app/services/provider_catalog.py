import hashlib
import time
from decimal import Decimal, InvalidOperation
from typing import Literal

import httpx

from app.core.config import Settings
from app.schemas.providers import ProviderRead, ProvidersRead
from app.services.outreach_ai import resolve_email_provider

_GEMINI_MODELS = "https://generativelanguage.googleapis.com/v1beta/models/{model}"
_GROQ_MODELS = "https://api.groq.com/openai/v1/models"
_TTL_SECONDS = 600
_cache: dict[str, tuple[float, ProvidersRead]] = {}

_GEMINI_CREDITS = (
    "Google does not report remaining credits or quota for an API key. "
    "The live balance is in Google AI Studio."
)
_GROQ_CREDITS = (
    "Groq does not report a credit balance through the API. "
    "Remaining daily requests only appear on a billed response, so this page does not "
    "spend a request to read them. Spend is in the Groq console."
)
_MISSING_KEY = "Add an API key in the server environment, then restart the API."
_UNREACHABLE = "The provider catalog could not be reached just now."


def describe_providers(settings: Settings, client: httpx.Client) -> ProvidersRead:
    cache_key = _cache_key(settings)
    cached = _cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < _TTL_SECONDS:
        return cached[1]
    active = resolve_email_provider(settings)
    snapshot = ProvidersRead(
        providers=[
            _gemini(settings, client, active == "gemini"),
            _groq(settings, client, active == "groq"),
        ]
    )
    _cache[cache_key] = (now, snapshot)
    return snapshot


def clear_provider_cache() -> None:
    _cache.clear()


def _cache_key(settings: Settings) -> str:
    digest = hashlib.sha256(
        f"{settings.gemini_api_key}\n{settings.groq_api_key}".encode()
    ).hexdigest()
    return (
        f"{settings.ai_email_provider}|{settings.gemini_model}|{settings.groq_model}|{digest}"
    )


def _gemini(settings: Settings, client: httpx.Client, active: bool) -> ProviderRead:
    model = settings.gemini_model.strip() or "gemini-3.5-flash"
    if not settings.gemini_api_key.strip():
        return ProviderRead(
            id="gemini",
            configured=False,
            active=False,
            model=model,
            credits=_MISSING_KEY,
        )
    try:
        response = client.get(
            _GEMINI_MODELS.format(model=model),
            headers={"x-goog-api-key": settings.gemini_api_key.strip()},
        )
    except httpx.HTTPError:
        return _unreachable("gemini", model, active)
    if response.status_code == 404:
        return ProviderRead(
            id="gemini",
            configured=True,
            active=active,
            model=model,
            listed=False,
            credits=_GEMINI_CREDITS,
        )
    if response.status_code != 200:
        return _unreachable("gemini", model, active)
    body = response.json()
    return ProviderRead(
        id="gemini",
        configured=True,
        active=active,
        model=model,
        display_name=_text(body.get("displayName")),
        listed=True,
        input_tokens=_whole(body.get("inputTokenLimit")),
        output_tokens=_whole(body.get("outputTokenLimit")),
        credits=_GEMINI_CREDITS,
    )


def _groq(settings: Settings, client: httpx.Client, active: bool) -> ProviderRead:
    model = settings.groq_model.strip() or "llama-3.3-70b-versatile"
    if not settings.groq_api_key.strip():
        return ProviderRead(
            id="groq",
            configured=False,
            active=False,
            model=model,
            credits=_MISSING_KEY,
        )
    try:
        response = client.get(
            _GROQ_MODELS,
            headers={"Authorization": f"Bearer {settings.groq_api_key.strip()}"},
        )
    except httpx.HTTPError:
        return _unreachable("groq", model, active)
    if response.status_code != 200:
        return _unreachable("groq", model, active)
    match = next(
        (item for item in response.json().get("data", []) if item.get("id") == model),
        None,
    )
    if match is None:
        return ProviderRead(
            id="groq",
            configured=True,
            active=active,
            model=model,
            listed=False,
            credits=_GROQ_CREDITS,
        )
    pricing = match.get("pricing") if isinstance(match.get("pricing"), dict) else {}
    return ProviderRead(
        id="groq",
        configured=True,
        active=active,
        model=model,
        display_name=_text(match.get("name")),
        listed=True,
        input_tokens=_whole(match.get("context_window")),
        output_tokens=_whole(match.get("max_completion_tokens")),
        prompt_usd_per_million=_per_million(pricing.get("prompt")),
        completion_usd_per_million=_per_million(pricing.get("completion")),
        credits=_GROQ_CREDITS,
    )


def _unreachable(provider: Literal["gemini", "groq"], model: str, active: bool) -> ProviderRead:
    return ProviderRead(
        id=provider,
        configured=True,
        active=active,
        model=model,
        credits=_UNREACHABLE,
    )


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _whole(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = int(value)
    return number if number > 0 else None


def _per_million(value: object) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        amount = (Decimal(value) * Decimal(1_000_000)).quantize(Decimal("0.0001"))
    except InvalidOperation:
        return None
    return float(amount)
