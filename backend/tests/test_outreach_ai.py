import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.outreach_ai import build_brief, draft_email, render_brief


def _settings(**overrides: str) -> Settings:
    values: dict[str, str] = {
        "gemini_api_key": "",
        "groq_api_key": "",
        "ai_email_provider": "",
    }
    values.update(overrides)
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://app:app@127.0.0.1:1/client_acquisition",
        gemini_api_key=values["gemini_api_key"],
        groq_api_key=values["groq_api_key"],
        ai_email_provider=values["ai_email_provider"],
        gemini_model="gemini-3.5-flash",
        groq_model="llama-3.3-70b-versatile",
    )


def _email_payload() -> dict[str, str]:
    return {
        "subject": "A faster homepage for Northwind Cafe",
        "body": (
            "Hi Ada,\n\n"
            "The homepage takes more than four seconds to load, "
            "which makes the menu harder to reach.\n\n"
            "I can put together a clearer homepage if that would help.\n\n"
            "Best regards,\nSam"
        ),
    }


def _brief():
    return build_brief(
        business="Northwind Cafe",
        industry="Cafe",
        description="Coffee and lunch.",
        city="Austin",
        country="United States",
        website="https://northwind.example",
        greeting_name="Ada",
        findings=[("Slow pages", "The homepage took more than 4 seconds to load.")],
        scores={"performance": 42},
        offer="A clearer homepage.",
        tone="professional",
        sender_name="Sam",
    )


def test_a_lead_without_a_website_offers_to_create_one() -> None:
    text = render_brief(
        build_brief(
            business="Northwind Cafe",
            industry="Cafe",
            description="Coffee and lunch.",
            city="Austin",
            country="United States",
            website=None,
            greeting_name=None,
            findings=[("Missing website", "This business has no website address.")],
            scores={"performance": 0, "seo": 0, "design": 0},
            offer=None,
            tone="professional",
            sender_name=None,
        )
    )

    assert "this business has no website" in text
    assert "create a professional website" in text
    assert "Coffee and lunch." in text
    assert "Austin, United States" in text
    assert "Performance" not in text
    assert "Missing website" not in text
    assert "Do not mention scores" in text


def test_a_reviewed_website_includes_design_and_seo_scores() -> None:
    text = render_brief(
        build_brief(
            business="Northwind Cafe",
            industry="Cafe",
            description=None,
            city=None,
            country=None,
            website="https://northwind.example",
            greeting_name=None,
            findings=[("Slow pages", "The homepage took more than 4 seconds to load.")],
            scores={"performance": 42, "design": 38, "seo": 55},
            offer="A clearer homepage.",
            tone="professional",
            sender_name=None,
        )
    )

    assert "weak points of the current website" in text
    assert "Performance 42/100" in text
    assert "Design 38/100" in text
    assert "SEO 55/100" in text


def test_brief_keeps_private_notes_and_contact_details_out() -> None:
    text = render_brief(_brief())

    assert "Northwind Cafe" in text
    assert "https://northwind.example" in text
    assert "The homepage took more than 4 seconds to load." in text
    assert "A clearer homepage." in text
    assert "ada@northwind.example" not in text
    assert "Call after 6" not in text
    assert "555-0100" not in text


def test_missing_keys_report_that_email_drafts_are_not_configured() -> None:
    with pytest.raises(AppError) as caught:
        draft_email(_brief(), _settings())

    assert caught.value.code == "AI_NOT_CONFIGURED"
    assert caught.value.status_code == 503


def test_gemini_draft_sends_the_public_brief_and_reads_the_email() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key", "")
        seen["body"] = request.content.decode()
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps(_email_payload())}
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    subject, body = draft_email(
        _brief(),
        _settings(gemini_api_key="test-key", ai_email_provider="gemini"),
        client,
    )

    assert seen["url"].endswith("/models/gemini-3.5-flash:generateContent")
    assert "key=" not in seen["url"]
    assert seen["key"] == "test-key"
    assert "Northwind Cafe" in seen["body"]
    assert "ada@northwind.example" not in seen["body"]
    assert subject == "A faster homepage for Northwind Cafe"
    assert "more than four seconds" in body


def test_groq_draft_reads_json_wrapped_in_a_fence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer groq-test"
        assert request.url.host == "api.groq.com"
        message = (
            "```json\n"
            '{"subject":"Lunch is hard to find","body":"Hi Ada,\\n\\n'
            'The menu is hard to find on the current homepage.\\n\\nBest regards,\\nSam"}\n'
            "```"
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": message}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    subject, body = draft_email(
        _brief(),
        _settings(groq_api_key="groq-test", ai_email_provider="groq"),
        client,
    )

    assert subject == "Lunch is hard to find"
    assert "hard to find" in body


def test_a_rate_limit_is_reported_without_the_provider_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "slow down"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AppError) as caught:
        draft_email(
            _brief(),
            _settings(gemini_api_key="test-key", ai_email_provider="gemini"),
            client,
        )

    assert caught.value.status_code == 429
    assert "free limit" in caught.value.message
    assert "slow down" not in caught.value.message
