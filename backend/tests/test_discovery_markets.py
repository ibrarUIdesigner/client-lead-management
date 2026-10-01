import httpx
import pytest

from app.core.config import Settings
from app.integrations.place_sources import collect_places_anywhere
from app.integrations.source_errors import PlaceSourceError
from app.services.discovery_markets import markets_for
from app.services.place_listings import FoundBusiness


def test_markets_follow_the_sources_that_are_turned_on() -> None:
    markets = markets_for(
        use_openstreetmap=False,
        use_google=False,
        use_yelp=False,
        use_yell=True,
        use_businesslist=True,
        use_epages=False,
    )
    cities = [market.city for market in markets]

    assert "Lahore" in cities
    assert "London" in cities
    assert "Manchester" in cities
    assert "Portland" not in cities


def test_anywhere_search_asks_each_covered_city(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_collect(**kwargs: object) -> tuple[list[FoundBusiness], list[str]]:
        city = str(kwargs["city"])
        calls.append(city)
        if city != "Lahore":
            return [], []
        return [
            FoundBusiness(
                source_key="osm:1",
                source="openstreetmap",
                name="City Pharmacy",
                industry="Pharmacy",
                phone=None,
                email=None,
                website_url=None,
                facebook_url=None,
                instagram_url=None,
                google_maps_url=None,
                city=city,
                country=str(kwargs["country"]),
                website_status="missing",
                lead_score=70,
                description="",
                notes="",
                tags=["discovered"],
            )
        ], []

    monkeypatch.setattr("app.integrations.place_sources.collect_places", fake_collect)
    monkeypatch.setattr("app.integrations.place_sources.time.sleep", lambda _seconds: None)
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://app:app@127.0.0.1:1/client_acquisition",
        gemini_api_key="",
        groq_api_key="",
        ai_email_provider="",
    )

    transport = httpx.MockTransport(lambda _request: httpx.Response(500))
    with httpx.Client(transport=transport) as client:
        found, notes = collect_places_anywhere(
            category="pharmacy",
            use_openstreetmap=True,
            use_google=False,
            use_yelp=False,
            use_yell=False,
            use_businesslist=True,
            use_epages=True,
            settings=settings,
            client=client,
        )

    assert calls[0] == "Lahore"
    assert "Karachi" in calls
    assert "London" in calls
    assert found[0].city == "Lahore"
    assert any("Lahore returned 1" in note for note in notes)


def test_anywhere_search_fails_when_every_city_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.integrations.place_sources.collect_places",
        lambda **_kwargs: ([], []),
    )
    monkeypatch.setattr("app.integrations.place_sources.time.sleep", lambda _seconds: None)
    settings = Settings(app_env="test")

    with httpx.Client() as client:
        with pytest.raises(PlaceSourceError):
            collect_places_anywhere(
                category="pharmacy",
                use_openstreetmap=False,
                use_google=False,
                use_yelp=False,
                use_yell=True,
                use_businesslist=False,
                use_epages=False,
                settings=settings,
                client=client,
            )
