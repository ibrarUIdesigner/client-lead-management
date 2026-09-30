import asyncio
import logging
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.core.errors import AppError
from app.services.url_safety import assert_public_http_url

logger = logging.getLogger(__name__)

_SKIP_EXT = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".css",
    ".js",
)
_BROKEN = {404, 410, 500, 502, 503}
_ROLES = (
    ("Contact", ("contact", "get-in-touch", "reach-us")),
    ("About", ("about", "about-us", "our-story", "who-we-are")),
    ("Service", ("service", "services", "menu", "shop", "product", "products", "pricing")),
)
_DEFAULT_AGENT = "ClientAcquisitionTool/0.1 (local prospecting workspace)"


@dataclass
class SelectedPage:
    role: str
    url: str


@dataclass
class CrawledPage:
    role: str
    url: str
    status: int | None
    title: str = ""
    meta_description: str = ""


@dataclass
class CrawlResult:
    checked: bool
    homepage: str = ""
    pages: list[CrawledPage] = field(default_factory=list)
    broken_links: list[str] = field(default_factory=list)
    checked_links: int = 0
    blocks_all: bool = False
    robots_checked: bool = False
    has_sitemap: bool = False
    sitemap_checked: bool = False


class _HtmlFacts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.skip = 0
        self.meta_description = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip += 1
        if self.skip:
            return
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            attr = {key.lower(): value or "" for key, value in attrs}
            if attr.get("name", "").lower() == "description" and not self.meta_description:
                self.meta_description = attr.get("content", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if self.in_title and not self.skip:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(part.strip() for part in self.title_parts if part.strip())[:300]


def select_representative_pages(homepage: str, links: list[tuple[str, str]]) -> list[SelectedPage]:
    home_path = _path_key(homepage)
    chosen: dict[str, str] = {}
    for href, text in links:
        normalized = _same_site_url(homepage, href)
        if normalized is None or _path_key(normalized) == home_path:
            continue
        role = _role_for(normalized, text)
        if role and role not in chosen:
            chosen[role] = normalized
    return [SelectedPage(role, chosen[role]) for role, _words in _ROLES if role in chosen]


def robots_blocks_all(text: str) -> bool:
    in_star = False
    disallows: list[str] = []
    allows: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            in_star = value == "*"
            continue
        if not in_star:
            continue
        if key == "disallow":
            disallows.append(value)
        elif key == "allow":
            allows.append(value)
    return "/" in disallows and "/" not in allows


def sitemap_urls(text: str) -> list[str]:
    found: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.lower().startswith("sitemap:"):
            value = line.split(":", 1)[1].strip()
            if value:
                found.append(value)
    return found[:2]


def crawl_issues(result: CrawlResult) -> list[dict[str, object]]:
    if not result.checked:
        return []
    issues: list[dict[str, object]] = []
    if result.robots_checked and result.blocks_all:
        issues.append(
            _issue(
                "blocked_by_robots",
                "Blocked by robots.txt",
                "robots.txt tells search engines not to crawl the site.",
                "Allow search engines to crawl the public pages.",
                10,
                result.homepage,
            )
        )
    broken_pages = [page for page in result.pages if page.status in _BROKEN]
    if broken_pages:
        shown = ", ".join(page.url for page in broken_pages[:3])
        issues.append(
            _issue(
                "broken_page",
                "Broken page",
                f"A linked page did not load: {shown}.",
                "Fix or remove the link to that page.",
                10,
                broken_pages[0].url,
            )
        )
    untitled = [
        page for page in result.pages if page.status == 200 and len(page.title.strip()) < 10
    ]
    if untitled:
        shown = ", ".join(page.url for page in untitled[:3])
        issues.append(
            _issue(
                "page_missing_title",
                "Page missing a title",
                f"A linked page has no useful title: {shown}.",
                "Add a title that names the page and the business.",
                0,
                untitled[0].url,
            )
        )
    if result.broken_links:
        shown = ", ".join(result.broken_links[:3])
        count = len(result.broken_links)
        noun = "link" if count == 1 else "links"
        issues.append(
            _issue(
                "broken_links",
                "Broken links",
                f"{count} internal {noun} returned an error, including {shown}.",
                "Repair or remove the broken links.",
                10,
                result.broken_links[0],
            )
        )
    if result.sitemap_checked and not result.has_sitemap:
        issues.append(
            _issue(
                "missing_sitemap",
                "No sitemap",
                "No XML sitemap was found for this site.",
                "Publish a sitemap and mention it in robots.txt.",
                0,
                result.homepage,
            )
        )
    return issues


def crawl_tool(result: CrawlResult) -> dict[str, str]:
    if not result.checked:
        return {
            "name": "SEO crawler",
            "status": "failed",
            "detail": "The extra pages could not be checked. The homepage result is still saved.",
        }
    roles = ", ".join(page.role for page in result.pages) or "no extra pages"
    return {
        "name": "SEO crawler",
        "status": "used",
        "detail": (
            f"Checked {roles}. "
            f"{result.checked_links} internal links, {len(result.broken_links)} broken."
        ),
    }


async def crawl_site(
    homepage: str,
    links: list[tuple[str, str]],
    user_agent: str = "",
) -> CrawlResult:
    try:
        homepage = assert_public_http_url(homepage)
    except AppError:
        return CrawlResult(checked=False, homepage=homepage)
    selected = select_representative_pages(homepage, links)
    origin = _origin(homepage)
    headers = {"User-Agent": user_agent.strip() or _DEFAULT_AGENT}
    try:
        async with httpx.AsyncClient(
            timeout=8.0, headers=headers, follow_redirects=False
        ) as client:
            robots_status, robots_text = await _read(client, urljoin(origin, "/robots.txt"))
            candidates = sitemap_urls(robots_text) if robots_status == 200 else []
            if not candidates:
                candidates = [urljoin(origin, "/sitemap.xml")]
            sitemap_ok = False
            sitemap_checked = False
            for sitemap in candidates[:2]:
                status, body = await _read(client, sitemap)
                sitemap_checked = True
                if status == 200 and ("<url" in body.lower() or "<sitemap" in body.lower()):
                    sitemap_ok = True
                    break
            page_bodies, link_statuses = await asyncio.gather(
                asyncio.gather(*[_read(client, page.url) for page in selected]),
                asyncio.gather(
                    *[_status(client, link) for link in _link_sample(homepage, links, selected)]
                ),
            )
    except httpx.HTTPError:
        logger.warning("audit_crawl_failed")
        return CrawlResult(checked=False, homepage=homepage)
    pages: list[CrawledPage] = []
    for page, (status, body) in zip(selected, page_bodies, strict=True):
        facts = _HtmlFacts()
        if status is not None and status < 400 and body:
            try:
                facts.feed(body)
            except Exception:
                logger.info("audit_page_parse_failed")
        pages.append(
            CrawledPage(
                role=page.role,
                url=page.url,
                status=status,
                title=facts.title,
                meta_description=facts.meta_description.strip()[:500],
            )
        )
    broken = [
        link
        for link, status in zip(_link_sample(homepage, links, selected), link_statuses, strict=True)
        if status in _BROKEN
    ]
    checked_links = sum(1 for status in link_statuses if status is not None)
    return CrawlResult(
        checked=True,
        homepage=homepage,
        pages=pages,
        broken_links=broken[:5],
        checked_links=checked_links,
        blocks_all=robots_status == 200 and robots_blocks_all(robots_text),
        robots_checked=robots_status is not None,
        has_sitemap=sitemap_ok,
        sitemap_checked=sitemap_checked,
    )


def _issue(
    code: str, title: str, detail: str, recommendation: str, points: int, url: str
) -> dict[str, object]:
    return {
        "code": code,
        "title": title,
        "detail": detail,
        "recommendation": recommendation,
        "points": points,
        "url": url,
    }


def _role_for(url: str, text: str) -> str | None:
    path = urlsplit(url).path.lower()
    label = text.lower()
    for role, words in _ROLES:
        if any(word in path for word in words):
            return role
    for role, words in _ROLES:
        if any(word in label for word in words):
            return role
    return None


def _same_site_url(homepage: str, href: str) -> str | None:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    joined = urljoin(homepage, href)
    parsed = urlsplit(joined)
    home = urlsplit(homepage)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if parsed.netloc.lower() != home.netloc.lower():
        return None
    path = parsed.path or "/"
    if any(path.lower().endswith(ext) for ext in _SKIP_EXT):
        return None
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, parsed.query, ""))


def _path_key(url: str) -> str:
    path = urlsplit(url).path.rstrip("/") or "/"
    return path.lower()


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _link_sample(
    homepage: str, links: list[tuple[str, str]], selected: list[SelectedPage]
) -> list[str]:
    home_path = _path_key(homepage)
    chosen = {_path_key(page.url) for page in selected}
    sample: list[str] = []
    seen: set[str] = set()
    for href, _text in links:
        normalized = _same_site_url(homepage, href)
        if normalized is None:
            continue
        key = _path_key(normalized)
        if key == home_path or key in chosen or key in seen:
            continue
        seen.add(key)
        sample.append(normalized)
        if len(sample) == 12:
            break
    return sample


async def _read(client: httpx.AsyncClient, url: str) -> tuple[int | None, str]:
    try:
        current = assert_public_http_url(url)
    except AppError:
        return None, ""
    try:
        for _hop in range(3):
            response = await client.get(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    return response.status_code, ""
                current = assert_public_http_url(urljoin(current, location))
                continue
            text = response.text[:150_000] if response.status_code < 400 else ""
            return response.status_code, text
    except (httpx.HTTPError, AppError):
        return None, ""
    return None, ""


async def _status(client: httpx.AsyncClient, url: str) -> int | None:
    try:
        current = assert_public_http_url(url)
    except AppError:
        return None
    try:
        for _hop in range(3):
            response = await client.head(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    return response.status_code
                current = assert_public_http_url(urljoin(current, location))
                continue
            if response.status_code in {405, 501} or response.status_code in _BROKEN:
                response = await client.get(current)
            return response.status_code
    except (httpx.HTTPError, AppError):
        return None
    return None
