from datetime import UTC, datetime
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.core.errors import AppError
from app.integrations.apify import ApifyClient
from app.main import create_app
from app.models.enums import ApifyRunStatus
from app.services.apify_mapping import (
    build_fields,
    classify_import,
    coerce_input,
    connector_identity,
    extract_input_schema,
    last_run_started_at,
    normalize_actor_ref,
    prepare_item,
    same_business,
    start_decision,
    summarize_pricing,
    validate_limits,
)
from tests.test_health import _settings

SCHEMA = {
    "type": "object",
    "required": ["searchTerms"],
    "properties": {
        "searchTerms": {
            "title": "Search terms",
            "type": "array",
            "editor": "stringList",
            "description": "Who to look for.",
        },
        "location": {
            "title": "Location",
            "type": "string",
            "prefill": "Lahore",
        },
        "maxResults": {
            "title": "Max results",
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
        },
        "language": {
            "title": "Language",
            "type": "string",
            "enum": ["en", "ur"],
            "enumTitles": ["English", "Urdu"],
        },
        "startUrls": {
            "title": "Start URLs",
            "type": "array",
            "editor": "requestListSources",
        },
        "internalToken": {
            "title": "Internal",
            "type": "string",
            "editor": "hidden",
            "default": "keep",
        },
    },
}


def test_account_actors_use_their_published_title() -> None:
    display_name, source, description = connector_identity(
        {
            "id": "AabCualFIriz3X6Fs",
            "username": "vortex_data",
            "name": "google-maps",
            "title": "Google Maps Scraper",
            "description": "Extract places from Google Maps.",
        }
    )

    assert display_name == "Google Maps Scraper"
    assert source == "vortex_data/google-maps"
    assert description == "Extract places from Google Maps."
    assert (
        last_run_started_at({"stats": {"lastRunStartedAt": "2026-10-01T10:52:42.596Z"}})
        == "2026-10-01T10:52:42.596Z"
    )


def test_actor_refs_use_the_tilde_form() -> None:
    assert normalize_actor_ref("owner/actor-name") == "owner~actor-name"
    assert normalize_actor_ref("nwua9Gu5YrADL7ZDj") == "nwua9Gu5YrADL7ZDj"

    with pytest.raises(AppError) as caught:
        normalize_actor_ref("not an actor")

    assert caught.value.status_code == 422


def test_input_fields_cover_search_filters_and_result_limits() -> None:
    fields = {field.key: field for field in build_fields(SCHEMA)}

    assert fields["searchTerms"].group == "search"
    assert fields["location"].group == "search"
    assert fields["location"].default_value == "Lahore"
    assert fields["maxResults"].group == "limit"
    assert fields["language"].field_type == "enum"
    assert fields["language"].options[0].label == "English"
    assert fields["startUrls"].field_type == "url_list"
    assert fields["internalToken"].field_type == "hidden"


def test_schema_can_be_read_from_the_build_definition_or_legacy_string() -> None:
    assert extract_input_schema({"actorDefinition": {"input": SCHEMA}})["required"] == [
        "searchTerms"
    ]
    assert extract_input_schema({"inputSchema": '{"type":"object","properties":{}}'}) == {
        "type": "object",
        "properties": {},
    }


def test_run_input_is_validated_against_the_actor_schema() -> None:
    cleaned = coerce_input(
        SCHEMA,
        {
            "searchTerms": ["dentists"],
            "maxResults": 20,
            "language": "en",
            "startUrls": ["https://example.com/listing"],
        },
    )

    assert cleaned["searchTerms"] == ["dentists"]
    assert cleaned["location"] == "Lahore"
    assert cleaned["maxResults"] == 20
    assert cleaned["startUrls"] == [{"url": "https://example.com/listing"}]
    assert cleaned["internalToken"] == "keep"

    with pytest.raises(AppError) as missing:
        coerce_input(SCHEMA, {})
    assert missing.value.message == "Enter Search terms."

    with pytest.raises(AppError) as bounds:
        coerce_input(SCHEMA, {"searchTerms": ["dentists"], "maxResults": 500})
    assert "at most" in bounds.value.message


def test_pricing_enables_the_cap_and_pay_per_result_limit() -> None:
    per_result = summarize_pricing(
        {
            "pricingModel": "PRICE_PER_DATASET_ITEM",
            "pricePerUnitUsd": 0.004,
            "unitName": "result",
            "minimalMaxTotalChargeUsd": 0.5,
        }
    )
    per_event = summarize_pricing(
        {
            "pricingModel": "PAY_PER_EVENT",
            "actorChargeEvents": {
                "result": {"eventTitle": "Result", "eventPriceUsd": 0.01},
            },
        }
    )
    unknown = summarize_pricing(None)

    assert per_result.supports_max_items is True
    assert per_result.supports_max_charge is True
    assert per_result.details == ["$0.0040 per result"]
    assert per_event.supports_max_items is False
    assert per_event.details == ["Result: $0.0100 each"]
    assert unknown.supports_max_charge is True
    assert unknown.details[0].startswith("Pricing information")

    validate_limits(per_result, 10, 1)
    with pytest.raises(AppError) as low_cap:
        validate_limits(per_result, None, 0.1)
    assert "at least $0.50" in low_cap.value.message
    with pytest.raises(AppError) as wrong_limit:
        validate_limits(per_event, 10, None)
    assert "does not charge per result" in wrong_limit.value.message


def test_the_same_result_keeps_one_source_key() -> None:
    collected = datetime(2026, 10, 1, tzinfo=UTC)
    item = {
        "title": "Northwind Cafe",
        "url": "https://northwind.example/menu?utm_source=ad",
        "city": "Lahore",
        "phone": "+92 300 0000000",
        "email": "hello@northwind.example",
        "scrapedAt": "2026-10-01T08:00:00.000Z",
    }

    first = prepare_item(item, actor_id="actor1", collected_at=collected)
    second = prepare_item(dict(item), actor_id="actor1", collected_at=collected)

    assert first.source_key == second.source_key
    assert first.source_url == "https://northwind.example/menu"
    assert first.website_url == first.source_url
    assert first.collected_at.isoformat().startswith("2026-10-01T08:00:00")
    assert first.city == "Lahore"
    assert classify_import(provenance_exists=False, lead_exists=False) == "create"
    assert classify_import(provenance_exists=True, lead_exists=True) == "skip"
    assert classify_import(provenance_exists=False, lead_exists=True) == "attach"
    assert same_business(
        first.source_key,
        first.website_url,
        None,
        existing_source_key="manual:1",
        existing_website_url=first.website_url,
        existing_google_maps_url=None,
    )
    maps = prepare_item(
        {"name": "Clinic", "googleMapsUrl": "https://maps.google.com/maps?q=clinic"},
        actor_id="actor1",
        collected_at=collected,
    )
    assert maps.website_url is None
    assert maps.google_maps_url == maps.source_url


def test_duplicate_submissions_do_not_start_another_run() -> None:
    assert start_decision(existing_request=True, active_run=False) == "replay"
    assert start_decision(existing_request=False, active_run=True) == "blocked"
    assert start_decision(existing_request=False, active_run=False) == "start"
    assert {
        ApifyRunStatus.SUCCEEDED.value,
        ApifyRunStatus.FAILED.value,
        ApifyRunStatus.TIMED_OUT.value,
        ApifyRunStatus.ABORTED.value,
    } <= {status.value for status in ApifyRunStatus}


def test_client_uses_official_async_endpoints_and_hides_the_token() -> None:
    token = "super-secret-token"
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.url.query.decode()))
        assert request.headers["Authorization"] == f"Bearer {token}"
        assert token not in str(request.url)
        path = request.url.path
        if request.method == "POST" and path.endswith("/runs"):
            return httpx.Response(201, json={"data": {"id": "run1", "status": "READY"}})
        if path.endswith("/dataset/items"):
            return httpx.Response(
                200,
                json=[{"url": "https://example.com"}],
                headers={"X-Apify-Pagination-Total": "3"},
            )
        if path.endswith("/abort"):
            return httpx.Response(200, json={"data": {"id": "run1", "status": "ABORTING"}})
        if path.endswith("/builds/default"):
            return httpx.Response(
                200,
                json={"data": {"actorDefinition": {"input": {"type": "object", "properties": {}}}}},
            )
        if path.endswith("/acts/owner~actor") or "owner" in path and path.endswith("actor"):
            return httpx.Response(
                200,
                json={"data": {"id": "abc", "name": "actor", "username": "owner"}},
            )
        if path.endswith("/actor-runs/run1"):
            return httpx.Response(
                200,
                json={"data": {"id": "run1", "status": "SUCCEEDED", "usageTotalUsd": 0.25}},
            )
        return httpx.Response(404, json={"error": {"type": "record-not-found"}})

    client = ApifyClient(token, http=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.get_actor("owner/actor")["id"] == "abc"
    client.get_default_build("abc")
    assert client.start_run(
        "abc",
        {"search": "dentists"},
        max_items=10,
        max_total_charge_usd=1.5,
    )["status"] == "READY"
    assert client.get_run("run1")["usageTotalUsd"] == 0.25
    assert client.abort_run("run1")["status"] == "ABORTING"
    items, total = client.dataset_items("run1", offset=0, limit=25)

    assert total == 3
    assert items == [{"url": "https://example.com"}]
    assert all("run-sync" not in path for _, path, _ in seen)
    start = next(item for item in seen if item[0] == "POST" and item[1].endswith("/runs"))
    assert "maxItems=10" in start[2]
    assert "maxTotalChargeUsd=1.5" in start[2]
    assert "waitForFinish" not in start[2]
    assert any(path.endswith("/acts/owner~actor") or "owner~actor" in path for _, path, _ in seen)


def test_account_lists_use_the_official_actor_and_run_endpoints() -> None:
    token = "super-secret-token"
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.url.query.decode()))
        assert request.headers["Authorization"] == f"Bearer {token}"
        assert token not in str(request.url)
        if request.url.path.endswith("/actors"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "total": 1,
                        "items": [
                            {
                                "id": "AabCualFIriz3X6Fs",
                                "username": "vortex_data",
                                "name": "google-maps",
                                "title": "Google Maps Scraper",
                                "stats": {"lastRunStartedAt": "2026-10-01T10:52:42.596Z"},
                            }
                        ],
                    }
                },
            )
        if request.url.path.endswith("/actor-runs"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "total": 1,
                        "items": [
                            {
                                "id": "eUhzlIKdHNipQBF0g",
                                "actId": "AabCualFIriz3X6Fs",
                                "status": "SUCCEEDED",
                                "usageTotalUsd": 0.05,
                            }
                        ],
                    }
                },
            )
        return httpx.Response(404, json={"error": {"type": "record-not-found"}})

    client = ApifyClient(token, http=httpx.Client(transport=httpx.MockTransport(handler)))
    actors = client.list_actors()
    runs = client.list_runs(limit=50)

    assert actors[0]["id"] == "AabCualFIriz3X6Fs"
    assert runs[0]["id"] == "eUhzlIKdHNipQBF0g"
    assert seen[0][0] == "GET"
    assert seen[0][1].endswith("/actors")
    assert "sortBy=stats.lastRunStartedAt" in seen[0][2]
    assert seen[1][1].endswith("/actor-runs")
    assert "limit=50" in seen[1][2]


def test_auth_failures_do_not_echo_the_token() -> None:
    token = "super-secret-token"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"type": "token-not-found", "message": token}},
        )

    client = ApifyClient(token, http=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(AppError) as caught:
        client.get_actor("actor1")

    assert caught.value.code == "APIFY_UNAUTHORIZED"
    assert token not in caught.value.message
    assert token not in str(caught.value.details)


def test_adding_a_connector_requires_the_server_token() -> None:
    app = create_app(_settings().model_copy(update={"apify_token": ""}))

    def override_session():
        yield Mock()

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/apify/connectors",
            json={"display_name": "Local listings", "actor_id": "owner/actor"},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "APIFY_NOT_CONFIGURED"
    assert "super-secret-token" not in response.text


def test_connector_names_and_run_input_are_validated() -> None:
    app = create_app(_settings())

    def override_session():
        yield Mock()

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        missing = client.post("/api/v1/apify/connectors", json={"actor_id": "owner/actor"})
        blank = client.post(
            "/api/v1/apify/connectors",
            json={"display_name": "   ", "actor_id": "owner/actor"},
        )
        bad_limit = client.post(
            "/api/v1/apify/connectors/00000000-0000-0000-0000-000000000000/runs",
            json={"max_items": 0},
        )

    assert missing.status_code == 422
    assert blank.status_code == 422
    assert bad_limit.status_code == 422
    assert missing.json()["error"]["code"] == "VALIDATION_ERROR"
