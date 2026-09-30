from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.services.audit_analysis import CapturedPage, analyze_missing_website, analyze_page
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
    assert analysis.opportunity_score == 70
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
