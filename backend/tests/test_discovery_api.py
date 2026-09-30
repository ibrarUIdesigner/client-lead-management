from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.main import create_app
from tests.test_health import _settings


def _client(session: Mock) -> TestClient:
    app = create_app(_settings())

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_a_search_needs_a_city_and_category() -> None:
    with _client(Mock()) as client:
        response = client.post("/api/v1/discovery/searches", json={"category": "dentist"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_search_must_use_at_least_one_source() -> None:
    with _client(Mock()) as client:
        response = client.post(
            "/api/v1/discovery/searches",
            json={
                "category": "dentist",
                "city": "Lahore",
                "country": "Pakistan",
                "use_openstreetmap": False,
                "use_google": False,
                "use_yelp": False,
                "use_yell": False,
                "use_businesslist": False,
                "use_epages": False,
            },
        )

    assert response.status_code == 422
