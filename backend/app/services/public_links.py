"""Links that leave the app and are opened by prospects."""

from __future__ import annotations

import os

from app.core.config import Settings
from app.models.mockup import Mockup


def public_base_url(settings: Settings) -> str:
    configured = settings.public_base_url.strip().rstrip("/")
    if configured:
        return configured
    vercel_host = (
        os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL") or ""
    ).strip()
    if vercel_host:
        return f"https://{vercel_host}"
    return ""


def public_mockup_url(settings: Settings, mockup: Mockup | None) -> str | None:
    """Absolute, login-free link to the mockup. None when no base URL is known.

    A relative path is never returned: it would open the protected app, which a
    prospect cannot sign in to.
    """
    if mockup is None or not mockup.public_token:
        return None
    base = public_base_url(settings)
    if not base:
        return None
    return f"{base}/api/v1/m/{mockup.public_token}"
