from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import datetime
import logging
import socket
import ssl
from urllib.parse import urlsplit

import httpx

from app.core.errors import AppError
from app.services.url_safety import assert_public_http_url

logger = logging.getLogger(__name__)


@dataclass
class SecurityReport:
    has_ssl: bool
    ssl_valid: bool | None = None
    ssl_expiry: str | None = None
    ssl_days_remaining: int | None = None
    ssl_issuer: str | None = None
    has_hsts: bool = False
    has_csp: bool = False
    has_x_frame_options: bool = False
    has_x_content_type_options: bool = False
    issues: list[dict[str, object]] = field(default_factory=list)
    recommendations: list[dict[str, object]] = field(default_factory=list)
    tool_detail: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "has_ssl": self.has_ssl,
            "ssl_valid": self.ssl_valid,
            "ssl_expiry": self.ssl_expiry,
            "ssl_days_remaining": self.ssl_days_remaining,
            "ssl_issuer": self.ssl_issuer,
            "has_hsts": self.has_hsts,
            "has_csp": self.has_csp,
            "has_x_frame_options": self.has_x_frame_options,
            "has_x_content_type_options": self.has_x_content_type_options,
        }

    def tool(self) -> dict[str, str]:
        return {
            "name": "Security Analyzer",
            "status": "used" if self.has_ssl else "warning",
            "detail": self.tool_detail or "Security checks completed.",
        }


def _check_tls_sync(hostname: str, port: int = 443) -> tuple[bool | None, str | None, int | None, str | None]:
    """Connect via TLS and extract peer certificate expiration and issuer."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=6) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return True, None, None, None
                not_after = cert.get("notAfter")
                expiry_str = None
                days_left = None
                if not_after:
                    try:
                        exp_dt = datetime.datetime.strptime(
                            not_after, "%b %d %H:%M:%S %Y %Z"
                        ).replace(tzinfo=datetime.timezone.utc)
                        now = datetime.datetime.now(datetime.timezone.utc)
                        expiry_str = exp_dt.strftime("%Y-%m-%d")
                        days_left = (exp_dt - now).days
                    except Exception:
                        pass
                issuer_name = None
                issuer_entries = cert.get("issuer", ())
                if issuer_entries:
                    issuer_dict = dict(item[0] for item in issuer_entries if item and len(item[0]) == 2)
                    issuer_name = issuer_dict.get("organizationName") or issuer_dict.get("commonName")
                return True, expiry_str, days_left, issuer_name
    except ssl.SSLCertVerificationError:
        return False, None, None, None
    except ssl.SSLError:
        return False, None, None, None
    except (socket.timeout, OSError) as exc:
        logger.warning("security_tls_failed hostname=%s error=%s", hostname, exc)
        return None, None, None, None


async def fetch_security(url: str) -> SecurityReport:
    """Analyze SSL certificate expiration and HTTP security headers (CSP, HSTS, X-Frame-Options)."""
    if not url or not url.lower().startswith("https://"):
        return SecurityReport(
            has_ssl=False,
            ssl_valid=False,
            tool_detail="The website is served over insecure HTTP without SSL encryption.",
        )

    try:
        assert_public_http_url(url)
    except AppError:
        return SecurityReport(
            has_ssl=False,
            ssl_valid=False,
            tool_detail="The target website address could not be verified for security audit.",
        )

    parsed = urlsplit(url)
    hostname = parsed.netloc.split(":")[0]
    port = parsed.port or 443

    # Check TLS in a background thread to prevent blocking
    tls_task = asyncio.to_thread(_check_tls_sync, hostname, port)

    # Check HTTP response security headers
    headers_task = _fetch_security_headers(url)

    (ssl_valid, ssl_expiry, ssl_days, ssl_issuer), (headers, final_url) = await asyncio.gather(
        tls_task, headers_task
    )

    has_hsts = "strict-transport-security" in headers
    has_csp = "content-security-policy" in headers
    has_x_frame = "x-frame-options" in headers
    has_nosniff = headers.get("x-content-type-options", "").lower() == "nosniff"

    issues: list[dict[str, object]] = []
    recommendations: list[dict[str, object]] = []
    target_url = final_url or url

    def add_issue(code: str, title: str, detail: str, recommendation: str, points: int) -> None:
        issues.append({"code": code, "title": title, "detail": detail, "url": target_url, "points": points})
        recommendations.append({"code": code, "title": recommendation, "detail": detail, "url": target_url})

    if ssl_valid is False:
        add_issue(
            "invalid_ssl",
            "Invalid SSL certificate",
            "The website's SSL/TLS certificate is invalid, untrusted, or has expired, causing security warnings for visitors.",
            "Install a valid, trusted SSL/TLS certificate (e.g. via Let's Encrypt or your hosting provider).",
            20,
        )
    elif ssl_days is not None and ssl_days < 0:
        add_issue(
            "ssl_expired",
            "SSL certificate expired",
            f"The SSL certificate expired on {ssl_expiry}. Browsers will block visitors from accessing the site.",
            "Renew the expired SSL certificate immediately.",
            25,
        )
    elif ssl_days is not None and ssl_days <= 21:
        add_issue(
            "ssl_expiring_soon",
            "SSL certificate expiring soon",
            f"The SSL certificate expires in {ssl_days} days on {ssl_expiry}. If not renewed, the site will show security warnings.",
            "Renew the SSL certificate before it expires to prevent service disruptions.",
            15,
        )

    if not has_hsts:
        add_issue(
            "missing_hsts",
            "Missing HSTS header",
            "The Strict-Transport-Security (HSTS) header is not configured, which leaves the site vulnerable to SSL-stripping and downgrade attacks.",
            "Configure the Strict-Transport-Security header with max-age=31536000 and includeSubDomains.",
            5,
        )

    if not has_csp:
        add_issue(
            "missing_csp",
            "Missing Content Security Policy (CSP)",
            "No Content-Security-Policy header found. A CSP prevents Cross-Site Scripting (XSS) and malicious code injection attacks.",
            "Implement a Content Security Policy (CSP) header to safeguard visitors from XSS vulnerabilities.",
            10,
        )

    if not has_x_frame and not has_csp:
        add_issue(
            "missing_clickjacking_protection",
            "Missing clickjacking protection",
            "Neither X-Frame-Options nor CSP frame-ancestors is configured, allowing malicious sites to embed this page in an iframe.",
            "Add the X-Frame-Options: SAMEORIGIN header to prevent clickjacking.",
            5,
        )

    # Build summary tool detail
    summary_parts: list[str] = []
    if ssl_valid and ssl_expiry:
        issuer_str = f" by {ssl_issuer}" if ssl_issuer else ""
        days_str = f" ({ssl_days} days left)" if ssl_days is not None else ""
        summary_parts.append(f"SSL valid until {ssl_expiry}{days_str}{issuer_str}")
    elif ssl_valid is False:
        summary_parts.append("SSL certificate is invalid or untrusted")

    header_status = []
    if has_hsts:
        header_status.append("HSTS active")
    else:
        header_status.append("HSTS missing")

    if has_csp:
        header_status.append("CSP active")
    else:
        header_status.append("CSP missing (XSS risk)")

    summary_parts.append(f"Headers: {', '.join(header_status)}.")

    return SecurityReport(
        has_ssl=ssl_valid is not False,
        ssl_valid=ssl_valid,
        ssl_expiry=ssl_expiry,
        ssl_days_remaining=ssl_days,
        ssl_issuer=ssl_issuer,
        has_hsts=has_hsts,
        has_csp=has_csp,
        has_x_frame_options=has_x_frame,
        has_x_content_type_options=has_nosniff,
        issues=issues,
        recommendations=recommendations,
        tool_detail=" ".join(summary_parts),
    )


async def _fetch_security_headers(url: str) -> tuple[dict[str, str], str]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
            response = await client.head(url)
            if response.status_code in {405, 501}:
                response = await client.get(url)
            return {k.lower(): v for k, v in response.headers.items()}, str(response.url)
    except Exception as exc:
        logger.warning("security_headers_fetch_failed url=%s error=%s", url, exc)
        return {}, url
