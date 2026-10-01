import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.core.errors import AppError
from app.services.audit_analysis import CapturedPage
from app.services.serverless_chromium import (
    SERVERLESS_ARGS,
    ServerlessBrowserError,
    browser_environment,
    ensure_serverless_chromium,
    serverless_runtime,
)
from app.services.url_safety import assert_public_http_url

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
NAVIGATION_TIMEOUT_MS = 20_000
_browser_lock = threading.Lock()

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
    outdated: Boolean(document.querySelector("marquee, font, frameset, center")),
    lcp: (() => {
      const paints = performance.getEntriesByType("largest-contentful-paint");
      const last = paints.length ? paints[paints.length - 1] : null;
      return last ? Math.round(last.startTime) : 0;
    })(),
    schemaTypes: collectSchemaTypes(),
    canonical: (() => {
      const link = document.querySelector('link[rel="canonical"]');
      return link ? link.href || "" : "";
    })(),
    robots: (() => {
      const meta = document.querySelector('meta[name="robots"]');
      return meta ? meta.content || "" : "";
    })(),
    links: Array.from(document.querySelectorAll("a[href]")).slice(0, 80).map((anchor) => ({
      href: anchor.href || "",
      text: (anchor.innerText || "").trim().slice(0, 80)
    }))
  };
  function collectSchemaTypes() {
    const types = [];
    const collect = (value) => {
      if (!value || typeof value !== "object") return;
      if (Array.isArray(value)) {
        value.forEach(collect);
        return;
      }
      const schemaType = value["@type"];
      if (typeof schemaType === "string") types.push(schemaType);
      else if (Array.isArray(schemaType)) {
        schemaType.forEach((item) => {
          if (typeof item === "string") types.push(item);
        });
      }
      if (Array.isArray(value["@graph"])) value["@graph"].forEach(collect);
    };
    document.querySelectorAll('script[type="application/ld+json"]').forEach((node) => {
      try {
        collect(JSON.parse(node.textContent || ""));
      } catch (error) {
        return;
      }
    });
    return types.slice(0, 20);
  }
}"""

_AXE_PATH = Path(__file__).resolve().parents[1] / "vendor" / "axe.min.js"
_AXE_RUN = """async () => {
  if (!window.axe || !window.axe.run) {
    throw new Error("missing");
  }
  const results = await window.axe.run(document, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    resultTypes: ["violations"],
    iframes: false
  });
  return (results.violations || []).slice(0, 12).map((violation) => ({
    id: violation.id || "",
    impact: violation.impact || "",
    help: violation.help || "",
    description: violation.description || "",
    count: Array.isArray(violation.nodes) ? violation.nodes.length : 0
  }));
}"""
_axe_source: str | None = None


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
    """Capture a public website in a worker thread.

    Playwright needs subprocess support. Uvicorn on Windows can run a selector
    loop that cannot spawn processes, so the browser run uses its own loop.
    """
    assert_public_http_url(url)
    try:
        return await asyncio.to_thread(_capture_website_isolated, url)
    except AuditRunError:
        raise
    except Exception:
        logger.exception("audit_browser_failed")
        raise AuditRunError("The website could not be analyzed.") from None


def _capture_website_isolated(url: str) -> CapturedPage:
    with _browser_lock:
        return asyncio.run(_capture_website(url))


async def _capture_website(url: str) -> CapturedPage:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("audit_browser_unavailable")
        raise AuditRunError(
            "The website browser is not available. Install Playwright in the API environment."
        ) from None
    if serverless_runtime():
        # Install the browser before Playwright starts its driver, so the driver
        # inherits the library path the serverless Chromium needs.
        try:
            ensure_serverless_chromium()
        except ServerlessBrowserError:
            logger.exception("audit_serverless_browser_failed")
            raise AuditRunError("The website browser could not be started.") from None
    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright)
        try:
            return await _capture(browser, url)
        finally:
            await browser.close()


async def _launch_browser(playwright: Any) -> Any:
    """Prefer Playwright Chromium, then the system Chrome or Edge install."""
    if serverless_runtime():
        try:
            executable = ensure_serverless_chromium()
            return await playwright.chromium.launch(
                executable_path=executable,
                args=list(SERVERLESS_ARGS),
                env=browser_environment(),
            )
        except AuditRunError:
            raise
        except Exception:
            logger.exception("audit_serverless_browser_failed")
            raise AuditRunError("The website browser could not be started.") from None
    attempts: list[dict[str, object]] = [
        {},
        {"channel": "chrome"},
        {"channel": "msedge"},
    ]
    last_error: Exception | None = None
    for options in attempts:
        try:
            return await playwright.chromium.launch(headless=True, **options)
        except Exception as exc:
            last_error = exc
            label = options.get("channel", "chromium")
            logger.warning("audit_browser_launch_failed channel=%s", label)
    detail = str(last_error or "")
    if "Executable doesn't exist" in detail or "playwright install" in detail.lower():
        raise AuditRunError(
            "The website browser is not installed. Run `playwright install chromium`, "
            "or install Google Chrome / Microsoft Edge on this machine."
        ) from None
    logger.warning("audit_browser_unavailable")
    raise AuditRunError("The website browser could not be started.") from None


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
        try:
            await page.wait_for_load_state("load", timeout=8_000)
        except Exception:
            logger.info("audit_load_timeout")
        load_time_ms = int((time.perf_counter() - started) * 1000)
        facts = await page.evaluate(_PAGE_FACTS)
        violations, accessibility_checked = await _accessibility(page)
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
        lcp_ms=_count(facts.get("lcp")),
        schema_types=_labels(facts.get("schemaTypes")),
        schema_checked=True,
        accessibility_violations=violations,
        accessibility_checked=accessibility_checked,
        canonical_url=_text(facts.get("canonical"), 500),
        robots_meta=_text(facts.get("robots"), 120),
        links=_links(facts.get("links")),
        index_checked=True,
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
    if "ERR_CONNECTION" in text or "ERR_ADDRESS_UNREACHABLE" in text:
        raise AuditRunError("The website could not be reached.") from None
    if "ERR_HTTP_RESPONSE_CODE_FAILURE" in text or "net::ERR_" in text:
        raise AuditRunError("The website refused the audit browser.") from None
    logger.warning("audit_navigation_failed error=%s", text[:300])
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


async def _accessibility(page: Any) -> tuple[list[dict[str, object]], bool]:
    source = _load_axe()
    if not source:
        return [], False
    try:
        await page.evaluate("(source) => { eval(source); }", source)
        raw = await page.evaluate(_AXE_RUN)
    except Exception:
        logger.warning("audit_axe_failed")
        return [], False
    return _violations(raw), True


def _load_axe() -> str:
    global _axe_source
    if _axe_source is None:
        if _AXE_PATH.is_file():
            _axe_source = _AXE_PATH.read_text(encoding="utf-8")
        else:
            _axe_source = ""
    return _axe_source


def _violations(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    parsed: list[dict[str, object]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        impact = item.get("impact")
        help_text = item.get("help")
        if not isinstance(impact, str) or not isinstance(help_text, str):
            continue
        count = item.get("count")
        parsed.append(
            {
                "id": _text(item.get("id"), 80),
                "impact": impact.strip().lower()[:20],
                "help": help_text.strip()[:180],
                "description": _text(item.get("description"), 240),
                "count": count if isinstance(count, int) and count >= 0 else 0,
            }
        )
    return parsed


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _count(value: object) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _links(value: object) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return []
    links: list[tuple[str, str]] = []
    for item in value[:80]:
        if not isinstance(item, dict):
            continue
        href = item.get("href")
        text = item.get("text")
        if isinstance(href, str) and href.startswith(("http://", "https://")):
            links.append((href.strip()[:500], _text(text, 80)))
    return links


def _labels(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value[:40]:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip()[:300])
    return labels
