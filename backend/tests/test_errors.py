from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app


def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://app:app@127.0.0.1:1/client_acquisition",
        cors_origins="http://localhost:5175,http://127.0.0.1:5175",
        log_level="WARNING",
    )
    app = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise AppError(
            code="LEAD_NOT_FOUND",
            message="Lead was not found.",
            status_code=404,
        )

    @app.get("/items")
    def items(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("secret database password")

    return TestClient(app, raise_server_exceptions=False)


def test_app_error_uses_standard_shape() -> None:
    response = _client().get("/boom")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "LEAD_NOT_FOUND",
            "message": "Lead was not found.",
            "details": {},
        }
    }


def test_unknown_route_uses_standard_shape() -> None:
    response = _client().get("/api/v1/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_validation_error_uses_standard_shape() -> None:
    response = _client().get("/items?limit=nope")

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed."
    assert body["details"]["errors"]


def test_unhandled_error_hides_internal_details() -> None:
    response = _client().get("/crash")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
    assert "secret" not in response.text


def test_app_factory_returns_fastapi() -> None:
    assert isinstance(create_app(Settings(app_env="test", log_level="WARNING")), FastAPI)
