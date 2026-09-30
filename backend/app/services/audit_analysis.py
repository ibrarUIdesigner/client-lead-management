from dataclasses import dataclass, field


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
    slow = page.load_time_ms > 4000
    thin = len(page.text.strip()) < 200
    missing_title = len(page.title.strip()) < 10
    missing_meta = len(page.meta_description.strip()) < 50
    missing_h1 = not page.h1.strip()

    breakdown: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    recommendations: list[dict[str, object]] = []

    def add(code: str, title: str, detail: str, recommendation: str, points: int) -> None:
        issues.append({"code": code, "title": title, "detail": detail})
        recommendations.append({"code": code, "title": recommendation, "detail": detail})
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
    if slow:
        add(
            "poor_performance",
            "Poor performance",
            "The page took more than 4 seconds to load.",
            "Reduce how long the page takes to become readable.",
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

    opportunity = min(100, sum(int(item["points"]) for item in breakdown))
    performance = _performance_score(page.load_time_ms)
    mobile = 100 if responsive else 30
    design = 40 if page.outdated_markup else 85
    ux_parts = [100 if cta else 30, 100 if contact_form else 30, 100 if navigation else 40]
    ux = round(sum(ux_parts) / len(ux_parts))
    seo_parts = [not missing_title, not missing_meta, not missing_h1, https]
    seo = round(100 * sum(1 for item in seo_parts if item) / len(seo_parts))
    overall = round((performance + mobile + design + ux + seo) / 5)

    return AuditAnalysis(
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
    )


def analyze_missing_website() -> AuditAnalysis:
    issue = {
        "code": "missing_website",
        "title": "Missing website",
        "detail": "This business has no website address.",
    }
    return AuditAnalysis(
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
