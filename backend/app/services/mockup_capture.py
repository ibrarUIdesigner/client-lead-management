"""Capture desktop and mobile screenshots of generated mockup HTML."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_browser_lock = threading.Lock()
# Match audit desktop width so downloads are true full-width desktop frames,
# independent of the narrow preview modal in the app UI.
DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

_FORCE_FULL_WIDTH = """() => {
  const root = document.documentElement;
  const body = document.body;
  if (!root || !body) return;
  root.style.setProperty("width", "100%", "important");
  root.style.setProperty("min-width", "100%", "important");
  root.style.setProperty("max-width", "none", "important");
  body.style.setProperty("width", "100%", "important");
  body.style.setProperty("min-width", "100%", "important");
  body.style.setProperty("max-width", "none", "important");
  body.style.setProperty("margin", "0", "important");
}"""


class MockupCaptureError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def capture_mockup_html(html: str) -> tuple[bytes, bytes]:
    """Return (desktop_png, mobile_png) from isolated HTML with network blocked."""
    try:
        return await asyncio.to_thread(_capture_isolated, html)
    except MockupCaptureError:
        raise
    except Exception:
        logger.exception("mockup_capture_failed")
        raise MockupCaptureError("Screenshots could not be captured.") from None


def _capture_isolated(html: str) -> tuple[bytes, bytes]:
    with _browser_lock:
        return asyncio.run(_capture(html))


async def _capture(html: str) -> tuple[bytes, bytes]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise MockupCaptureError(
            "Playwright is not available. Install Playwright in the API environment."
        ) from exc
    from app.services.serverless_chromium import ServerlessBrowserError, ensure_serverless_chromium, serverless_runtime

    if serverless_runtime():
        try:
            ensure_serverless_chromium()
        except ServerlessBrowserError as exc:
            raise MockupCaptureError(str(exc) or "Chromium is not available.") from exc
    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright)
        try:
            desktop = await _shot(browser, html, DESKTOP)
            mobile = await _shot(browser, html, MOBILE)
            return desktop, mobile
        finally:
            await browser.close()


async def _shot(browser: Any, html: str, viewport: dict[str, int]) -> bytes:
    context = await browser.new_context(
        viewport=viewport,
        device_scale_factor=1,
        java_script_enabled=True,
    )
    page = await context.new_page()
    try:
        await page.set_viewport_size(viewport)
        await page.route("**/*", _block_remote)
        await page.set_content(html, wait_until="domcontentloaded", timeout=20_000)
        await page.set_viewport_size(viewport)
        try:
            await page.evaluate(_FORCE_FULL_WIDTH)
        except Exception:
            logger.info("mockup_capture_width_hook_skipped")
        await page.wait_for_timeout(200)
        data = await page.screenshot(
            full_page=True,
            type="png",
            animations="disabled",
            scale="css",
        )
        if not data:
            raise MockupCaptureError("Screenshots could not be captured.")
        return data
    finally:
        await context.close()


async def _block_remote(route: Any) -> None:
    request = route.request
    url = request.url
    if url.startswith(("data:", "blob:", "about:")):
        await route.continue_()
        return
    if request.resource_type == "document" and url in {"about:blank", "about:srcdoc"}:
        await route.continue_()
        return
    await route.abort()


async def _launch_browser(playwright: Any) -> Any:
    from app.services.serverless_chromium import (
        SERVERLESS_ARGS,
        browser_environment,
        ensure_serverless_chromium,
        serverless_runtime,
    )

    if serverless_runtime():
        try:
            executable = ensure_serverless_chromium()
            return await playwright.chromium.launch(
                executable_path=executable,
                headless=False,
                args=list(SERVERLESS_ARGS),
                env=browser_environment(),
            )
        except Exception as exc:
            logger.exception("mockup_serverless_browser_failed")
            raise MockupCaptureError("The screenshot browser could not be started.") from exc
    attempts: list[dict[str, object]] = [{}, {"channel": "chrome"}, {"channel": "msedge"}]
    last_error: Exception | None = None
    for options in attempts:
        try:
            return await playwright.chromium.launch(headless=True, **options)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "mockup_browser_launch_failed channel=%s",
                options.get("channel", "chromium"),
            )
    detail = str(last_error or "")
    if "Executable doesn't exist" in detail or "playwright install" in detail.lower():
        raise MockupCaptureError(
            "The screenshot browser is not installed. Run `playwright install chromium`."
        ) from None
    raise MockupCaptureError("The screenshot browser could not be started.") from None
