import logging
import re
from urllib.parse import urljoin

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
SKIP_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".js",
    ".css",
    ".woff",
    ".woff2",
    ".map",
    ".ico",
    ".pdf",
)
BAD_DOMAINS = (
    "example.com",
    "sentry.io",
    "domain.com",
    "wixpress.com",
    "w3.org",
    "schema.org",
    "cloudflare.com",
    "googleapis.com",
)
SKIP_WEBSITE_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
)


STRICT_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,10}$")


def extract_clean_emails(text: str) -> list[str]:
    raw_emails = set(EMAIL_REGEX.findall(text))
    cleaned: list[str] = []
    for raw in raw_emails:
        email = raw.strip().rstrip(".,:;!?)<>'\"")
        low = email.lower()
        if any(low.endswith(ext) for ext in SKIP_EXTENSIONS):
            continue
        if "@" not in low:
            continue
        user, domain = low.split("@", 1)
        if user in ("wght", "opsz", "ital", "woff", "woff2", "font"):
            continue
        if any(bad in domain for bad in BAD_DOMAINS):
            continue
        if ".." in domain:
            continue
        if not STRICT_EMAIL_REGEX.match(low):
            continue
        if len(email) >= 6:
            cleaned.append(email)
    return cleaned


def find_business_email(
    website_url: str,
    *,
    client: httpx.Client | None = None,
    settings: Settings | None = None,
) -> str | None:
    """Attempt to extract contact email from website homepage or contact page."""
    if not website_url or not website_url.strip():
        return None
    url = website_url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    low_url = url.lower()
    if any(domain in low_url for domain in SKIP_WEBSITE_DOMAINS):
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    should_close_client = False
    active_client = client
    if active_client is None:
        active_client = httpx.Client(timeout=6.0, follow_redirects=True, headers=headers)
        should_close_client = True

    try:
        try:
            r = active_client.get(url, headers=headers, timeout=4.0)
            if r.status_code < 400:
                emails = extract_clean_emails(r.text)
                if emails:
                    return emails[0]
            for path in ("/contact", "/contact-us", "/about"):
                try:
                    c_url = urljoin(url, path)
                    r_contact = active_client.get(c_url, headers=headers, timeout=3.0)
                    if r_contact.status_code < 400:
                        emails = extract_clean_emails(r_contact.text)
                        if emails:
                            return emails[0]
                except Exception:
                    pass
        except Exception:
            pass

        if settings and settings.scrapingbee_api_key.strip():
            try:
                sb_key = settings.scrapingbee_api_key.strip()
                sb_res = active_client.get(
                    "https://app.scrapingbee.com/api/v1/",
                    params={"api_key": sb_key, "url": url, "render_js": "false"},
                    timeout=5.0,
                )
                if sb_res.status_code == 200:
                    emails = extract_clean_emails(sb_res.text)
                    if emails:
                        return emails[0]
            except Exception:
                pass
    finally:
        if should_close_client and active_client is not None:
            active_client.close()

    return None
