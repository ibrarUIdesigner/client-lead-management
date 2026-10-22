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
    "The settled price for that first site is $850."
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
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
)
_GROQ_FALLBACK_MODELS = (
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
)
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(frozen=True)
class EmailBrief:
    business: str
    industry: str | None
    services: str | None
    notes: str | None
    tags: tuple[str, ...]
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
    sender_email: str | None = None
    sender_whatsapp: str | None = None
    sender_portfolio: str | None = None
    research_summary: str | None = None
    proactive_solutions: tuple[str, ...] = ()


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
    sender_email: str | None = None,
    sender_whatsapp: str | None = None,
    sender_portfolio: str | None = None,
    notes: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    research_summary: str | None = None,
    proactive_solutions: list[str] | tuple[str, ...] | None = None,
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
        notes=_clip(notes, 600),
        tags=tuple(t.strip() for t in (tags or []) if t.strip())[:10],
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
        sender_email=" ".join((sender_email or "").split()) or None,
        sender_whatsapp=" ".join((sender_whatsapp or "").split()) or None,
        sender_portfolio=" ".join((sender_portfolio or "").split()) or None,
        purpose="review" if has_website else "new_site",
        research_summary=research_summary.strip() if research_summary and research_summary.strip() else None,
        proactive_solutions=tuple(s.strip() for s in (proactive_solutions or []) if s.strip())[:5],
    )


def render_brief(brief: EmailBrief) -> str:
    """Render a structured context block from the lead's Overview data for the AI prompt."""
    lines = [
        "=== LEAD OVERVIEW ===",
        f"Business name: {brief.business}",
        f"Has a public website: {'yes' if brief.has_website else 'no'}",
    ]
    if brief.website:
        lines.append(f"Website: {brief.website}")
    if brief.industry:
        lines.append(f"Industry: {brief.industry}")
    if brief.services:
        lines.append(f"Description: {brief.services}")
    if brief.location:
        lines.append(f"Location: {brief.location}")
    if brief.tags:
        lines.append(f"Tags: {', '.join(brief.tags)}")

    if brief.greeting_name:
        lines.append(f"Greeting name: {brief.greeting_name}")
    else:
        lines.append("Greeting name: unknown. Open with Hi, and do not invent a name.")

    if brief.purpose == "new_site":
        lines.append(
            "Email purpose: this business has no website. Offer to create a professional website."
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

    if brief.research_summary or brief.proactive_solutions:
        lines.append("=== RESEARCH INTELLIGENCE & PROACTIVE SOLUTIONS ===")
        if brief.research_summary:
            lines.append(f"Researched Intelligence Summary: {brief.research_summary}")
        if brief.proactive_solutions:
            lines.append("Proactive solutions to offer the customer:")
            lines.extend(f"- {sol}" for sol in brief.proactive_solutions)
        lines.append("Instruction: Weave one of these proactive solutions into your value proposition to directly address their specific bottleneck.")

    lines.append(f"Offer: {brief.offer}")
    lines.append(f"Tone: {brief.tone}. {_TONES.get(brief.tone, '')}")
    sender = brief.sender_name or "Ibrar"
    lines.append(f"Sign the email as: {sender}")
    sig_details = []
    if brief.sender_portfolio:
        sig_details.append(f"Portfolio: {brief.sender_portfolio}")
    if brief.sender_whatsapp:
        sig_details.append(f"WhatsApp: {brief.sender_whatsapp}")
    if brief.sender_email:
        sig_details.append(f"Email: {brief.sender_email}")
    if sig_details:
        lines.append("Sender signature details to include at the end:")
        lines.extend(f"- {d}" for d in sig_details)
        lines.append("Instruction: Always include the portfolio link, WhatsApp number, and email in the sign-off.")
    return "\n".join(lines)


def append_sender_signature(
    body: str,
    *,
    name: str | None = None,
    portfolio: str | None = None,
    whatsapp: str | None = None,
    email: str | None = None,
) -> str:
    """Ensure sender signature details (portfolio, whatsapp, email) are attached cleanly."""
    cleaned = body.rstrip()
    if not (portfolio or whatsapp or email):
        return cleaned

    parts_to_add: list[str] = []
    if portfolio and portfolio not in cleaned:
        parts_to_add.append(f"Portfolio: {portfolio}")
    if whatsapp and whatsapp not in cleaned:
        parts_to_add.append(f"WhatsApp: {whatsapp}")
    if email and email not in cleaned:
        parts_to_add.append(f"Email: {email}")

    if not parts_to_add:
        return cleaned

    return cleaned + "\n" + "\n".join(parts_to_add)


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
    http = client or httpx.Client(timeout=25.0)
    raw = None
    try:
        if provider == "gemini":
            try:
                raw = _gemini(http, settings, prompt)
            except Exception as exc:
                if _should_try_groq(settings, provider, exc):
                    logger.warning("email_draft_gemini_failed (%s), falling back to Groq", exc)
                    try:
                        raw = _groq(http, settings, prompt)
                    except Exception as groq_exc:
                        logger.error("email_draft_groq_fallback_failed: %s", groq_exc)
                        raise
                else:
                    if isinstance(exc, AppError):
                        raise
                    raise AppError(
                        code="AI_DRAFT_FAILED",
                        message="The email draft could not be written. Try again in a moment.",
                        status_code=502,
                    ) from exc
        else:
            raw = _groq(http, settings, prompt)
    except httpx.TimeoutException as exc:
        logger.warning("email_draft_timeout provider=%s", provider)
        if _should_try_groq(settings, provider, exc):
            logger.warning("email_draft_fallback provider=groq after timeout")
            try:
                raw = _groq(http, settings, prompt)
            except Exception:
                raise AppError(
                    code="AI_DRAFT_FAILED",
                    message="The email draft took too long. Try again in a moment.",
                    status_code=504,
                ) from exc
        else:
            raise AppError(
                code="AI_DRAFT_FAILED",
                message="The email draft took too long. Try again in a moment.",
                status_code=504,
            ) from exc
    except httpx.HTTPError as exc:
        logger.warning("email_draft_failed provider=%s", provider)
        if _should_try_groq(settings, provider, exc):
            logger.warning("email_draft_fallback provider=groq after http error")
            try:
                raw = _groq(http, settings, prompt)
            except Exception:
                raise AppError(
                    code="AI_DRAFT_FAILED",
                    message="The email draft could not be written. Try again in a moment.",
                    status_code=502,
                ) from exc
        else:
            raise AppError(
                code="AI_DRAFT_FAILED",
                message="The email draft could not be written. Try again in a moment.",
                status_code=502,
            ) from exc
    finally:
        if owns_client:
            http.close()
    parsed_subj, parsed_body = parse_draft(raw)
    name = brief.sender_name or getattr(settings, "outreach_sender_name", None) or "Ibrar"
    portfolio = brief.sender_portfolio or getattr(settings, "outreach_sender_portfolio", None)
    whatsapp = brief.sender_whatsapp or getattr(settings, "outreach_sender_whatsapp", None)
    email = brief.sender_email or getattr(settings, "outreach_sender_email", None)
    parsed_body = append_sender_signature(
        parsed_body,
        name=name,
        portfolio=portfolio,
        whatsapp=whatsapp,
        email=email,
    )
    return parsed_subj, parsed_body


def suggest_offer(
    *,
    business: str,
    industry: str | None,
    has_website: bool,
    findings: list[tuple[str, str]],
    scores: dict[str, int],
    settings: Settings,
    research_summary: str | None = None,
    proactive_solutions: list[str] | tuple[str, ...] | None = None,
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
        research_summary=research_summary,
        proactive_solutions=proactive_solutions,
    )
    owns_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        if provider == "gemini":
            try:
                raw = _gemini_offer(http, settings, prompt)
            except Exception as exc:
                if _should_try_groq(settings, provider, exc):
                    logger.warning("offer_suggest_gemini_failed (%s), falling back to Groq", exc)
                    try:
                        raw = _groq_offer(http, settings, prompt)
                    except Exception:
                        return fallback, "audit" if findings or scores else "default"
                else:
                    return fallback, "audit" if findings or scores else "default"
        else:
            raw = _groq_offer(http, settings, prompt)
    except Exception:
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
    """Calculate pricing strictly between $500 and $1,000 USD based on audit & research complexity."""
    if not has_website:
        return 850, "refresh"
    weak = [score for score in scores.values() if isinstance(score, int) and score < 70]
    severe = [score for score in weak if score < 45]
    issue_count = len([title for title, _detail in findings if title.strip()])
    if severe or len(weak) >= 3 or issue_count >= 4:
        return 950, "redesign"
    if len(weak) >= 2 or issue_count >= 2:
        return 750, "repair"
    return 550, "refresh"


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
    """
    Build the AI prompt following the strategic directives:
    - Peer-to-peer, observant, concise tone
    - Strictly under 110 words body
    - 3–5 word subject, neutral and curiosity-driven
    - Open with a specific detail extracted from the Overview
    - 1–2 sentence value prop focused on outcome, not features
    - Low-friction single CTA
    - No corporate filler, no invented metrics
    """
    strict_rules = (
        "RULES (non-negotiable):\n"
        "• Use ONLY the facts in the LEAD OVERVIEW below. Do not invent data, metrics, or prior conversations.\n"
        "• Do NOT mention AI, audits, or that this email was generated.\n"
        "• NEVER use: 'I hope this email finds you well', 'I came across', 'In today's fast-paced world', 'game-changer', 'revolutionary'.\n"
        "• Subject line: 3–5 words, sentence case or all lowercase, neutral and curiosity-driven. No clickbait. No fake urgency.\n"
        "• Body: strictly under 110 words. Every sentence must earn its place.\n"
        "• Tone: peer-to-peer — observant, candid, and specific. No sycophancy. No marketing jargon.\n"
        "• If RESEARCH INTELLIGENCE & PROACTIVE SOLUTIONS are provided below, make sure the value paragraph proactively pitches that exact solution to their situation.\n"
        "• Structure (3 short paragraphs, no bullets):\n"
        "    1. Opening — address ONE specific operational or contextual detail from the Overview. Make it feel observed, not generic.\n"
        "    2. Value — 1–2 sentences showing a clear outcome or operational relief. Focus on result, not feature list.\n"
        "    3. CTA — one low-friction ask (e.g. 'Worth a quick look?', 'Open to a brief breakdown?'). Never ask for a 30-minute demo.\n"
        "• Closing: include the Offer line verbatim in the CTA paragraph. Do not alter the price.\n"
        "• Return clean JSON only — keys: subject (string) and body (string).\n\n"
    )

    if purpose == "new_site":
        task = (
            "TASK: Write a first-contact outreach email to a business that has no website.\n"
            "The opening must reference something specific about what this business does or where it operates.\n"
            "The value paragraph explains concretely how a professional website helps their customers reach them.\n"
            "Do NOT claim you reviewed or audited any existing site.\n"
        )
    else:
        task = (
            "TASK: Write a first-contact outreach email referencing the business's existing website.\n"
            "The opening must pick ONE concrete detail from the findings or scores — not a vague claim.\n"
            "Translate scores into plain customer-impact language (e.g. slow load = customers leave).\n"
            "Do not list every finding. Choose the sharpest angle and build the email around it.\n"
            "Do NOT write a checklist or bullet list inside the email body.\n"
        )

    return f"{task}\n{strict_rules}{facts}"


def _gemini(client: httpx.Client, settings: Settings, prompt: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 4096,
            "thinkingConfig": {"thinkingBudget": 0},
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
            "thinkingConfig": {"thinkingBudget": 0},
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
        try:
            response = _post(
                client,
                _GEMINI_URL.format(model=model),
                headers={"x-goog-api-key": settings.gemini_api_key.strip()},
                json=payload,
            )
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("email_draft_model_error model=%s error=%s", model, exc)
            continue
        if response.status_code < 400:
            if model != preferred:
                logger.info("email_draft_model_fallback model=%s", model)
            return response
        last = response
        if response.status_code not in {404, 408, 429, 502, 503, 504}:
            break
        logger.warning(
            "email_draft_model_retry model=%s status=%s",
            model,
            response.status_code,
        )
    if last is None:
        raise httpx.TimeoutException("All Gemini models timed out or failed to connect.")
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
    models: list[str] = []
    preferred = settings.groq_model.strip()
    if preferred:
        models.append(preferred)
    for model in _GROQ_FALLBACK_MODELS:
        if model not in models:
            models.append(model)
    last: httpx.Response | None = None
    for model in models:
        try:
            response = _post(
                client,
                _GROQ_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key.strip()}"},
                json={
                    "model": model,
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
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("groq_draft_error model=%s error=%s", model, exc)
            continue
        if response.status_code < 400:
            return _groq_text(response)
        last = response
        if response.status_code not in {404, 429}:
            break
    if last is None:
        raise httpx.TimeoutException("All Groq models timed out or failed to connect.")
    _raise_for_status(last, "groq")
    return _groq_text(last)


def _groq_text(response: httpx.Response) -> str:
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
    models: list[str] = []
    preferred = settings.groq_model.strip()
    if preferred:
        models.append(preferred)
    for model in _GROQ_FALLBACK_MODELS:
        if model not in models:
            models.append(model)
    last: httpx.Response | None = None
    for model in models:
        try:
            response = _post(
                client,
                _GROQ_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key.strip()}"},
                json={
                    "model": model,
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
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("groq_offer_error model=%s error=%s", model, exc)
            continue
        if response.status_code < 400:
            return _groq_text(response)
        last = response
        if response.status_code not in {404, 429}:
            break
    if last is None:
        raise httpx.TimeoutException("All Groq models timed out or failed to connect.")
    _raise_for_status(last, "groq")
    return _groq_text(last)


def _offer_instructions(
    *,
    business: str,
    industry: str | None,
    has_website: bool,
    findings: list[tuple[str, str]],
    scores: dict[str, int],
    research_summary: str | None = None,
    proactive_solutions: list[str] | tuple[str, ...] | None = None,
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
    if research_summary:
        lines.append(f"Business Context: {research_summary}")
    if proactive_solutions:
        lines.append("Proactive solutions identified:")
        lines.extend(f"- {sol}" for sol in proactive_solutions[:3])
        lines.append("Instruction: Anchor the value proposition of the offer around solving these bottlenecks.")
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


def _should_try_groq(settings: Settings, provider: str, exc: object = None) -> bool:
    if provider != "gemini":
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
