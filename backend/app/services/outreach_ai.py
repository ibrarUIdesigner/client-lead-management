import json
import logging
import re
import time
from dataclasses import dataclass
from typing import NoReturn

import httpx

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

DEFAULT_OFFER = (
    "I design clearer websites for local businesses, starting with a homepage "
    "that makes the next step obvious."
)
NEW_SITE_OFFER = (
    "I can create a professional website for the business, with a clear homepage "
    "and a simple way for customers to get in touch. "
    "The settled price for that first site is $1,400."
)
_SCORE_LABELS = {
    "performance": "Performance",
    "design": "Design",
    "seo": "SEO",
    "mobile": "Mobile",
    "ux": "Usability",
    "overall": "Overall",
}
_SCORE_ORDER = ("performance", "design", "seo", "mobile", "ux", "overall")
_TONES = {
    "professional": "Calm, specific, and respectful.",
    "warm": "Friendly and plain, still professional. No jokes and no emoji.",
    "direct": "Short and plain. Say what you noticed and what you can do.",
    "brief": "Keep the body under 80 words.",
}
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,40}(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,40})?$")
_GEMINI_FALLBACK_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
)
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(frozen=True)
class EmailBrief:
    business: str
    industry: str | None
    services: str | None
    location: str | None
    has_website: bool
    website: str | None
    greeting_name: str | None
    findings: tuple[tuple[str, str], ...]
    scores: tuple[tuple[str, int], ...]
    offer: str
    tone: str
    sender_name: str | None
    purpose: str


def provider_ready(settings: Settings, name: str) -> bool:
    if name == "gemini":
        return bool(settings.gemini_api_key.strip()) and _valid_model(settings.gemini_model)
    if name == "groq":
        return bool(settings.groq_api_key.strip()) and _valid_model(settings.groq_model)
    return False


def resolve_email_provider(settings: Settings) -> str | None:
    requested = settings.ai_email_provider.strip().lower()
    gemini = bool(settings.gemini_api_key.strip()) and _valid_model(settings.gemini_model)
    groq = bool(settings.groq_api_key.strip()) and _valid_model(settings.groq_model)
    if requested == "gemini":
        return "gemini" if gemini else None
    if requested == "groq":
        return "groq" if groq else None
    if requested not in {"", "auto"}:
        return None
    if gemini:
        return "gemini"
    if groq:
        return "groq"
    return None


def build_brief(
    *,
    business: str,
    industry: str | None,
    description: str | None,
    city: str | None,
    country: str | None,
    website: str | None,
    greeting_name: str | None,
    findings: list[tuple[str, str]],
    scores: dict[str, int],
    offer: str | None,
    tone: str,
    sender_name: str | None,
) -> EmailBrief:
    location = ", ".join(part for part in (city, country) if part and part.strip())
    cleaned_offer = " ".join((offer or "").split())
    cleaned_sender = " ".join((sender_name or "").split())
    has_website = bool(website and website.strip())
    if not has_website:
        findings = []
        scores = {}
    if not cleaned_offer or (not has_website and cleaned_offer == DEFAULT_OFFER):
        cleaned_offer = NEW_SITE_OFFER if not has_website else DEFAULT_OFFER
    return EmailBrief(
        business=business.strip(),
        industry=_clip(industry, 120),
        services=_clip(description, 400),
        location=location or None,
        has_website=has_website,
        website=_clip(website, 300) if has_website else None,
        greeting_name=_clip(greeting_name, 80),
        findings=tuple((title, detail) for title, detail in findings[:6]),
        scores=tuple(
            (key, scores[key]) for key in _SCORE_ORDER if isinstance(scores.get(key), int)
        ),
        offer=cleaned_offer,
        tone=tone if tone in _TONES else "professional",
        sender_name=cleaned_sender or None,
        purpose="review" if has_website else "new_site",
    )


def render_brief(brief: EmailBrief) -> str:
    lines = [
        f"Business name: {brief.business}",
        f"Has a public website: {'yes' if brief.has_website else 'no'}",
    ]
    if brief.website:
        lines.append(f"Website: {brief.website}")
    if brief.industry:
        lines.append(f"Industry: {brief.industry}")
    if brief.services:
        lines.append(f"What the business does: {brief.services}")
    if brief.location:
        lines.append(f"Location: {brief.location}")
    if brief.greeting_name:
        lines.append(f"Greeting name: {brief.greeting_name}")
    else:
        lines.append("Greeting name: unknown. Open with Hi, and do not invent a name.")
    if brief.purpose == "new_site":
        lines.append(
            "Email purpose: this business has no website. Offer to create a professional one."
        )
        lines.append("Do not mention scores, page problems, or a review of a website.")
    elif brief.findings or brief.scores:
        lines.append("Email purpose: describe the weak points of the current website.")
        if brief.findings:
            lines.append("Verified findings. Use the most useful two or three:")
            lines.extend(f"- {title}: {detail}" for title, detail in brief.findings)
        if brief.scores:
            listed = ", ".join(
                f"{_SCORE_LABELS.get(name, name)} {score}/100"
                for name, score in brief.scores
            )
            lines.append(f"Scores: {listed}")
    else:
        lines.append("Verified findings: none. Do not claim you found specific problems.")
    lines.append(f"Offer: {brief.offer}")
    lines.append(f"Tone: {brief.tone}. {_TONES[brief.tone]}")
    if brief.sender_name:
        lines.append(f"Sign the email as: {brief.sender_name}")
    else:
        lines.append("Sign off with Best regards, and do not invent a sender name.")
    return "\n".join(lines)


def draft_email(
    brief: EmailBrief,
    settings: Settings,
    client: httpx.Client | None = None,
) -> tuple[str, str]:
    provider = resolve_email_provider(settings)
    if provider is None:
        raise AppError(
            code="AI_NOT_CONFIGURED",
            message=(
                "Add GEMINI_API_KEY or GROQ_API_KEY in the server environment, "
                "then generate the draft again."
            ),
            status_code=503,
        )
    prompt = _instructions(render_brief(brief), brief.purpose)
    owns_client = client is None
    http = client or httpx.Client(timeout=45.0)
    try:
        try:
            if provider == "gemini":
                raw = _gemini(http, settings, prompt)
            else:
                raw = _groq(http, settings, prompt)
        except AppError as exc:
            if not _should_try_groq(settings, provider, exc):
                raise
            logger.warning("email_draft_fallback provider=groq")
            raw = _groq(http, settings, prompt)
    except httpx.TimeoutException as exc:
        logger.warning("email_draft_timeout provider=%s", provider)
        raise AppError(
            code="AI_DRAFT_FAILED",
            message="The email draft took too long. Try again in a moment.",
            status_code=504,
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("email_draft_failed provider=%s", provider)
        raise AppError(
            code="AI_DRAFT_FAILED",
            message="The email draft could not be written. Try again in a moment.",
            status_code=502,
        ) from exc
    finally:
        if owns_client:
            http.close()
    return parse_draft(raw)


def suggest_offer(
    *,
    business: str,
    industry: str | None,
    has_website: bool,
    findings: list[tuple[str, str]],
    scores: dict[str, int],
    settings: Settings,
    client: httpx.Client | None = None,
) -> tuple[str, str]:
    """Return (offer, source) where source is ai, audit, or default."""
    fallback = offer_from_findings(
        has_website=has_website,
        industry=industry,
        findings=findings,
        scores=scores,
    )
    provider = resolve_email_provider(settings)
    if provider is None:
        return fallback, "audit" if findings or scores else "default"

    prompt = _offer_instructions(
        business=business,
        industry=industry,
        has_website=has_website,
        findings=findings,
        scores=scores,
    )
    owns_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        try:
            if provider == "gemini":
                raw = _gemini_offer(http, settings, prompt)
            else:
                raw = _groq_offer(http, settings, prompt)
        except AppError as exc:
            if not _should_try_groq(settings, provider, exc):
                logger.warning("offer_suggest_failed code=%s", exc.code)
                return fallback, "audit" if findings or scores else "default"
            logger.warning("offer_suggest_fallback provider=groq")
            raw = _groq_offer(http, settings, prompt)
    except (httpx.TimeoutException, httpx.HTTPError, AppError):
        logger.warning("offer_suggest_failed")
        return fallback, "audit" if findings or scores else "default"
    finally:
        if owns_client:
            http.close()

    offer = _parse_offer(raw)
    price, _package = _settled_quote(
        has_website=has_website,
        findings=findings,
        scores=scores,
    )
    if not offer or not _keeps_price(offer, price):
        return fallback, "audit" if findings or scores or not has_website else "default"
    return offer, "ai"


def offer_from_findings(
    *,
    has_website: bool,
    industry: str | None,
    findings: list[tuple[str, str]],
    scores: dict[str, int],
) -> str:
    label = (industry or "business").strip().lower() or "business"
    price, package = _settled_quote(has_website=has_website, findings=findings, scores=scores)
    money = f"${price:,}"
    if not has_website:
        return NEW_SITE_OFFER

    weak = [
        (name, score)
        for name, score in scores.items()
        if isinstance(score, int) and score < 70
    ]
    weak.sort(key=lambda item: item[1])
    titles = [title.strip().rstrip(".") for title, _detail in findings if title.strip()]
    issue = _issue_sentence(weak, titles)
    scope = {
        "redesign": "This is a redesign of those weak parts",
        "repair": "This is a focused repair of those issues",
        "refresh": "This is a homepage refresh",
    }[package]
    if issue:
        return (
            f"I can improve this {label} website. {issue} "
            f"{scope}, and the homepage should make the next step obvious. "
            f"The settled price is {money}."
        )
    return (
        f"I can tighten this {label} website so the homepage is clearer and easier to use. "
        f"The settled price for that refresh is {money}."
    )


def _settled_quote(
    *,
    has_website: bool,
    findings: list[tuple[str, str]],
    scores: dict[str, int],
) -> tuple[int, str]:
    if not has_website:
        return 1400, "refresh"
    weak = [score for score in scores.values() if isinstance(score, int) and score < 70]
    severe = [score for score in weak if score < 45]
    issue_count = len([title for title, _detail in findings if title.strip()])
    if severe or len(weak) >= 3 or issue_count >= 4:
        return 1450, "redesign"
    if len(weak) >= 2 or issue_count >= 2:
        return 950, "repair"
    return 650, "refresh"


def _issue_sentence(
    weak: list[tuple[str, int]],
    titles: list[str],
) -> str:
    score_name = _SCORE_LABELS.get(weak[0][0], weak[0][0]).lower() if weak else ""
    if score_name and titles:
        return (
            f"The weakest area is {score_name}. "
            f"I would start with {_join_titles(titles[:3])}."
        )
    if titles:
        return f"I would start with {_join_titles(titles[:3])}."
    if score_name:
        second = ""
        if len(weak) > 1:
            second_name = _SCORE_LABELS.get(weak[1][0], weak[1][0]).lower()
            second = f" and {second_name}"
        return f"The weakest area is {score_name}{second}."
    return ""


def _join_titles(titles: list[str]) -> str:
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f"{titles[0]} and {titles[1]}"
    return f"{', '.join(titles[:-1])}, and {titles[-1]}"


def parse_draft(raw: str) -> tuple[str, str]:
    payload = _json_object(raw)
    subject = payload.get("subject")
    body = payload.get("body")
    if not isinstance(subject, str) or not isinstance(body, str):
        _invalid_draft()
    cleaned_subject = " ".join(subject.split())
    cleaned_body = body.strip()
    if not 3 <= len(cleaned_subject) <= 200 or not 20 <= len(cleaned_body) <= 6000:
        _invalid_draft()
    return cleaned_subject, cleaned_body


def _instructions(facts: str, purpose: str) -> str:
    shared = (
        "Use only the facts below. Do not invent metrics, awards, or a previous conversation.\n"
        "Do not mention AI, audits, or that the email was generated.\n"
        "Write three short paragraphs in plain sentences. No bullet list. No jargon.\n"
        "No 'I hope this email finds you well'.\n"
        "The subject is specific and under 70 characters.\n"
        "The body is 80 to 130 words, unless the tone says to keep it shorter.\n"
        "Return JSON with keys subject and body.\n\n"
    )
    if purpose == "new_site":
        task = (
            "Write one professional email offering to create a website for this business.\n"
            "Use the business name, what it does, and where it is.\n"
            "Explain that a professional website would make the business easier to find "
            "and give customers a clear way to get in touch.\n"
            "Do not claim you looked at an existing website.\n"
            "The last paragraph must use the Offer line, including its price exactly. "
            "Do not change the amount or turn it into a range.\n"
        )
    else:
        task = (
            "Write one professional email about the current website.\n"
            "Every listed score is a weak point. Give each score its own short sentence, "
            "in everyday language: speed, design, or search visibility.\n"
            "Then mention findings about how the page looks or how a customer gets in touch, "
            "when those are not already covered by the scores.\n"
            "Do not mention a score that is not listed. Do not write a checklist.\n"
            "Say why this matters for customers.\n"
            "The last paragraph must use the Offer line, including its price exactly. "
            "Do not change the amount or turn it into a range.\n"
        )
    shared = shared.replace(
        "The body is 80 to 130 words, unless the tone says to keep it shorter.\n",
        "The body is 90 to 160 words, unless the tone says to keep it shorter.\n",
    )
    return f"{task}{shared}{facts}"


def _gemini(client: httpx.Client, settings: Settings, prompt: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "subject": {"type": "STRING"},
                    "body": {"type": "STRING"},
                },
                "required": ["subject", "body"],
            },
        },
    }
    response = _gemini_generate(client, settings, payload)
    return _gemini_text(response)


def _gemini_offer(client: httpx.Client, settings: Settings, prompt: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {"offer": {"type": "STRING"}},
                "required": ["offer"],
            },
        },
    }
    response = _gemini_generate(client, settings, payload)
    return _gemini_text(response)


def _gemini_generate(client: httpx.Client, settings: Settings, payload: dict[str, object]) -> httpx.Response:
    models: list[str] = []
    preferred = settings.gemini_model.strip()
    if preferred:
        models.append(preferred)
    for model in _GEMINI_FALLBACK_MODELS:
        if model not in models:
            models.append(model)
    last: httpx.Response | None = None
    for model in models:
        response = _post(
            client,
            _GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": settings.gemini_api_key.strip()},
            json=payload,
        )
        if response.status_code < 400:
            if model != preferred:
                logger.info("email_draft_model_fallback model=%s", model)
            return response
        last = response
        if response.status_code not in {404, 429}:
            break
        logger.warning(
            "email_draft_model_retry model=%s status=%s",
            model,
            response.status_code,
        )
    assert last is not None
    _raise_for_status(last, "gemini")
    return last


def _gemini_text(response: httpx.Response) -> str:
    payload = _response_json(response)
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or not candidates:
        _invalid_draft()
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        _invalid_draft()
    texts = [
        part.get("text")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought")
    ]
    if not texts:
        _invalid_draft()
    return "\n".join(texts)


def _groq(client: httpx.Client, settings: Settings, prompt: str) -> str:
    response = _post(
        client,
        _GROQ_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key.strip()}"},
        json={
            "model": settings.groq_model.strip(),
            "temperature": 0.5,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You write plain outreach emails and return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        },
    )
    _raise_for_status(response, "groq")
    payload = _response_json(response)
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        _invalid_draft()
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        _invalid_draft()
    return content


def _groq_offer(client: httpx.Client, settings: Settings, prompt: str) -> str:
    response = _post(
        client,
        _GROQ_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key.strip()}"},
        json={
            "model": settings.groq_model.strip(),
            "temperature": 0.4,
            "max_tokens": 256,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                "You write a short professional outreach offer and return JSON only. "
                "Keep the stated price exactly."
            ),
                },
                {"role": "user", "content": prompt},
            ],
        },
    )
    _raise_for_status(response, "groq")
    payload = _response_json(response)
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        _invalid_draft()
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        _invalid_draft()
    return content


def _offer_instructions(
    *,
    business: str,
    industry: str | None,
    has_website: bool,
    findings: list[tuple[str, str]],
    scores: dict[str, int],
) -> str:
    price, package = _settled_quote(
        has_website=has_website,
        findings=findings,
        scores=scores,
    )
    lines = [
        "Write a professional first-person offer for an outreach email.",
        "Two or three sentences. No quotes. No bullet list.",
        "Do not mention AI, audits, or that this was generated.",
        "Speak as a web designer helping a local business.",
        f"Use this exact settled price: ${price:,}. Do not change it or give a range.",
        f"Business: {business.strip()}",
    ]
    if industry and industry.strip():
        lines.append(f"Industry: {industry.strip()}")
    if not has_website:
        lines.append(
            "They have no website. Offer a first professional site: homepage, contact, and mobile."
        )
    else:
        lines.append(
            "They have a website. Describe the work from the issues, then state the price."
        )
        lines.append(f"Package: {package}.")
        weak = [
            f"{_SCORE_LABELS.get(name, name)} {score}/100"
            for name, score in scores.items()
            if isinstance(score, int) and score < 70
        ]
        if weak:
            lines.append("Weak areas: " + ", ".join(weak[:4]))
        if findings:
            lines.append("Findings to address:")
            lines.extend(f"- {title}: {detail}" for title, detail in findings[:4])
    lines.append('Return JSON with key "offer".')
    return "\n".join(lines)


def _parse_offer(raw: str) -> str | None:
    try:
        payload = _json_object(raw)
    except AppError:
        return None
    value = payload.get("offer")
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip(" \"'")
    if not 20 <= len(cleaned) <= 700:
        return None
    return cleaned[:700]


def _keeps_price(offer: str, price: int) -> bool:
    compact = offer.replace(",", "").replace("$", "")
    return str(price) in compact


def _post(client: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
    response = client.post(url, **kwargs)
    if response.status_code != 503:
        return response
    time.sleep(1.2)
    return client.post(url, **kwargs)


def _should_try_groq(settings: Settings, provider: str, exc: AppError) -> bool:
    if provider != "gemini" or exc.code != "AI_DRAFT_FAILED":
        return False
    if settings.ai_email_provider.strip().lower() == "gemini":
        return False
    return bool(settings.groq_api_key.strip()) and _valid_model(settings.groq_model)


def _raise_for_status(response: httpx.Response, provider: str) -> None:
    if response.status_code < 400:
        return
    logger.warning(
        "email_draft_rejected provider=%s status=%s",
        provider,
        response.status_code,
    )
    if response.status_code == 429:
        raise AppError(
            code="AI_DRAFT_FAILED",
            message="The free limit for email drafts was reached. Wait a bit and try again.",
            status_code=429,
        )
    if response.status_code in {401, 403}:
        raise AppError(
            code="AI_DRAFT_FAILED",
            message="The email API key was rejected. Check the key in the server environment.",
            status_code=502,
        )
    if response.status_code == 404:
        raise AppError(
            code="AI_DRAFT_FAILED",
            message=(
                "That email model is not available. Set GEMINI_MODEL or GROQ_MODEL "
                "to a current free model."
            ),
            status_code=502,
        )
    raise AppError(
        code="AI_DRAFT_FAILED",
        message="The email draft could not be written. Try again in a moment.",
        status_code=502,
    )


def _response_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        _invalid_draft()


def _json_object(raw: str) -> dict[str, object]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            _invalid_draft()
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            _invalid_draft()
    if not isinstance(payload, dict):
        _invalid_draft()
    return payload


def _invalid_draft() -> NoReturn:
    raise AppError(
        code="AI_DRAFT_FAILED",
        message="The email draft came back incomplete. Try again.",
        status_code=502,
    )


def _clip(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    return cleaned[:limit]


def _valid_model(value: str) -> bool:
    return _MODEL.fullmatch(value.strip()) is not None
