from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:5432/client_acquisition"
    cors_origins: str = "http://localhost:5175,http://127.0.0.1:5175"
    log_level: str = "INFO"
    storage_dir: Path = ROOT_DIR / "storage"
    discovery_enabled: bool = True
    discovery_hour: int = Field(default=6, ge=0, le=23)
    discovery_timezone: str = "UTC"
    google_places_api_key: str = ""
    google_pagespeed_api_key: str = ""
    yelp_api_key: str = ""
    discovery_user_agent: str = "ClientAcquisitionTool/0.1 (local prospecting workspace)"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ai_email_provider: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    groq_model: str = "llama-3.3-70b-versatile"
    outreach_sender_name: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/gmail/oauth/callback"
    gmail_frontend_redirect_url: str = "http://localhost:5175/settings"
    token_encryption_key: str = ""
    gmail_sync_enabled: bool = True
    gmail_sync_interval_minutes: int = Field(default=3, ge=1, le=60)
    gmail_api_max_retries: int = Field(default=4, ge=1, le=10)

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gmail_oauth_configured(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
