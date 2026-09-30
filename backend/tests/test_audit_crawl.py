from app.services.audit_analysis import analyze_page, apply_crawl
from app.services.audit_crawl import (
    CrawlResult,
    crawl_issues,
    robots_blocks_all,
    select_representative_pages,
)
from app.services.audit_crux import parse_crux
from app.services.audit_pagespeed import choose_confirmed_score
from tests.test_audit import _healthy_page


def test_selects_about_contact_and_a_service_page() -> None:
    pages = select_representative_pages(
        "https://example.com/",
        [
            ("https://example.com/", "Home"),
            ("https://example.com/about", "About us"),
            ("https://example.com/contact", "Contact"),
            ("https://example.com/menu", "Menu"),
            ("https://other.example/about", "About"),
            ("mailto:a@example.com", "Email"),
        ],
    )

    roles = {page.role: page.url for page in pages}
    assert roles["About"] == "https://example.com/about"
    assert roles["Contact"] == "https://example.com/contact"
    assert roles["Service"] == "https://example.com/menu"


def test_robots_disallow_root_blocks_the_site() -> None:
    assert robots_blocks_all("User-agent: *\nDisallow: /\n")
    assert not robots_blocks_all("User-agent: *\nDisallow: /admin\n")
    assert not robots_blocks_all("User-agent: *\nDisallow: /\nAllow: /\n")


def test_broken_links_and_a_missing_sitemap_are_reported() -> None:
    result = CrawlResult(
        checked=True,
        homepage="https://example.com/",
        broken_links=["https://example.com/old"],
        checked_links=4,
        sitemap_checked=True,
        has_sitemap=False,
    )

    codes = {str(item["code"]) for item in crawl_issues(result)}
    assert "broken_links" in codes
    assert "missing_sitemap" in codes


def test_crawl_issues_raise_the_opportunity_score() -> None:
    analysis = analyze_page(_healthy_page())
    apply_crawl(
        analysis,
        CrawlResult(
            checked=True,
            homepage="https://example.com/",
            broken_links=["https://example.com/old"],
            checked_links=2,
            sitemap_checked=True,
            has_sitemap=True,
        ),
    )

    assert analysis.opportunity_score == 10
    assert analysis.report[0]["title"] == "Broken links"
    assert analysis.report[0]["url"] == "https://example.com/old"
    assert analysis.tools[-1]["name"] == "SEO crawler"


def test_a_poor_speed_result_is_replaced_by_the_repeat() -> None:
    assert choose_confirmed_score(30, 80) == 80
    assert choose_confirmed_score(30, 40) == 40
    assert choose_confirmed_score(88, None) == 88


def test_crux_parser_reads_phone_percentiles() -> None:
    outcome = parse_crux(
        {
            "record": {
                "metrics": {
                    "largest_contentful_paint": {"percentiles": {"p75": 3200}},
                    "cumulative_layout_shift": {"percentiles": {"p75": 0.12}},
                    "interaction_to_next_paint": {"percentiles": {"p75": 180}},
                }
            }
        }
    )

    assert outcome is not None
    assert outcome.status == "used"
    assert outcome.lcp == "3.2 s"
    assert outcome.inp == "180 ms"
    assert "Real visitors on phones" in outcome.detail
