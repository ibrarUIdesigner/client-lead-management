from app.core.config import Settings
from app.models.lead import Lead
from app.services.outreach_policy import (
    can_auto_send,
    country_code,
    policy_for,
    with_compliance_footer,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/x",
        "postgres_url": "",
        "outreach_postal_address": "1 Main St, Austin, TX",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _lead(**overrides: object) -> Lead:
    values: dict[str, object] = {
        "business_name": "Acme",
        "country": "United States",
        "email": "hello@acme.example",
        "lead_status": "QUALIFIED",
        "do_not_contact": False,
        "email_suppressed": False,
    }
    values.update(overrides)
    return Lead(**values)  # type: ignore[arg-type]


def test_country_names_and_codes_normalize() -> None:
    assert country_code("United States") == "US"
    assert country_code("uk") == "GB"
    assert country_code("de") == "DE"
    assert country_code("Atlantis") is None
    assert country_code(None) is None


def test_unknown_and_strict_countries_are_never_auto_sent() -> None:
    settings = _settings()
    assert policy_for(_lead(country="United States"), settings) == "allow"
    assert policy_for(_lead(country="Germany"), settings) == "manual"
    assert policy_for(_lead(country="Atlantis"), settings) == "manual"
    assert policy_for(_lead(country=None), settings) == "manual"


def test_policy_can_be_overridden_from_settings() -> None:
    settings = _settings(outreach_country_policy='{"pk": "allow", "US": "block", "bad": "yes"}')
    assert policy_for(_lead(country="Pakistan"), settings) == "allow"
    assert policy_for(_lead(country="United States"), settings) == "block"


def test_invalid_policy_json_falls_back_to_defaults() -> None:
    settings = _settings(outreach_country_policy="{not json")
    assert policy_for(_lead(country="United States"), settings) == "allow"


def test_auto_send_requires_every_safety_condition() -> None:
    settings = _settings()
    assert can_auto_send(_lead(), settings) == (True, "ok")
    assert not can_auto_send(_lead(do_not_contact=True), settings)[0]
    assert not can_auto_send(_lead(email_suppressed=True), settings)[0]
    assert not can_auto_send(_lead(email=None), settings)[0]
    assert not can_auto_send(_lead(country="Germany"), settings)[0]
    assert not can_auto_send(_lead(), _settings(outreach_postal_address=""))[0]


def test_footer_is_added_once_with_address() -> None:
    settings = _settings()
    once = with_compliance_footer("Hello there.", settings)
    assert 'reply "unsubscribe"' in once
    assert "1 Main St, Austin, TX" in once
    assert with_compliance_footer(once, settings) == once
