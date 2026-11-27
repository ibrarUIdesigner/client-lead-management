from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _secured_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "development",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/client_acquisition",
        "postgres_url": "",
        "storage_dir": "/tmp/storage",
        "log_level": "WARNING",
        "auth_enabled": True,
        "auth_email": "owner@example.com",
        "auth_password": "correct horse battery",
        "token_encryption_key": "",
        "discovery_enabled": False,
        "gmail_sync_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_protected_routes_reject_requests_without_a_session() -> None:
    with TestClient(create_app(_secured_settings()), raise_server_exceptions=False) as client:
        for path in ("/api/v1/leads", "/api/v1/mockups", "/api/v1/pipeline/status"):
            response = client.get(path)
            assert response.status_code == 401, path
            assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_public_routes_stay_open() -> None:
    with TestClient(create_app(_secured_settings()), raise_server_exceptions=False) as client:
        assert client.get("/api/v1/health").status_code == 200
        # Unknown token: 404 from the route itself, not 401 from the middleware.
        assert client.get("/api/v1/m/not-a-real-token-value").status_code != 401
        # Cron routes check their own secret.
        assert client.get("/api/v1/jobs/tick").status_code == 401


def test_login_sets_session_cookie_and_unlocks_the_api() -> None:
    with TestClient(create_app(_secured_settings()), raise_server_exceptions=False) as client:
        bad = client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "nope"}
        )
        assert bad.status_code == 401

        ok = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "correct horse battery"},
        )
        assert ok.status_code == 200
        token = ok.json()["access_token"]
        assert "clm_token" in ok.headers["set-cookie"]
        assert "HttpOnly" in ok.headers["set-cookie"]

        with_bearer = client.get(
            "/api/v1/pipeline/status", headers={"Authorization": f"Bearer {token}"}
        )
        assert with_bearer.status_code != 401


def test_login_is_disabled_until_a_password_is_configured() -> None:
    settings = _secured_settings(auth_password="")
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": ""}
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"
