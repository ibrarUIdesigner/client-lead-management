import asyncio
import logging
from dataclasses import dataclass, field

import httpx

from app.core.errors import AppError
from app.services.url_safety import assert_public_http_url

logger = logging.getLogger(__name__)

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
_PSI_AUDITS = (
    "first-contentful-paint",
    "largest-contentful-paint",
    "server-response-time",
    "total-blocking-time",
    "cumulative-layout-shift",
    "render-blocking-resources",
    "render-blocking-insight",
    "uses-optimized-images",
    "image-delivery-insight",
    "modern-image-formats",
    "unminified-javascript",
    "minify-javascript",
    "unminified-css",
    "minify-css",
    "viewport",
    "viewport-insight",
)


@dataclass
class PageSpeedReport:
    performance: int | None
    seo: int | None
    accessibility: int | None
    findings: list[tuple[str, str, str]] = field(default_factory=list)
    mobile_performance: int | None = None
    desktop_performance: int | None = None
    fcp: str | None = None
    lcp: str | None = None
    server_response_time: str | None = None
    has_viewport: bool | None = None
    note: str = ""


@dataclass
class PageSpeedOutcome:
    status: str
    report: PageSpeedReport | None = None


def parse_pagespeed(payload: object) -> PageSpeedReport | None:
    if not isinstance(payload, dict):
        return None
    lighthouse = payload.get("lighthouseResult")
    if not isinstance(lighthouse, dict):
        return None
    categories = lighthouse.get("categories")
    audits = lighthouse.get("audits")
    if not isinstance(categories, dict):
        categories = {}
    if not isinstance(audits, dict):
        audits = {}

    fcp = _display_value(audits, "first-contentful-paint")
    lcp = _display_value(audits, "largest-contentful-paint")
    server_time = _display_value(audits, "server-response-time")

    vp_audit = audits.get("viewport") or audits.get("viewport-insight")
    has_viewport = None
    if isinstance(vp_audit, dict):
        vp_score = vp_audit.get("score")
        if isinstance(vp_score, (int, float)) and not isinstance(vp_score, bool):
            has_viewport = vp_score >= 0.9

    report = PageSpeedReport(
        performance=_category_score(categories, "performance"),
        seo=_category_score(categories, "seo"),
        accessibility=_category_score(categories, "accessibility"),
        findings=_findings(audits),
        fcp=fcp,
        lcp=lcp,
        server_response_time=server_time,
        has_viewport=has_viewport,
    )
    if report.performance is None and report.seo is None:
        return None
    return report


def pagespeed_tool(status: str) -> dict[str, str]:
    if status == "skipped":
        return {
            "name": "PageSpeed Insights",
            "status": "skipped",
            "detail": "Set GOOGLE_PAGESPEED_API_KEY to add Lighthouse performance and SEO scores.",
        }
    return {
        "name": "PageSpeed Insights",
        "status": "failed",
        "detail": "Lighthouse did not respond. Performance uses the page load time instead.",
    }


def choose_confirmed_score(first: int | None, second: int | None) -> int | None:
    if first is None:
        return second
    if first >= 50 or second is None:
        return first
    return second


async def fetch_pagespeed(url: str, api_key: str) -> PageSpeedOutcome:
    if not api_key.strip():
        return PageSpeedOutcome(status="skipped")
    try:
        assert_public_http_url(url)
    except AppError:
        logger.warning("pagespeed_url_blocked")
        return PageSpeedOutcome(status="failed")
    key = api_key.strip()
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            mobile, desktop = await asyncio.gather(
                _strategy(client, url, key, "mobile"),
                _strategy(client, url, key, "desktop"),
            )
            mobile, desktop, note = await _confirm_poor(client, url, key, mobile, desktop)
    except httpx.HTTPError:
        logger.warning("pagespeed_failed")
        return PageSpeedOutcome(status="failed")
    report = _combine(mobile, desktop, note)
    if report is None:
        return PageSpeedOutcome(status="failed")
    return PageSpeedOutcome(status="ok", report=report)


async def _strategy(
    client: httpx.AsyncClient, url: str, api_key: str, strategy: str
) -> PageSpeedReport | None:
    params = [
        ("url", url),
        ("strategy", strategy),
        ("category", "performance"),
        ("category", "seo"),
        ("category", "accessibility"),
        ("key", api_key),
    ]
    response = await client.get(PSI_URL, params=params)
    if response.status_code != 200:
        logger.warning("pagespeed_failed status=%s strategy=%s", response.status_code, strategy)
        return None
    try:
        payload = response.json()
    except ValueError:
        logger.warning("pagespeed_failed strategy=%s", strategy)
        return None
    return parse_pagespeed(payload)


async def _confirm_poor(
    client: httpx.AsyncClient,
    url: str,
    api_key: str,
    mobile: PageSpeedReport | None,
    desktop: PageSpeedReport | None,
) -> tuple[PageSpeedReport | None, PageSpeedReport | None, str]:
    options: list[tuple[str, int]] = []
    if mobile is not None and mobile.performance is not None and mobile.performance < 50:
        options.append(("mobile", mobile.performance))
    if desktop is not None and desktop.performance is not None and desktop.performance < 50:
        options.append(("desktop", desktop.performance))
    if not options:
        return mobile, desktop, ""
    strategy = min(options, key=lambda item: item[1])[0]
    retry = await _strategy(client, url, api_key, strategy)
    if retry is None or retry.performance is None:
        return mobile, desktop, ""
    if strategy == "mobile":
        mobile = retry
    else:
        desktop = retry
    if retry.performance >= 50:
        note = f"The first {strategy} speed result was unusually slow, so it was checked again."
    else:
        note = f"The slow {strategy} speed result was checked twice."
    return mobile, desktop, note


def _combine(
    mobile: PageSpeedReport | None, desktop: PageSpeedReport | None, note: str
) -> PageSpeedReport | None:
    if mobile is None and desktop is None:
        return None
    scores = [
        report.performance
        for report in (mobile, desktop)
        if report is not None and report.performance is not None
    ]
    slower = mobile if _score(mobile) <= _score(desktop) else desktop
    source = slower or mobile or desktop
    if source is None:
        return None
    seo = (
        _first_score(mobile, "seo")
        if _first_score(mobile, "seo") is not None
        else _first_score(desktop, "seo")
    )
    accessibility = _first_score(mobile, "accessibility")
    if accessibility is None:
        accessibility = _first_score(desktop, "accessibility")

    fcp = mobile.fcp if mobile and mobile.fcp else (desktop.fcp if desktop else None)
    lcp = mobile.lcp if mobile and mobile.lcp else (desktop.lcp if desktop else None)
    srt = (
        mobile.server_response_time
        if mobile and mobile.server_response_time
        else (desktop.server_response_time if desktop else None)
    )
    has_viewport = (
        mobile.has_viewport
        if mobile and mobile.has_viewport is not None
        else (desktop.has_viewport if desktop else None)
    )

    return PageSpeedReport(
        performance=min(scores) if scores else None,
        seo=seo,
        accessibility=accessibility,
        findings=list(source.findings),
        mobile_performance=None if mobile is None else mobile.performance,
        desktop_performance=None if desktop is None else desktop.performance,
        fcp=fcp,
        lcp=lcp,
        server_response_time=srt,
        has_viewport=has_viewport,
        note=note,
    )


def _score(report: PageSpeedReport | None) -> int:
    if report is None or report.performance is None:
        return 101
    return report.performance


def _first_score(report: PageSpeedReport | None, name: str) -> int | None:
    if report is None:
        return None
    value = report.seo if name == "seo" else report.accessibility
    return value


def _category_score(categories: dict[str, object], name: str) -> int | None:
    category = categories.get(name)
    if not isinstance(category, dict):
        return None
    value = category.get("score")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return max(0, min(100, round(float(value) * 100)))


def _display_value(audits: dict[str, object], name: str) -> str | None:
    audit = audits.get(name)
    if not isinstance(audit, dict):
        return None
    val = audit.get("displayValue")
    if isinstance(val, str) and val.strip():
        return val.replace("\xa0", " ").strip()
    return None


def _findings(audits: dict[str, object]) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for code in _PSI_AUDITS:
        audit = audits.get(code)
        if not isinstance(audit, dict):
            continue
        score = audit.get("score")
        title = audit.get("title")
        threshold = (
            0.5
            if code
            in {
                "first-contentful-paint",
                "largest-contentful-paint",
                "server-response-time",
                "total-blocking-time",
                "cumulative-layout-shift",
            }
            else 0.9
        )
        if isinstance(score, bool) or not isinstance(score, int | float) or score >= threshold:
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        canonical_code = code.replace("-", "_").replace("_insight", "")
        if canonical_code in seen:
            continue
        seen.add(canonical_code)
        display = audit.get("displayValue")
        detail = title.strip()
        if isinstance(display, str) and display.strip():
            cleaned_display = display.replace("\xa0", " ").strip()
            detail = f"{title.strip()} is {cleaned_display}."
        found.append((canonical_code, title.strip()[:120], detail[:240]))
    return found
