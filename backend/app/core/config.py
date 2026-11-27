import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    apollo_api_key: str = ""
    serpapi_api_key: str = ""
    scrapingbee_api_key: str = ""
    discovery_user_agent: str = "ClientAcquisitionTool/0.1 (local prospecting workspace)"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ai_email_provider: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    groq_model: str = "openai/gpt-oss-120b"
    outreach_sender_name: str = "Ibrar"
    outreach_sender_email: str = "ibraruidesigner@gmail.com"
    outreach_sender_whatsapp: str = "+923028131491"
    outreach_sender_portfolio: str = "https://ibrardevportfolio.netlify.app/"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/gmail/oauth/callback"
    gmail_frontend_redirect_url: str = "http://localhost:5175/settings"
    token_encryption_key: str = ""
    gmail_sync_enabled: bool = True
    gmail_sync_interval_minutes: int = Field(default=3, ge=1, le=60)
    gmail_api_max_retries: int = Field(default=4, ge=1, le=10)
    apify_token: str = ""
    apify_api_base: str = "https://api.apify.com/v2"
    design_md_max_bytes: int = Field(default=262_144, ge=1_024, le=5_000_000)
    postgres_url: str = ""

    # Public base URL of the deployed app. Used for links sent to prospects.
    public_base_url: str = ""

    # Outreach safety: daily send cap, postal address for the email footer, and
    # the per-country sending policy (JSON object {"DE": "manual", ...}).
    outreach_daily_send_cap: int = Field(default=20, ge=0, le=500)
    outreach_postal_address: str = ""
    outreach_country_policy: str = ""
    # Automatic sends only happen inside this window (weekdays, local hours).
    outreach_timezone: str = "UTC"
    outreach_send_start_hour: int = Field(default=9, ge=0, le=23)
    outreach_send_end_hour: int = Field(default=17, ge=1, le=24)
    # Follow-ups per day (also counted in the daily send cap).
    followup_daily_limit: int = Field(default=10, ge=0, le=200)

    # Pipeline automation budgets (heavy steps per UTC day) and shared tick secret.
    pipeline_enabled: bool = True
    pipeline_min_score: int = Field(default=40, ge=0, le=100)
    pipeline_daily_audits: int = Field(default=25, ge=0, le=500)
    pipeline_daily_research: int = Field(default=25, ge=0, le=500)
    pipeline_daily_mockups: int = Field(default=10, ge=0, le=200)
    pipeline_daily_drafts: int = Field(default=30, ge=0, le=500)

    # Lead Research Providers (Tavily & Exa)
    tavily_api_key: str = ""
    exa_api_key: str = ""

    # AI Website Mockup Generation Tools
    stitch_api_key: str = ""
    banani_api_key: str = ""
    magicpath_url: str = "https://api.magicpath.ai/mcp"

    # Stock Image Providers for Mockups (Unsplash & Pixabay)
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""
    pixabay_api_key: str = ""

    # Web Push / VAPID Keys
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claims_email: str = "mailto:ibraruidesigner@gmail.com"

    # Authentication Settings
    auth_email: str = "ibraruidesigner@gmail.com"
    auth_password: str = ""
    auth_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    @model_validator(mode="after")
    def use_hosted_database(self) -> "Settings":
        url = self.database_url
        hosted = self.postgres_url.strip()
        if hosted and _is_local_database(url):
            url = hosted
        self.database_url = _normalize_database_url(url)
        if os.environ.get("VERCEL") == "1" and "STORAGE_DIR" not in os.environ:
            default_storage = (ROOT_DIR / "storage").resolve()
            if self.storage_dir.resolve() == default_storage:
                # The deployment filesystem is read-only. Screenshots go to /tmp.
                self.storage_dir = Path("/tmp/storage")
        return self

    @property
    def auth_configured(self) -> bool:
        return bool(self.auth_password.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gmail_oauth_configured(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)

    @property
    def lead_research_configured(self) -> bool:
        return bool(self.tavily_api_key.strip() or self.exa_api_key.strip())

    @property
    def vapid_configured(self) -> bool:
        return bool(self.vapid_public_key.strip() and self.vapid_private_key.strip())


def _is_local_database(url: str) -> bool:
    return "127.0.0.1" in url or "localhost" in url


def _normalize_database_url(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://"):
        cleaned = "postgresql+psycopg://" + cleaned[len("postgresql://") :]
    return cleaned


@lru_cache
def get_settings() -> Settings:
    return Settings()
