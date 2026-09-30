import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlsplit

from app.core.errors import AppError
from app.services.audit_analysis import CapturedPage
from app.services.url_safety import assert_public_http_url

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
NAVIGATION_TIMEOUT_MS = 20_000
_browser_lock = asyncio.Lock()

_PAGE_FACTS = """() => {
  const text = (document.body && document.body.innerText
    ? document.body.innerText
    : "").slice(0, 8000);
  const title = document.title || "";
  const meta = document.querySelector('meta[name="description"]');
  const heading = document.querySelector("h1");
  const theme = document.querySelector('meta[name="theme-color"]');
  const bodyStyle = getComputedStyle(document.body);
  const headingStyle = heading ? getComputedStyle(heading) : null;
  const labels = Array.from(document.querySelectorAll("a, button"))
    .slice(0, 40)
    .map((element) => (element.innerText || "").trim())
    .filter((label) => label.length > 0 && label.length < 80);
  const images = Array.from(document.querySelectorAll("img"))
    .slice(0, 12)
    .map((image) => image.currentSrc || image.src || "")
    .filter((src) => src.startsWith("http://") || src.startsWith("https://"));
  const phone = /(?:\\+?\\d[\\d\\s().-]{7,}\\d)/.test(text)
    || Boolean(document.querySelector('a[href^="tel:"]'));
  return {
    title,
    meta: meta ? meta.content || "" : "",
    h1: heading ? heading.innerText || "" : "",
    text,
    linkCount: document.querySelectorAll("a").length,
    navCount: document.querySelectorAll("nav a").length,
    formCount: document.querySelectorAll("form").length,
    inputCount: document.querySelectorAll("input, textarea").length,
    labels,
    images,
    phone,
    background: bodyStyle.backgroundColor || "",
    color: bodyStyle.color || "",
    font: bodyStyle.fontFamily || "",
    headingFont: headingStyle ? headingStyle.fontFamily || "" : "",
    theme: theme ? theme.content || "" : "",
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 8,
    outdated: Boolean(document.querySelector("marquee, font, frameset, center"))
  };
}"""


class AuditRunError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class _Guard:
    def __init__(self) -> None:
        self.blocked = False
        self.too_many_redirects = False

    async def handle(self, route) -> None:  # noqa: ANN001
        request = route.request
        scheme = urlsplit(request.url).scheme
        if request.resource_type != "document" and scheme in {"data", "blob", "about"}:
            await route.continue_()
            return
        if request.resource_type == "document" and _redirect_count(request) > MAX_REDIRECTS:
            self.too_many_redirects = True
            await route.abort()
            return
        try:
            assert_public_http_url(request.url)
        except AppError:
            if request.resource_type == "document":
                self.blocked = True
            await route.abort()
            return
        await route.continue_()


async def capture_website(url: str) -> CapturedPage:
    assert_public_http_url(url)
    async with _browser_lock:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("audit_browser_unavailable")
            raise AuditRunError("The website browser is not available.") from None
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(headless=True)
            except Exception:
                logger.warning("audit_browser_unavailable")
                raise AuditRunError("The website browser is not available.") from None
            try:
                return await _capture(browser, url)
            finally:
                await browser.close()


async def _capture(browser: Any, url: str) -> CapturedPage:
    guard = _Guard()
    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=False,
    )
    try:
        page = await context.new_page()
        page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
        await page.route("**/*", guard.handle)
        started = time.perf_counter()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
        except Exception as exc:
            _raise_navigation_error(guard, exc)
        _raise_if_blocked(guard)
        load_time_ms = int((time.perf_counter() - started) * 1000)
        facts = await page.evaluate(_PAGE_FACTS)
        desktop = await page.screenshot(type="png", full_page=False)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(300)
        overflow = bool(
            await page.evaluate(
                "() => document.documentElement.scrollWidth > "
                "document.documentElement.clientWidth + 8"
            )
        )
        mobile = await page.screenshot(type="png", full_page=False)
        final_url = page.url
    finally:
        await context.close()

    if not isinstance(facts, dict):
        raise AuditRunError("The website could not be analyzed.")
    return CapturedPage(
        final_url=final_url,
        title=_text(facts.get("title"), 300),
        meta_description=_text(facts.get("meta"), 500),
        h1=_text(facts.get("h1"), 300),
        text=_text(facts.get("text"), 4000),
        link_count=_count(facts.get("linkCount")),
        nav_link_count=_count(facts.get("navCount")),
        form_count=_count(facts.get("formCount")),
        input_count=_count(facts.get("inputCount")),
        cta_labels=_labels(facts.get("labels")),
        image_urls=_labels(facts.get("images")),
        phone_visible=bool(facts.get("phone")),
        background_color=_text(facts.get("background"), 80),
        text_color=_text(facts.get("color"), 80),
        font_family=_text(facts.get("font"), 120),
        heading_font=_text(facts.get("headingFont"), 120),
        theme_color=_text(facts.get("theme"), 32),
        horizontal_overflow=overflow,
        outdated_markup=bool(facts.get("outdated")),
        load_time_ms=load_time_ms,
        desktop_png=desktop,
        mobile_png=mobile,
    )


def _raise_navigation_error(guard: _Guard, exc: Exception) -> None:
    _raise_if_blocked(guard)
    text = str(exc)
    if "ERR_CERT" in text or "SSL" in text:
        raise AuditRunError("The website certificate could not be verified.") from None
    if "Timeout" in text or "timeout" in text:
        raise AuditRunError("The website took too long to respond.") from None
    if "ERR_NAME_NOT_RESOLVED" in text:
        raise AuditRunError("The website address could not be found.") from None
    logger.warning("audit_navigation_failed")
    raise AuditRunError("The website could not be analyzed.") from None


def _raise_if_blocked(guard: _Guard) -> None:
    if guard.blocked:
        raise AuditRunError("The website redirected to an address that cannot be analyzed.")
    if guard.too_many_redirects:
        raise AuditRunError("The website redirected too many times.")


def _redirect_count(request) -> int:  # noqa: ANN001
    count = 0
    current = request.redirected_from
    while current is not None and count <= MAX_REDIRECTS:
        count += 1
        current = current.redirected_from
    return count


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _count(value: object) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _labels(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value[:40]:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip()[:300])
    return labels
