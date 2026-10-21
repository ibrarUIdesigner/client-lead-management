from unittest.mock import Mock

import httpx
import pytest

from app.core.config import Settings
from app.integrations.apollo_source import fetch_apollo
from app.integrations.scrapingbee_source import fetch_scrapingbee
from app.integrations.serpapi_source import fetch_serpapi
from app.services.email_finder import extract_clean_emails, find_business_email


def test_extract_clean_emails() -> None:
    html = """
    <html>
      <body>
        <p>Contact us at info@exampledental.pk or support@clinic.com</p>
        <img src="logo@2x.png" />
        <script src="bundle@1.2.3.js"></script>
        <a href="mailto:booking@exampledental.pk">Book now</a>
      </body>
    </html>
    """
    emails = extract_clean_emails(html)
    assert "info@exampledental.pk" in emails
    assert "support@clinic.com" in emails
    assert "booking@exampledental.pk" in emails
    assert not any(e.endswith(".png") for e in emails)
    assert not any(e.endswith(".js") for e in emails)


def test_apollo_fetch_skipped_without_key() -> None:
    settings = Settings(apollo_api_key="")
    client = Mock(spec=httpx.Client)
    listings, note = fetch_apollo(
        category="dentist",
        city="Lahore",
        country="Pakistan",
        settings=settings,
        client=client,
    )
    assert listings == []
    assert "skipped" in note.lower()


def test_apollo_fetch_parses_organizations() -> None:
    settings = Settings(apollo_api_key="mock_key")
    client = Mock(spec=httpx.Client)
    client.post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "organizations": [
                {
                    "id": "org_1",
                    "name": "Apex Dental",
                    "website_url": "https://apexdental.pk",
                    "phone": "+92 300 1234567",
                    "city": "Lahore",
                    "country": "Pakistan",
                    "industry": "Healthcare",
                    "short_description": "Premier dental clinic in Lahore.",
                }
            ]
        },
    )
    # Mock client.get for email finder
    client.get.return_value = Mock(
        status_code=200,
        text="<html><body>Email: contact@apexdental.pk</body></html>",
    )

    listings, note = fetch_apollo(
        category="dentist",
        city="Lahore",
        country="Pakistan",
        settings=settings,
        client=client,
    )
    assert len(listings) == 1
    assert listings[0].name == "Apex Dental"
    assert listings[0].email == "contact@apexdental.pk"
    assert listings[0].source == "apollo"
    assert "1" in note


def test_serpapi_fetch_skipped_without_key() -> None:
    settings = Settings(serpapi_api_key="")
    client = Mock(spec=httpx.Client)
    listings, note = fetch_serpapi(
        category="dentist",
        city="Lahore",
        country="Pakistan",
        settings=settings,
        client=client,
    )
    assert listings == []
    assert "skipped" in note.lower()


def test_serpapi_fetch_parses_local_results() -> None:
    settings = Settings(serpapi_api_key="mock_serp_key")
    client = Mock(spec=httpx.Client)
    client.get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "local_results": [
                {
                    "title": "City Dental Clinic",
                    "website": "https://citydental.com",
                    "phone": "+92 42 35780000",
                    "address": "Gulberg III, Lahore",
                    "rating": 4.8,
                    "reviews": 120,
                    "place_id": "ChIJ123456",
                }
            ]
        },
    )

    listings, note = fetch_serpapi(
        category="dentist",
        city="Lahore",
        country="Pakistan",
        settings=settings,
        client=client,
    )
    assert len(listings) == 1
    assert listings[0].name == "City Dental Clinic"
    assert listings[0].source == "serpapi"
    assert "1" in note


def test_scrapingbee_fetch_skipped_without_key() -> None:
    settings = Settings(scrapingbee_api_key="")
    client = Mock(spec=httpx.Client)
    listings, note = fetch_scrapingbee(
        category="dentist",
        city="Lahore",
        country="Pakistan",
        settings=settings,
        client=client,
    )
    assert listings == []
    assert "skipped" in note.lower()


def test_scrapingbee_fetch_parses_google_store() -> None:
    settings = Settings(scrapingbee_api_key="mock_bee_key")
    client = Mock(spec=httpx.Client)
    client.get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "organic_results": [
                {
                    "title": "Elite Smile Dental Care - Lahore",
                    "url": "https://elitesmile.pk",
                    "description": "Call 0300-1112233 or email info@elitesmile.pk for appointments.",
                    "domain": "elitesmile.pk",
                }
            ]
        },
    )

    listings, note = fetch_scrapingbee(
        category="dentist",
        city="Lahore",
        country="Pakistan",
        settings=settings,
        client=client,
    )
    assert len(listings) == 1
    assert listings[0].name == "Elite Smile Dental Care"
    assert listings[0].email == "info@elitesmile.pk"
    assert listings[0].source == "scrapingbee"
    assert "1" in note
