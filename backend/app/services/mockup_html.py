"""Validate and sanitize generated homepage HTML for safe preview and capture."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from app.core.errors import AppError

MAX_HTML_CHARS = 400_000
_SCRIPT = re.compile(r"<script\b[^>]*>[\s\S]*?</script\s*>", re.IGNORECASE)
_STYLE_IMPORT = re.compile(r"@import\b[^;]*;", re.IGNORECASE)
_URL_IN_CSS = re.compile(r"url\(\s*(['\"]?)(https?:|//)", re.IGNORECASE)
_EVENT_ATTR = re.compile(r"\son[a-z]+\s*=\s*(['\"]).*?\1", re.IGNORECASE | re.DOTALL)
_EVENT_ATTR_UNQUOTED = re.compile(r"\son[a-z]+\s*=\s*[^\s>]+", re.IGNORECASE)
_META_REFRESH = re.compile(
    r"<meta\b[^>]*http-equiv\s*=\s*(['\"]?)refresh\1[^>]*>",
    re.IGNORECASE,
)
_BASE_TAG = re.compile(r"<base\b[^>]*>", re.IGNORECASE)
_OBJECT_EMBED = re.compile(r"</?(?:object|embed|applet|iframe|frame|frameset)\b[^>]*>", re.IGNORECASE)
_FORM_ACTION = re.compile(r"\saction\s*=\s*(['\"]).*?\1", re.IGNORECASE | re.DOTALL)
_REMOTE_SRC = re.compile(
    r"""(?P<attr>\b(?:src|href|poster|data)\s*=\s*)(?P<quote>['"])(?P<url>https?:[^'"]+|//[^'"]+)(?P=quote)""",
    re.IGNORECASE,
)
_ASSET_SRC = re.compile(
    r"""(?P<attr>\b(?:src|href|poster)\s*=\s*)(?P<quote>['"])asset:(?P<index>\d+)(?P=quote)""",
    re.IGNORECASE,
)
_REMOTE_SRCSET = re.compile(
    r"""(?P<attr>\bsrcset\s*=\s*)(?P<quote>['"])(?P<value>[^'"]+)(?P=quote)""",
    re.IGNORECASE,
)


class _StructureCheck(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.has_html = False
        self.has_body = False
        self.has_script = False
        self.external_scripts = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "html":
            self.has_html = True
        elif name == "body":
            self.has_body = True
        elif name == "script":
            self.has_script = True
            mapping = {key.lower(): value for key, value in attrs if key}
            src = mapping.get("src")
            if src and src.strip().lower().startswith(("http://", "https://", "//")):
                self.external_scripts += 1


def extract_html_document(raw: str) -> str:
    text = raw.replace("\x00", "").strip()
    if not text:
        raise AppError(
            code="MOCKUP_INVALID_HTML",
            message="The model returned empty HTML.",
            status_code=502,
        )
    fenced = re.search(r"```(?:html)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    start = re.search(r"<!doctype\s+html\b|<html\b", text, re.IGNORECASE)
    if start:
        text = text[start.start() :]
    end = re.search(r"</html\s*>", text, re.IGNORECASE)
    if end:
        text = text[: end.end()]
    return text.strip()


def sanitize_html(raw: str, *, asset_data_uris: dict[str, str] | None = None) -> str:
    html = extract_html_document(raw)
    if len(html) > MAX_HTML_CHARS:
        raise AppError(
            code="MOCKUP_INVALID_HTML",
            message="The generated page is too large to preview safely.",
            status_code=502,
        )
    html = _SCRIPT.sub("", html)
    html = _META_REFRESH.sub("", html)
    html = _BASE_TAG.sub("", html)
    html = _OBJECT_EMBED.sub("", html)
    html = _EVENT_ATTR.sub("", html)
    html = _EVENT_ATTR_UNQUOTED.sub("", html)
    html = _FORM_ACTION.sub(' action="#"', html)
    html = _STYLE_IMPORT.sub("/* omitted import */", html)
    html = _URL_IN_CSS.sub("url(data:image/gif;base64,R0lGODlhAQABAAAAACw=)", html)

    assets = asset_data_uris or {}
    indexed: list[str] = []
    for key in sorted(assets.keys()):
        if key.isdigit() or key.startswith("asset:"):
            continue
        # Prefer numeric keys if present; otherwise keep path/filename map.
    for index in range(32):
        value = assets.get(str(index)) or assets.get(f"asset:{index}")
        if isinstance(value, str):
            indexed.append(value)

    def replace_asset(match: re.Match[str]) -> str:
        attr = match.group("attr")
        quote = match.group("quote")
        index = int(match.group("index"))
        if 0 <= index < len(indexed):
            return f"{attr}{quote}{indexed[index]}{quote}"
        # Fall back to any ordered data URI values.
        values = [uri for uri in assets.values() if isinstance(uri, str) and uri.startswith("data:")]
        if 0 <= index < len(values):
            return f"{attr}{quote}{values[index]}{quote}"
        return f"{attr}{quote}{quote_safe_placeholder()}{quote}"

    html = _ASSET_SRC.sub(replace_asset, html)

    def replace_remote(match: re.Match[str]) -> str:
        attr = match.group("attr")
        quote = match.group("quote")
        url = match.group("url")
        lowered = url.lower()
        if lowered.startswith(("tel:", "mailto:", "#", "data:")):
            return match.group(0)
        if attr.lower().startswith("href"):
            return f"{attr}{quote}#{quote}"
        for key, data_uri in assets.items():
            if key and key in url:
                return f"{attr}{quote}{data_uri}{quote}"
        return f"{attr}{quote}{quote_safe_placeholder()}{quote}"

    html = _REMOTE_SRC.sub(replace_remote, html)

    def replace_srcset(match: re.Match[str]) -> str:
        return f"{match.group('attr')}{match.group('quote')}{quote_safe_placeholder()}{match.group('quote')}"

    html = _REMOTE_SRCSET.sub(replace_srcset, html)

    checker = _StructureCheck()
    try:
        checker.feed(html)
        checker.close()
    except Exception as exc:
        raise AppError(
            code="MOCKUP_INVALID_HTML",
            message="The generated HTML could not be parsed.",
            status_code=502,
        ) from exc
    if checker.has_script or checker.external_scripts:
        html = _SCRIPT.sub("", html)
    if not checker.has_html or not checker.has_body:
        raise AppError(
            code="MOCKUP_INVALID_HTML",
            message="The model did not return a complete HTML document.",
            status_code=502,
        )
    _require_designed_styles(html)
    if not html.lower().startswith("<!doctype"):
        html = "<!DOCTYPE html>\n" + html
    return html


def _require_designed_styles(html: str) -> None:
    """Reject bare wireframes that look like unstyled HTML dumps."""
    styles = re.findall(r"<style\b[^>]*>([\s\S]*?)</style\s*>", html, re.IGNORECASE)
    css = "\n".join(styles).strip()
    if len(css) < 200:
        raise AppError(
            code="MOCKUP_INVALID_HTML",
            message="The model returned an unstyled page. Retry generation.",
            status_code=502,
        )
    lowered = css.lower()
    needed = ("background", "padding", "color", "max-width", "display")
    missing = [token for token in needed if token not in lowered]
    if len(missing) >= 3:
        raise AppError(
            code="MOCKUP_INVALID_HTML",
            message="The model returned an unstyled page. Retry generation.",
            status_code=502,
        )


def quote_safe_placeholder() -> str:
    return "data:image/gif;base64,R0lGODlhAQABAAAAACw="


def preview_csp() -> str:
    return (
        "default-src 'none'; "
        "img-src data: blob:; "
        "style-src 'unsafe-inline'; "
        "font-src data:; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'; "
        "navigate-to 'none'"
    )


def wrap_for_srcdoc(html: str) -> str:
    """Inject a restrictive CSP meta tag for sandboxed iframe previews."""
    csp = preview_csp()
    meta = f'<meta http-equiv="Content-Security-Policy" content="{csp}">'
    if re.search(r"<head\b", html, re.IGNORECASE):
        return re.sub(r"<head\b([^>]*)>", rf"<head\1>{meta}", html, count=1, flags=re.IGNORECASE)
    if re.search(r"<html\b", html, re.IGNORECASE):
        return re.sub(
            r"<html\b([^>]*)>",
            rf"<html\1><head>{meta}</head>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"<!DOCTYPE html><html><head>{meta}</head><body>{html}</body></html>"
