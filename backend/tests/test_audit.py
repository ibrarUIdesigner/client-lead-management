import asyncio
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.services.audit_analysis import (
    CapturedPage,
    analyze_missing_website,
    analyze_page,
    apply_pagespeed,
)
from app.services.audit_pagespeed import PageSpeedReport, fetch_pagespeed, parse_pagespeed
from app.services.audits import AuditService
from app.services.storage import resolve_storage_path, save_screenshot
from app.services.url_safety import assert_public_http_url

PUBLIC = ["93.184.216.34"]


def _public(host: str) -> list[str]:
    return PUBLIC


def test_public_https_url_is_allowed() -> None:
    normalized = assert_public_http_url("https://Example.com/pricing", resolve=_public)

    assert normalized == "https://Example.com/pricing"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/admin",
        "http://10.1.2.3/",
        "http://192.168.1.20/",
        "http://172.16.0.4/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://0.0.0.0/",
        "http://2130706433/",
        "http://0177.0.0.1/",
        "http://metadata.google.internal/",
        "http://printer.local/",
        "file:///etc/passwd",
        "http://user:secret@example.com/",
        "gopher://example.com/",
    ],
)
def test_internal_and_non_http_urls_are_blocked(url: str) -> None:
    with pytest.raises(AppError) as error:
        assert_public_http_url(url, resolve=_public)

    assert error.value.code == "URL_BLOCKED"
    assert "127" not in error.value.message
    assert "169.254" not in error.value.message


def test_hostname_that_resolves_to_a_private_address_is_blocked() -> None:
    with pytest.raises(AppError) as error:
        assert_public_http_url("https://example.com/", resolve=lambda _host: ["10.0.0.8"])

    assert error.value.code == "URL_BLOCKED"


def test_screenshot_path_cannot_escape_storage(tmp_path: Path) -> None:
    with pytest.raises(AppError) as error:
        resolve_storage_path(tmp_path, "../.env")

    assert error.value.code == "NOT_FOUND"


def test_screenshot_must_be_a_png(tmp_path: Path) -> None:
    with pytest.raises(AppError):
        save_screenshot(tmp_path, "leads/a/audits/b/desktop.png", b"<html>")


def test_stored_screenshot_is_served_when_the_file_is_gone(tmp_path: Path) -> None:
    from app.services.storage import encode_png, read_screenshot

    png = b"\x89PNG\r\n\x1a\n" + b"pixels"
    encoded = encode_png(png)

    assert encoded is not None
    loaded = read_screenshot(
        tmp_path,
        "leads/a/audits/b/desktop.png",
        {"desktop_png": encoded},
        "desktop",
    )

    assert loaded == png


def test_audit_response_omits_stored_screenshot_bytes() -> None:
    from datetime import UTC, datetime

    from app.schemas.audits import AuditRead

    audit = AuditRead.model_validate(
        {
            "id": uuid4(),
            "lead_id": uuid4(),
            "url": "https://example.com",
            "status": "COMPLETED",
            "desktop_screenshot_url": "leads/a/desktop.png",
            "performance_score": None,
            "design_score": None,
            "mobile_score": None,
            "ux_score": None,
            "seo_score": None,
            "overall_score": None,
            "has_ssl": True,
            "is_mobile_responsive": True,
            "has_clear_cta": True,
            "has_contact_form": False,
            "has_social_proof": False,
            "has_modern_navigation": True,
            "issues": [],
            "recommendations": [],
            "raw_analysis": {"title": "Cafe", "desktop_png": "abc", "mobile_png": "def"},
            "completed_at": datetime.now(UTC),
            "created_at": datetime.now(UTC),
        }
    )

    assert audit.raw_analysis == {"title": "Cafe"}
    assert audit.has_desktop_screenshot is True


def test_missing_website_scores_thirty_points() -> None:
    analysis = analyze_missing_website()

    assert analysis.opportunity_score == 30
    assert analysis.opportunity_breakdown[0]["label"] == "Missing website"


def test_weak_page_explains_the_opportunity_score() -> None:
    analysis = analyze_page(
        CapturedPage(
            final_url="http://example.com/",
            title="Cafe",
            meta_description="",
            h1="",
            text="Open daily",
            link_count=1,
            nav_link_count=0,
            form_count=0,
            input_count=0,
            cta_labels=["Home"],
            image_urls=[],
            phone_visible=False,
            background_color="rgb(255, 255, 255)",
            text_color="rgb(0, 0, 0)",
            font_family="Times New Roman",
            heading_font="",
            theme_color="",
            horizontal_overflow=True,
            outdated_markup=True,
            load_time_ms=5000,
        )
    )

    points = {str(item["code"]): int(item["points"]) for item in analysis.opportunity_breakdown}
    assert points["no_https"] == 10
    assert points["poor_mobile"] == 20
    assert points["outdated_design"] == 15
    assert points["weak_cta"] == 10
    assert points["no_contact_form"] == 10
    assert points["poor_performance"] == 5
    assert points["missing_phone"] == 5
    assert analysis.opportunity_score == 75
    assert analysis.report[0]["title"] == "Poor mobile UX"
    assert len(analysis.report) == 5
    assert analysis.has_ssl is False
    assert analysis.is_mobile_responsive is False


def test_prepare_rejects_a_private_website_before_the_job_runs(tmp_path: Path) -> None:
    session = Mock()
    lead = Mock()
    lead.id = uuid4()
    lead.website_url = "http://127.0.0.1/admin"
    lead.lead_status = "NEW"
    session.get.return_value = lead
    found = Mock()
    found.first.return_value = None
    session.scalars.return_value = found

    with pytest.raises(AppError) as error:
        AuditService(session, tmp_path).prepare(lead.id)

    assert error.value.code == "URL_BLOCKED"


def test_business_schema_and_accessibility_change_the_opportunity() -> None:
    plain = analyze_page(_healthy_page())
    flagged = analyze_page(
        _healthy_page(
            schema_checked=True,
            schema_types=["WebSite"],
            accessibility_checked=True,
            accessibility_violations=[
                {
                    "id": "color-contrast",
                    "impact": "serious",
                    "help": "Elements must have sufficient color contrast",
                    "description": "Contrast is too low.",
                    "count": 2,
                }
            ],
        )
    )

    assert all(item["code"] != "missing_schema" for item in plain.issues)
    points = {str(item["code"]): int(item["points"]) for item in flagged.opportunity_breakdown}
    assert points["missing_schema"] == 5
    assert points["accessibility"] == 10
    assert flagged.opportunity_score == plain.opportunity_score + 15
    assert "color contrast" in flagged.issues[-1]["detail"]


def test_local_business_schema_is_accepted() -> None:
    analysis = analyze_page(_healthy_page(schema_checked=True, schema_types=["LocalBusiness"]))

    assert all(item["code"] != "missing_schema" for item in analysis.issues)


def test_slow_paint_is_a_performance_issue() -> None:
    analysis = analyze_page(_healthy_page(lcp_ms=5200, load_time_ms=800))

    assert analysis.performance_score == 40
    assert any(item["code"] == "poor_performance" for item in analysis.issues)


def test_pagespeed_replaces_a_misleading_load_time() -> None:
    analysis = analyze_page(_healthy_page(load_time_ms=5000))
    apply_pagespeed(
        analysis,
        PageSpeedReport(performance=88, seo=91, accessibility=73, findings=[]),
    )

    assert analysis.performance_score == 88
    assert analysis.seo_score == 91
    assert all(item["code"] != "poor_performance" for item in analysis.issues)
    assert analysis.tools[-1]["name"] == "PageSpeed Insights"
    assert analysis.tools[-1]["status"] == "used"


def test_pagespeed_records_a_slow_lighthouse_result() -> None:
    analysis = analyze_page(_healthy_page())
    apply_pagespeed(
        analysis,
        PageSpeedReport(
            performance=32,
            seo=80,
            accessibility=70,
            findings=[
                (
                    "largest_contentful_paint",
                    "Largest Contentful Paint",
                    "Largest Contentful Paint is 6.2 s.",
                )
            ],
        ),
    )

    assert analysis.performance_score == 32
    performance = next(item for item in analysis.issues if item["code"] == "poor_performance")
    assert performance["detail"] == "Largest Contentful Paint is 6.2 s."
    assert any(item["code"] == "poor_performance" for item in analysis.opportunity_breakdown)


def test_pagespeed_parser_reads_lighthouse_scores() -> None:
    report = parse_pagespeed(
        {
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.42},
                    "seo": {"score": 0.8},
                    "accessibility": {"score": 0.71},
                },
                "audits": {
                    "largest-contentful-paint": {
                        "score": 0.2,
                        "title": "Largest Contentful Paint",
                        "displayValue": "6.2 s",
                    },
                    "cumulative-layout-shift": {"score": 1, "title": "Cumulative Layout Shift"},
                },
            }
        }
    )

    assert report is not None
    assert report.performance == 42
    assert report.seo == 80
    assert report.accessibility == 71
    assert report.findings[0][0] == "largest_contentful_paint"


def test_pagespeed_without_a_key_is_skipped() -> None:
    outcome = asyncio.run(fetch_pagespeed("https://example.com/", ""))

    assert outcome.status == "skipped"


def test_axe_library_is_packaged() -> None:
    source = (Path(__file__).resolve().parents[1] / "app" / "vendor" / "axe.min.js").read_text(
        encoding="utf-8"
    )

    assert "axe v4.10.3" in source[:80]


def _healthy_page(**overrides: object) -> CapturedPage:
    values: dict[str, object] = {
        "final_url": "https://example.com/",
        "title": "North Cafe in Lahore",
        "meta_description": "Coffee, breakfast, and catering for offices in Lahore.",
        "h1": "North Cafe",
        "text": "We serve coffee and breakfast. Clients trust our catering. " * 8,
        "link_count": 6,
        "nav_link_count": 4,
        "form_count": 1,
        "input_count": 2,
        "cta_labels": ["Contact"],
        "image_urls": [],
        "phone_visible": True,
        "background_color": "rgb(255, 255, 255)",
        "text_color": "rgb(0, 0, 0)",
        "font_family": "Inter",
        "heading_font": "Inter",
        "theme_color": "#111111",
        "horizontal_overflow": False,
        "outdated_markup": False,
        "load_time_ms": 800,
    }
    values.update(overrides)
    return CapturedPage(
        final_url=str(values["final_url"]),
        title=str(values["title"]),
        meta_description=str(values["meta_description"]),
        h1=str(values["h1"]),
        text=str(values["text"]),
        link_count=int(values["link_count"]),  # type: ignore[arg-type]
        nav_link_count=int(values["nav_link_count"]),  # type: ignore[arg-type]
        form_count=int(values["form_count"]),  # type: ignore[arg-type]
        input_count=int(values["input_count"]),  # type: ignore[arg-type]
        cta_labels=list(values["cta_labels"]),  # type: ignore[arg-type]
        image_urls=list(values["image_urls"]),  # type: ignore[arg-type]
        phone_visible=bool(values["phone_visible"]),
        background_color=str(values["background_color"]),
        text_color=str(values["text_color"]),
        font_family=str(values["font_family"]),
        heading_font=str(values["heading_font"]),
        theme_color=str(values["theme_color"]),
        horizontal_overflow=bool(values["horizontal_overflow"]),
        outdated_markup=bool(values["outdated_markup"]),
        load_time_ms=int(values["load_time_ms"]),  # type: ignore[arg-type]
        lcp_ms=int(values["lcp_ms"]) if "lcp_ms" in values else 0,  # type: ignore[arg-type]
        schema_types=list(values["schema_types"]) if "schema_types" in values else [],  # type: ignore[arg-type]
        schema_checked=bool(values["schema_checked"]) if "schema_checked" in values else False,
        accessibility_violations=(
            list(values["accessibility_violations"])  # type: ignore[arg-type]
            if "accessibility_violations" in values
            else []
        ),
        accessibility_checked=(
            bool(values["accessibility_checked"]) if "accessibility_checked" in values else False
        ),
    )
