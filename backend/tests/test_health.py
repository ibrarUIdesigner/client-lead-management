from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import check_database
from app.main import create_app


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://app:app@127.0.0.1:1/client_acquisition",
        cors_origins="http://localhost:5175,http://127.0.0.1:5175",
        log_level="WARNING",
    )


def test_health_reports_database_unavailable_without_postgres() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "client-acquisition-api"
    assert body["environment"] == "test"
    assert body["database"] == "unavailable"
    assert response.headers["x-request-id"]


def test_check_database_returns_false_when_connection_fails() -> None:
    engine = Mock()
    engine.connect.side_effect = OSError("connection refused")

    assert check_database(engine) is False


def test_cors_allows_configured_origin() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5175",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5175"


def test_cors_allows_loopback_dev_origin() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://127.0.0.1:5175",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5175"
