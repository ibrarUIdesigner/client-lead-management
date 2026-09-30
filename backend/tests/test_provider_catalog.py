import httpx

from app.core.config import Settings
from app.services.provider_catalog import clear_provider_cache, describe_providers


def _settings(**overrides: str) -> Settings:
    values = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/client_acquisition",
        "gemini_api_key": "",
        "groq_api_key": "",
        "ai_email_provider": "",
        "gemini_model": "gemini-3.5-flash",
        "groq_model": "llama-3.3-70b-versatile",
    }
    values.update(overrides)
    return Settings(**values)


def setup_function() -> None:
    clear_provider_cache()


def test_missing_keys_do_not_call_providers() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("catalog should not be requested")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = describe_providers(_settings(), client)

    assert [item.id for item in snapshot.providers] == ["gemini", "groq"]
    assert all(item.configured is False for item in snapshot.providers)
    assert all(item.listed is None for item in snapshot.providers)


def test_gemini_catalog_reports_token_limits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models/gemini-3.5-flash")
        assert request.headers["x-goog-api-key"] == "gemini-key"
        return httpx.Response(
            200,
            json={
                "displayName": "Gemini 3.5 Flash",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 65536,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = describe_providers(_settings(gemini_api_key="gemini-key"), client)

    gemini = snapshot.providers[0]
    assert gemini.configured is True
    assert gemini.active is True
    assert gemini.listed is True
    assert gemini.display_name == "Gemini 3.5 Flash"
    assert gemini.input_tokens == 1048576
    assert gemini.output_tokens == 65536
    assert "does not report remaining credits" in gemini.credits


def test_groq_reports_price_when_the_model_is_listed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer groq-key"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "llama-3.3-70b-versatile",
                        "name": "Llama 3.3 70B",
                        "context_window": 128000,
                        "max_completion_tokens": 32768,
                        "pricing": {"prompt": "0.00000059", "completion": "0.00000079"},
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = describe_providers(
            _settings(groq_api_key="groq-key", ai_email_provider="groq"),
            client,
        )

    groq = snapshot.providers[1]
    assert groq.active is True
    assert groq.listed is True
    assert groq.display_name == "Llama 3.3 70B"
    assert groq.input_tokens == 128000
    assert groq.prompt_usd_per_million == 0.59
    assert groq.completion_usd_per_million == 0.79
    assert snapshot.providers[0].active is False


def test_groq_marks_a_retired_model() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "other-model"}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = describe_providers(_settings(groq_api_key="groq-key"), client)

    groq = snapshot.providers[1]
    assert groq.listed is False
    assert groq.input_tokens is None
    assert "does not report a credit balance" in groq.credits
