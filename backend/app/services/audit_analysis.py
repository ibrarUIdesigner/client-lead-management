from dataclasses import dataclass, field

from app.services.audit_crawl import CrawlResult, crawl_issues, crawl_tool
from app.services.audit_pagespeed import PageSpeedReport


@dataclass
class CapturedPage:
    final_url: str
    title: str
    meta_description: str
    h1: str
    text: str
    link_count: int
    nav_link_count: int
    form_count: int
    input_count: int
    cta_labels: list[str]
    image_urls: list[str]
    phone_visible: bool
    background_color: str
    text_color: str
    font_family: str
    heading_font: str
    theme_color: str
    horizontal_overflow: bool
    outdated_markup: bool
    load_time_ms: int
    lcp_ms: int = 0
    schema_types: list[str] = field(default_factory=list)
    schema_checked: bool = False
    accessibility_violations: list[dict[str, object]] = field(default_factory=list)
    accessibility_checked: bool = False
    canonical_url: str = ""
    robots_meta: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)
    index_checked: bool = False
    desktop_png: bytes = field(default=b"", repr=False)
    mobile_png: bytes = field(default=b"", repr=False)


@dataclass
class AuditAnalysis:
    performance_score: int
    design_score: int
    mobile_score: int
    ux_score: int
    seo_score: int
    overall_score: int
    opportunity_score: int
    has_ssl: bool
    is_mobile_responsive: bool
    has_clear_cta: bool
    has_contact_form: bool
    has_social_proof: bool
    has_modern_navigation: bool
    issues: list[dict[str, object]]
    recommendations: list[dict[str, object]]
    opportunity_breakdown: list[dict[str, object]]
    brand: dict[str, object]
    title: str
    final_url: str
    tools: list[dict[str, str]] = field(default_factory=list)
    report: list[dict[str, str]] = field(default_factory=list)
    pages: list[dict[str, str]] = field(default_factory=list)
    field_data: dict[str, str] | None = None


CTA_WORDS = (
    "contact",
    "get started",
    "book",
    "call",
    "quote",
    "buy",
    "shop",
    "schedule",
    "request",
    "sign up",
    "learn more",
)
SOCIAL_WORDS = ("testimonial", "review", "clients", "trusted by", "stars")


def analyze_page(page: CapturedPage) -> AuditAnalysis:
    https = page.final_url.lower().startswith("https://")
    responsive = not page.horizontal_overflow
    cta = _has_cta(page.cta_labels)
    contact_form = page.form_count > 0 and page.input_count > 0
    social = _has_social_proof(page.text)
    navigation = page.nav_link_count >= 3
    slow = page.lcp_ms > 4000 or (page.lcp_ms <= 0 and page.load_time_ms > 4000)
    if page.lcp_ms > 4000:
        slow_detail = "The largest content took more than 4 seconds to appear."
    else:
        slow_detail = "The page took more than 4 seconds to load."
    thin = len(page.text.strip()) < 200
    missing_title = len(page.title.strip()) < 10
    missing_meta = len(page.meta_description.strip()) < 50
    missing_h1 = not page.h1.strip()

    breakdown: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    recommendations: list[dict[str, object]] = []

    def add(code: str, title: str, detail: str, recommendation: str, points: int) -> None:
        issues.append({"code": code, "title": title, "detail": detail, "url": page.final_url})
        recommendations.append(
            {"code": code, "title": recommendation, "detail": detail, "url": page.final_url}
        )
        if points:
            breakdown.append({"code": code, "label": title, "points": points})

    if not https:
        add(
            "no_https",
            "No HTTPS",
            "The page did not load over HTTPS.",
            "Serve the site over HTTPS.",
            10,
        )
    if not responsive:
        add(
            "poor_mobile",
            "Poor mobile UX",
            "The page is wider than a phone screen.",
            "Make the layout fit a phone without horizontal scrolling.",
            20,
        )
    if page.outdated_markup:
        add(
            "outdated_design",
            "Outdated design",
            "The page still uses outdated layout markup.",
            "Replace outdated layout markup with a current page structure.",
            15,
        )
    if not cta:
        add(
            "weak_cta",
            "Weak CTA",
            "No clear call to action was found.",
            "Add a clear next step, such as contact, book, or request a quote.",
            10,
        )
    if not contact_form:
        add(
            "no_contact_form",
            "No contact form",
            "No contact form was found on the page.",
            "Add a short contact form.",
            10,
        )
    if not page.phone_visible:
        add(
            "missing_phone",
            "Phone number is hard to find",
            "No phone number was visible on the homepage.",
            "Show a phone number near the top of the page.",
            5,
        )
    if slow:
        add(
            "poor_performance",
            "Poor performance",
            slow_detail,
            "Reduce how long the main content takes to appear.",
            5,
        )
    if missing_title:
        add(
            "missing_title",
            "Missing page title",
            "The page title is missing or very short.",
            "Add a page title that names the business.",
            0,
        )
    if missing_meta:
        add(
            "missing_description",
            "Missing description",
            "The page has no useful meta description.",
            "Add a short description of the business.",
            0,
        )
    if missing_h1:
        add(
            "missing_heading",
            "Missing heading",
            "The page has no main heading.",
            "Add one clear heading at the top of the page.",
            0,
        )
    if thin:
        add(
            "thin_content",
            "Thin content",
            "The page has very little text.",
            "Explain what the business does in plain language.",
            0,
        )
    if not navigation:
        add(
            "weak_navigation",
            "Weak navigation",
            "The page has little navigation.",
            "Add navigation to the main pages.",
            0,
        )
    if page.index_checked and "noindex" in page.robots_meta.lower():
        add(
            "noindex",
            "Hidden from search",
            "The page asks search engines not to index it.",
            "Allow this page to be indexed.",
            10,
        )
    if page.index_checked and not page.canonical_url.strip():
        add(
            "missing_canonical",
            "Missing canonical URL",
            "The homepage does not declare a canonical URL.",
            "Add a canonical link to the preferred homepage address.",
            0,
        )
    if page.index_checked and not social:
        add(
            "no_social_proof",
            "No visible reviews",
            "The homepage does not mention reviews or project examples.",
            "Add a short review or example of the work.",
            0,
        )
    if page.schema_checked and not _has_business_schema(page.schema_types):
        add(
            "missing_schema",
            "No business schema",
            "The page has no LocalBusiness or Organization structured data.",
            "Add schema markup so search engines can understand the business.",
            5,
        )
    accessibility = (
        _accessibility_finding(page.accessibility_violations)
        if page.accessibility_checked
        else None
    )
    if accessibility is not None:
        detail, recommendation, points = accessibility
        add("accessibility", "Accessibility problems", detail, recommendation, points)

    opportunity = min(100, sum(int(item["points"]) for item in breakdown))
    performance = (
        _lcp_score(page.lcp_ms) if page.lcp_ms > 0 else _performance_score(page.load_time_ms)
    )
    mobile = 100 if responsive else 30
    design = 40 if page.outdated_markup else 85
    ux_parts = [100 if cta else 30, 100 if contact_form else 30, 100 if navigation else 40]
    ux = round(sum(ux_parts) / len(ux_parts))
    seo_parts = [not missing_title, not missing_meta, not missing_h1, https]
    seo = round(100 * sum(1 for item in seo_parts if item) / len(seo_parts))
    overall = round((performance + mobile + design + ux + seo) / 5)

    analysis = AuditAnalysis(
        performance_score=performance,
        design_score=design,
        mobile_score=mobile,
        ux_score=ux,
        seo_score=seo,
        overall_score=overall,
        opportunity_score=opportunity,
        has_ssl=https,
        is_mobile_responsive=responsive,
        has_clear_cta=cta,
        has_contact_form=contact_form,
        has_social_proof=social,
        has_modern_navigation=navigation,
        issues=issues,
        recommendations=recommendations,
        opportunity_breakdown=breakdown,
        brand=_brand(page),
        title=page.title.strip(),
        final_url=page.final_url,
        tools=_tools(page),
        pages=(
            [{"role": "Homepage", "url": page.final_url, "title": page.title.strip()}]
            if page.final_url
            else []
        ),
    )
    analysis.report = build_report(analysis)
    return analysis


def analyze_missing_website() -> AuditAnalysis:
    issue = {
        "code": "missing_website",
        "title": "Missing website",
        "detail": "This business has no website address.",
    }
    analysis = AuditAnalysis(
        performance_score=0,
        design_score=0,
        mobile_score=0,
        ux_score=0,
        seo_score=0,
        overall_score=0,
        opportunity_score=30,
        has_ssl=False,
        is_mobile_responsive=False,
        has_clear_cta=False,
        has_contact_form=False,
        has_social_proof=False,
        has_modern_navigation=False,
        issues=[issue],
        recommendations=[
            {
                "code": "missing_website",
                "title": "Offer a simple website",
                "detail": "This business has no website address.",
            }
        ],
        opportunity_breakdown=[
            {"code": "missing_website", "label": "Missing website", "points": 30}
        ],
        brand={},
        title="",
        final_url="",
    )
    analysis.report = build_report(analysis)
    return analysis


def apply_pagespeed(analysis: AuditAnalysis, report: PageSpeedReport) -> None:
    if report.performance is not None:
        analysis.performance_score = report.performance
        _replace_performance_issue(analysis, report)
    if report.seo is not None:
        analysis.seo_score = report.seo
    analysis.overall_score = round(
        (
            analysis.performance_score
            + analysis.mobile_score
            + analysis.design_score
            + analysis.ux_score
            + analysis.seo_score
        )
        / 5
    )
    analysis.opportunity_score = min(
        100, sum(int(item["points"]) for item in analysis.opportunity_breakdown)
    )
    speed: list[str] = []
    if report.mobile_performance is not None:
        speed.append(f"mobile {report.mobile_performance}")
    if report.desktop_performance is not None:
        speed.append(f"desktop {report.desktop_performance}")
    if not speed and report.performance is not None:
        speed.append(f"mobile {report.performance}")
    detail = "Lighthouse " + " and ".join(speed) if speed else "Lighthouse results from Google."
    if report.seo is not None:
        detail += f", SEO {report.seo}."
    elif speed:
        detail += "."
    if report.note:
        detail += f" {report.note}"
    analysis.tools.append({"name": "PageSpeed Insights", "status": "used", "detail": detail})
    analysis.report = build_report(analysis)


def apply_crawl(analysis: AuditAnalysis, result: CrawlResult) -> None:
    for item in crawl_issues(result):
        code = str(item["code"])
        title = str(item["title"])
        detail = str(item["detail"])
        url = str(item["url"])
        points = item["points"] if isinstance(item["points"], int) else 0
        analysis.issues.append({"code": code, "title": title, "detail": detail, "url": url})
        analysis.recommendations.append(
            {
                "code": code,
                "title": str(item["recommendation"]),
                "detail": detail,
                "url": url,
            }
        )
        if points:
            analysis.opportunity_breakdown.append({"code": code, "label": title, "points": points})
    for page in result.pages:
        analysis.pages.append({"role": page.role, "url": page.url, "title": page.title})
    analysis.opportunity_score = min(
        100, sum(int(item["points"]) for item in analysis.opportunity_breakdown)
    )
    analysis.tools.append(crawl_tool(result))
    analysis.report = build_report(analysis)


def build_report(analysis: AuditAnalysis) -> list[dict[str, str]]:
    points = {
        str(item.get("code")): int(item["points"])
        for item in analysis.opportunity_breakdown
        if isinstance(item.get("points"), int)
    }
    fixes = {
        str(item.get("code")): str(item.get("title") or "") for item in analysis.recommendations
    }
    ranked = sorted(
        analysis.issues,
        key=lambda issue: (
            -points.get(str(issue.get("code")), 0),
            _REPORT_ORDER.get(str(issue.get("code")), 80),
        ),
    )
    report: list[dict[str, str]] = []
    for issue in ranked[:5]:
        code = str(issue.get("code") or "")
        url = issue.get("url") or analysis.final_url
        report.append(
            {
                "code": code,
                "title": str(issue.get("title") or ""),
                "detail": str(issue.get("detail") or ""),
                "fix": fixes.get(code, ""),
                "url": str(url or ""),
            }
        )
    return report


_REPORT_ORDER = {
    "poor_mobile": 0,
    "blocked_by_robots": 1,
    "no_https": 2,
    "broken_page": 3,
    "broken_links": 4,
    "accessibility": 5,
    "outdated_design": 6,
    "noindex": 7,
    "weak_cta": 8,
    "no_contact_form": 9,
    "missing_phone": 10,
    "poor_performance": 11,
    "missing_schema": 12,
}


def _replace_performance_issue(analysis: AuditAnalysis, report: PageSpeedReport) -> None:
    _drop_code(analysis, "poor_performance")
    if report.performance is None or report.performance >= 50:
        return
    detail = "Google Lighthouse scored mobile performance below 50."
    if report.findings:
        detail = report.findings[0][2]
    analysis.issues.append(
        {
            "code": "poor_performance",
            "title": "Poor performance",
            "detail": detail,
            "url": analysis.final_url,
        }
    )
    analysis.recommendations.append(
        {
            "code": "poor_performance",
            "title": "Reduce how long the main content takes to appear.",
            "detail": detail,
        }
    )
    analysis.opportunity_breakdown.append(
        {"code": "poor_performance", "label": "Poor performance", "points": 5}
    )
    for code, title, finding_detail in report.findings[1:3]:
        issue_code = f"psi_{code}"
        analysis.issues.append(
            {
                "code": issue_code,
                "title": title,
                "detail": finding_detail,
                "url": analysis.final_url,
            }
        )
        analysis.recommendations.append(
            {
                "code": issue_code,
                "title": title,
                "detail": finding_detail,
                "url": analysis.final_url,
            }
        )


def _drop_code(analysis: AuditAnalysis, code: str) -> None:
    analysis.issues = [item for item in analysis.issues if item.get("code") != code]
    analysis.recommendations = [
        item for item in analysis.recommendations if item.get("code") != code
    ]
    analysis.opportunity_breakdown = [
        item for item in analysis.opportunity_breakdown if item.get("code") != code
    ]


def _has_cta(labels: list[str]) -> bool:
    for label in labels:
        lowered = label.lower()
        if any(word in lowered for word in CTA_WORDS):
            return True
    return False


def _has_social_proof(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in SOCIAL_WORDS)


def _performance_score(load_time_ms: int) -> int:
    if load_time_ms < 1000:
        return 100
    if load_time_ms < 3000:
        return 70
    if load_time_ms <= 4000:
        return 50
    if load_time_ms < 6000:
        return 40
    return 20


def _lcp_score(lcp_ms: int) -> int:
    if lcp_ms < 2500:
        return 100
    if lcp_ms < 4000:
        return 60
    if lcp_ms < 6000:
        return 40
    return 20


_GENERIC_SCHEMA = frozenset(
    {
        "website",
        "webpage",
        "breadcrumblist",
        "imageobject",
        "searchaction",
        "sitenavigationelement",
        "entrypoint",
        "propertyvalue",
        "listitem",
        "itemlist",
        "speakablespecification",
    }
)
_SERIOUS_IMPACT = {"critical", "serious"}
_IMPACT_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}


def _has_business_schema(types: list[str]) -> bool:
    for name in types:
        cleaned = name.split("/")[-1].strip().lower()
        if cleaned and cleaned not in _GENERIC_SCHEMA:
            return True
    return False


def _accessibility_finding(
    violations: list[dict[str, object]],
) -> tuple[str, str, int] | None:
    ranked: list[tuple[int, str, str]] = []
    for item in violations:
        impact = item.get("impact")
        help_text = item.get("help")
        if not isinstance(impact, str) or not isinstance(help_text, str):
            continue
        impact_name = impact.strip().lower()
        help_text = help_text.strip()
        if not help_text or impact_name not in _IMPACT_ORDER:
            continue
        ranked.append((_IMPACT_ORDER[impact_name], impact_name, help_text))
    ranked.sort(key=lambda item: item[0])
    serious = [item for item in ranked if item[1] in _SERIOUS_IMPACT]
    chosen = serious[:3] or [item for item in ranked if item[1] == "moderate"][:2]
    if not chosen:
        return None
    unique: list[str] = []
    for _, _, help_text in chosen:
        if help_text not in unique:
            unique.append(help_text)
    detail = "; ".join(unique)
    if len(detail) > 280:
        detail = detail[:277] + "..."
    recommendation = (
        unique[0]
        if len(unique) == 1
        else "Fix the accessibility problems, starting with labels and contrast."
    )
    return detail, recommendation, 10 if serious else 0


def _tools(page: CapturedPage) -> list[dict[str, str]]:
    tools = [
        {
            "name": "Playwright",
            "status": "used",
            "detail": "Screenshots, mobile layout, and page structure",
        }
    ]
    if page.accessibility_checked:
        tools.append(
            {
                "name": "axe-core",
                "status": "used",
                "detail": "Labels, contrast, and other accessibility checks",
            }
        )
    else:
        tools.append(
            {
                "name": "axe-core",
                "status": "skipped",
                "detail": "The accessibility library was not available for this run.",
            }
        )
    if page.schema_checked:
        tools.append(
            {
                "name": "Structured data",
                "status": "used",
                "detail": "Schema markup for rich results",
            }
        )
    return tools


def _brand(page: CapturedPage) -> dict[str, object]:
    description = page.meta_description.strip() or page.text.strip()[:280]
    images = [url for url in page.image_urls if url.startswith(("http://", "https://"))][:12]
    return {
        "primary_color": page.theme_color.strip() or page.background_color.strip() or None,
        "secondary_color": page.text_color.strip() or None,
        "font_primary": _first_font(page.font_family),
        "font_secondary": _first_font(page.heading_font),
        "brand_description": description or None,
        "logo_url": images[0] if images else None,
        "extracted_images": images,
        "extracted_content": {
            "title": page.title.strip(),
            "h1": page.h1.strip(),
            "meta_description": page.meta_description.strip(),
        },
    }


def _first_font(value: str) -> str | None:
    font = value.split(",", maxsplit=1)[0].strip().strip("\"'")
    return font or None
