from html.parser import HTMLParser
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
  const h1Elements = document.querySelectorAll("h1");
  const allImages = Array.from(document.querySelectorAll("img"));
  const imagesMissingAlt = allImages.filter((img) => !img.hasAttribute("alt") || !img.alt.trim()).length;
  const viewportMeta = Boolean(document.querySelector('meta[name="viewport"]'));
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
    h1Count: h1Elements.length,
    imagesTotal: allImages.length,
    imagesMissingAlt: imagesMissingAlt,
    viewportMeta: viewportMeta,
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



class _PageHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.in_title = False
        self.meta_description = ""
        self.canonical = ""
        self.robots = ""
        self.theme_color = ""
        self.has_viewport = False
        self.h1_texts: list[str] = []
        self.in_h1 = False
        self.current_h1_parts: list[str] = []
        self.body_text_parts: list[str] = []
        self.in_body = False
        self.ignore_depth = 0
        self.link_count = 0
        self.in_nav = 0
        self.nav_link_count = 0
        self.links: list[tuple[str, str]] = []
        self.current_a_href: str | None = None
        self.current_a_parts: list[str] = []
        self.form_count = 0
        self.input_count = 0
        self.in_button = False
        self.current_button_parts: list[str] = []
        self.cta_labels: list[str] = []
        self.images_total = 0
        self.images_missing_alt = 0
        self.image_urls: list[str] = []
        self.has_tel = False
        self.outdated_markup = False
        self.schema_types: list[str] = []
        self.in_ldjson = False
        self.ldjson_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs if k}
        name = tag.lower()
        if name == "title":
            self.in_title = True
        elif name == "h1":
            self.in_h1 = True
            self.current_h1_parts = []
        elif name == "meta":
            m_name = attrs_dict.get("name", "").lower()
            m_prop = attrs_dict.get("property", "").lower()
            if m_name == "description" or m_prop == "og:description":
                if not self.meta_description:
                    self.meta_description = attrs_dict.get("content", "")
            elif m_name == "viewport":
                self.has_viewport = True
            elif m_name == "theme-color":
                self.theme_color = attrs_dict.get("content", "")
            elif m_name == "robots":
                self.robots = attrs_dict.get("content", "")
        elif name == "link":
            rel = attrs_dict.get("rel", "").lower()
            if rel == "canonical":
                self.canonical = attrs_dict.get("href", "")
        elif name == "a":
            self.link_count += 1
            if self.in_nav > 0:
                self.nav_link_count += 1
            href = attrs_dict.get("href", "")
            if href.lower().startswith("tel:"):
                self.has_tel = True
            self.current_a_href = href
            self.current_a_parts = []
        elif name == "nav":
            self.in_nav += 1
        elif name == "form":
            self.form_count += 1
        elif name in ("input", "textarea", "select"):
            self.input_count += 1
        elif name == "button":
            self.in_button = True
            self.current_button_parts = []
        elif name == "img":
            self.images_total += 1
            alt = (attrs_dict.get("alt") or "").strip()
            if not alt:
                self.images_missing_alt += 1
            src = (attrs_dict.get("src") or attrs_dict.get("data-src") or "").strip()
            if src and len(self.image_urls) < 12:
                from urllib.parse import urljoin
                self.image_urls.append(urljoin(self.base_url, src))
        elif name == "script":
            s_type = attrs_dict.get("type", "").lower()
            if "ld+json" in s_type:
                self.in_ldjson = True
                self.ldjson_parts = []
            self.ignore_depth += 1
        elif name in ("style", "svg", "noscript"):
            self.ignore_depth += 1
        elif name in ("marquee", "font", "frameset", "center"):
            self.outdated_markup = True
        elif name == "body":
            self.in_body = True

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_h1:
            self.current_h1_parts.append(data)
        if self.current_a_href is not None:
            self.current_a_parts.append(data)
        if self.in_button:
            self.current_button_parts.append(data)
        if self.in_ldjson:
            self.ldjson_parts.append(data)
        if self.in_body and self.ignore_depth == 0:
            self.body_text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name == "title":
            self.in_title = False
        elif name == "h1":
            self.in_h1 = False
            txt = " ".join("".join(self.current_h1_parts).split())
            if txt:
                self.h1_texts.append(txt)
        elif name == "a":
            if self.current_a_href is not None:
                txt = " ".join("".join(self.current_a_parts).split())
                if len(self.links) < 80:
                    from urllib.parse import urljoin
                    self.links.append((urljoin(self.base_url, self.current_a_href), txt[:80]))
                if txt and len(txt) < 80:
                    self.cta_labels.append(txt)
                self.current_a_href = None
        elif name == "nav":
            self.in_nav = max(0, self.in_nav - 1)
        elif name == "button":
            self.in_button = False
            txt = " ".join("".join(self.current_button_parts).split())
            if txt and len(txt) < 80:
                self.cta_labels.append(txt)
        elif name == "script":
            if self.in_ldjson:
                self.in_ldjson = False
                import json
                try:
                    payload = json.loads("".join(self.ldjson_parts))
                    def extract_type(obj: Any) -> None:
                        if isinstance(obj, dict):
                            t = obj.get("@type")
                            if t and isinstance(t, str):
                                self.schema_types.append(t)
                            for v in obj.values():
                                extract_type(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                extract_type(item)
                    extract_type(payload)
                except Exception:
                    pass
            self.ignore_depth = max(0, self.ignore_depth - 1)
        elif name in ("style", "svg", "noscript"):
            self.ignore_depth = max(0, self.ignore_depth - 1)
        elif name == "body":
            self.in_body = False


def _capture_website_http(url: str) -> CapturedPage:
    import re
    import httpx

    assert_public_http_url(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    start_time = time.monotonic()
    try:
        with httpx.Client(follow_redirects=True, timeout=20.0, headers=headers) as client:
            response = client.get(url)
            final_url = str(response.url)
            assert_public_http_url(final_url)
            load_time_ms = int((time.monotonic() - start_time) * 1000)
            html = response.text
    except Exception as exc:
        logger.warning("audit_http_fallback_failed url=%s error=%s", url, exc)
        raise AuditRunError("The website could not be reached. Check the website address.") from exc

    parser = _PageHtmlParser(final_url)
    try:
        parser.feed(html)
    except Exception as parse_err:
        logger.warning("audit_html_parse_error: %s", parse_err)

    title = " ".join("".join(parser.title_parts).split())
    body_text = " ".join("".join(parser.body_text_parts).split())[:8000]
    h1 = parser.h1_texts[0] if parser.h1_texts else ""
    phone = parser.has_tel or bool(re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", body_text))

    return CapturedPage(
        final_url=final_url,
        title=title,
        meta_description=parser.meta_description,
        h1=h1,
        h1_count=len(parser.h1_texts),
        text=body_text,
        link_count=parser.link_count,
        nav_link_count=parser.nav_link_count,
        form_count=parser.form_count,
        input_count=parser.input_count,
        cta_labels=parser.cta_labels[:40],
        image_urls=parser.image_urls,
        phone_visible=phone,
        background_color="#ffffff",
        text_color="#111827",
        font_family="system-ui, sans-serif",
        heading_font="system-ui, sans-serif",
        theme_color=parser.theme_color,
        horizontal_overflow=False,
        outdated_markup=parser.outdated_markup,
        load_time_ms=load_time_ms,
        images_total=parser.images_total,
        images_missing_alt=parser.images_missing_alt,
        has_viewport_meta=parser.has_viewport,
        schema_types=parser.schema_types,
        canonical_url=parser.canonical,
        robots_meta=parser.robots,
        links=parser.links,
        desktop_png=b"",
        mobile_png=b"",
    )


def _capture_website_isolated(url: str) -> CapturedPage:
    with _browser_lock:
        try:
            return asyncio.run(_capture_website(url))
        except Exception as exc:
            logger.warning("audit_browser_failed_fallback url=%s error=%s", url, exc)
            return _capture_website_http(url)


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
        except ServerlessBrowserError as exc:
            logger.exception("audit_serverless_browser_failed")
            raise _browser_start_error(exc) from None
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
                # The serverless build is chrome-headless-shell. Playwright's default
                # --headless flag makes that binary exit immediately.
                headless=False,
                args=list(SERVERLESS_ARGS),
                env=browser_environment(),
            )
        except AuditRunError:
            raise
        except Exception as exc:
            logger.exception("audit_serverless_browser_failed")
            raise _browser_start_error(exc) from None
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


def _browser_start_error(exc: BaseException) -> AuditRunError:
    detail = ""
    for line in str(exc).splitlines():
        cleaned = " ".join(line.split())
        if not cleaned or cleaned.startswith("File ") or cleaned.startswith("Traceback"):
            continue
        if "browser logs" in cleaned.lower() or cleaned.startswith("Call log"):
            continue
        detail = cleaned
    if len(detail) > 180:
        detail = detail[:180].rstrip() + "..."
    message = "The website browser could not be started."
    if detail and detail != message:
        message = f"{message} {detail}"
    return AuditRunError(message)


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
        h1_count=_count(facts.get("h1Count")) if facts.get("h1Count") is not None else (1 if facts.get("h1") else 0),
        images_total=_count(facts.get("imagesTotal")),
        images_missing_alt=_count(facts.get("imagesMissingAlt")),
        has_viewport_meta=bool(facts.get("viewportMeta", True)),
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
