import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import create_db_engine
from app.models.enums import AuditStatus, LeadStatus, MockupStatus
from app.models.lead import Lead
from app.models.website_audit import WebsiteAudit
from app.schemas.design_guides import DesignGuideWrite, MockupCreate, MockupRefine, MockupRetry
from app.services.design_guides import DesignGuideService
from app.services.mockup_ai import generate_homepage_html, resolve_mockup_provider
from app.services.mockup_html import sanitize_html, wrap_for_srcdoc
from app.services.mockups import MockupService

_MIN_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/client_acquisition",
        "gemini_api_key": "test-gemini",
        "groq_api_key": "test-groq",
        "gemini_model": "gemini-3.5-flash",
        "groq_model": "llama-3.3-70b-versatile",
        "ai_email_provider": "",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _sample_html(business: str = "Northwind Cafe") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{business}</title>
  <style>
    :root {{ --ink: #0b0f19; --bg: #f8f9fb; --accent: #4f46e5; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: system-ui, sans-serif; color: var(--ink); background: var(--bg); }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 1.5rem; display: block; }}
    header {{ display: flex; justify-content: space-between; align-items: center; padding: 1rem 0; }}
    nav a {{ margin-left: 1rem; color: var(--ink); text-decoration: none; }}
    .hero {{ padding: 4rem 0; background: #e8eefc; }}
    .button {{ display: inline-block; background: var(--accent); color: #fff; padding: 0.75rem 1.1rem; text-decoration: none; border-radius: 8px; }}
    section {{ padding: 3rem 0; }}
    img {{ max-width: 120px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <strong>{business}</strong>
      <nav><a href="#services">Services</a> <a href="#contact">Contact</a></nav>
    </header>
  </div>
  <section class="hero">
    <div class="wrap">
      <h1>{business}</h1>
      <p>Coffee and lunch in Austin.</p>
      <a class="button" href="tel:5550100">Call now</a>
    </div>
  </section>
  <section id="services">
    <div class="wrap">
      <h2>Services</h2>
      <p>Coffee and lunch.</p>
    </div>
  </section>
  <section id="contact">
    <div class="wrap">
      <h2>Contact</h2>
      <p>Phone: 555-0100</p>
      <p>Email: hello@northwind.example</p>
      <form action="#"><label>Name <input name="name" /></label></form>
    </div>
  </section>
  <footer><div class="wrap"><p>{business}</p></div></footer>
</body>
</html>"""


def test_sanitize_strips_scripts_and_remote_assets() -> None:
    dirty = """<!DOCTYPE html><html><head><style>
    body { margin: 0; color: #111; background: #f7f7f5; font-family: system-ui, sans-serif; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 24px; display: block; }
    .btn { background: #1d4ed8; color: #fff; padding: 12px 18px; border-radius: 8px; }
    section { padding: 48px 0; }
    </style></head><body>
    <script>alert(1)</script>
    <img src="https://evil.example/x.png" onerror="alert(1)" />
    <a href="https://evil.example">Leave</a>
    <form action="https://evil.example/steal"><button>Go</button></form>
    </body></html>"""
    clean = sanitize_html(dirty)
    assert "<script" not in clean.lower()
    assert "onerror" not in clean.lower()
    assert "https://evil.example" not in clean
    assert 'action="#"' in clean
    preview = wrap_for_srcdoc(clean)
    assert "Content-Security-Policy" in preview


def test_unstyled_html_is_rejected() -> None:
    bare = """<!DOCTYPE html><html><body>
    <h1>Business</h1><a href="tel:1">Call</a>
    </body></html>"""
    with pytest.raises(AppError) as caught:
        sanitize_html(bare)
    assert caught.value.code == "MOCKUP_INVALID_HTML"


def test_sanitize_maps_asset_placeholders() -> None:
    html = """<!DOCTYPE html><html><head><style>
    body { margin: 0; color: #111; background: #fff; font-family: system-ui, sans-serif; }
    main { max-width: 960px; padding: 24px; display: block; }
    .hero { background: #eef2ff; padding: 48px 24px; }
    </style></head><body><img src="asset:0" alt="Logo" /></body></html>"""
    clean = sanitize_html(html, asset_data_uris={"0": "data:image/png;base64,abc"})
    assert 'src="data:image/png;base64,abc"' in clean


def test_resolve_provider_is_explicit() -> None:
    settings = _settings(gemini_api_key="", groq_api_key="test-groq")
    with pytest.raises(AppError) as caught:
        resolve_mockup_provider(settings, "gemini")
    assert caught.value.code == "AI_NOT_CONFIGURED"
    assert resolve_mockup_provider(settings, "groq") == "groq"


def test_generate_homepage_uses_mocked_gemini(tmp_path: Path) -> None:
    settings = _settings(storage_dir=tmp_path)
    html_doc = _sample_html()

    def handler(request: httpx.Request) -> httpx.Response:
        assert "generativelanguage.googleapis.com" in str(request.url)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps({"html": html_doc})}],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        html, model = generate_homepage_html(
            brief="Business: Northwind Cafe",
            settings=settings,
            provider="gemini",
            client=client,
        )
    assert "<h1>Northwind Cafe</h1>" in html
    assert "<script" not in html.lower()
    assert model.startswith("gemini")


def test_generate_homepage_uses_mocked_groq(tmp_path: Path) -> None:
    settings = _settings(storage_dir=tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.groq.com" in str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"html": _sample_html()})}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        html, model = generate_homepage_html(
            brief="Business: Northwind Cafe",
            settings=settings,
            provider="groq",
            client=client,
        )
    assert "Northwind Cafe" in html
    assert model == "llama-3.3-70b-versatile"


def test_generate_does_not_silently_switch_provider(tmp_path: Path) -> None:
    settings = _settings(storage_dir=tmp_path, groq_api_key="test-groq")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "generativelanguage.googleapis.com" in str(request.url)
        return httpx.Response(429, json={"error": {"message": "rate"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AppError) as caught:
            generate_homepage_html(
                brief="Business: Northwind Cafe",
                settings=settings,
                provider="gemini",
                client=client,
            )
    assert caught.value.code == "AI_RATE_LIMITED"


def test_full_mockup_flow_with_mocked_ai_and_screenshots(tmp_path: Path) -> None:
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    storage = tmp_path / "storage"
    service_settings = _settings(
        storage_dir=storage,
        gemini_api_key="test-gemini",
        groq_api_key="test-groq",
    )
    try:
        lead = Lead(
            business_name="Northwind Cafe",
            lead_status=LeadStatus.NEW.value,
            city="Austin",
            industry="Cafe",
            description="Coffee and lunch.",
            email="hello@northwind.example",
            phone="555-0100",
            website_url="https://northwind.example",
        )
        session.add(lead)
        session.flush()
        session.add(
            WebsiteAudit(
                lead_id=lead.id,
                url="https://northwind.example",
                status=AuditStatus.COMPLETED.value,
                design_score=40,
                raw_analysis={
                    "report": [{"title": "Weak call to action", "detail": "Checked on the homepage."}]
                },
            )
        )
        guide = DesignGuideService(session, service_settings).create_guide(
            DesignGuideWrite(
                name="Calm cafe",
                description="Soft layout",
                tags=["calm"],
                content="# Colors\n\n- Accent: #4f46e5\n",
            )
        )
        service = MockupService(session, service_settings, storage)
        created = service.create(
            MockupCreate(
                lead_id=lead.id,
                design_guide_id=guide.id,
                guide_mode="selected",
                provider="gemini",
                goal="calls",
                requirements="Make the call button obvious.",
            ),
            assets=[("logo.png", _MIN_PNG, "image/png")],
        )
        assert created.status == MockupStatus.GENERATING.value
        assert "Weak call to action" in (created.prompt or "")
        assert "asset:0" in (created.prompt or "")

        def handler(request: httpx.Request) -> httpx.Response:
            markup = _sample_html().replace(
                "</body>",
                '<img src="asset:0" alt="Logo" /></body>',
            )
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": json.dumps({"html": markup})}]
                            }
                        }
                    ]
                },
            )

        def fake_capture(html: str) -> tuple[bytes, bytes]:
            assert "Northwind Cafe" in html
            assert "script" not in html.lower() or "<script" not in html.lower()
            return _MIN_PNG, _MIN_PNG

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            asyncio.run(service.execute(created.id, client=client, capture=fake_capture))

        detail = service.detail(created.id)
        assert detail.status == MockupStatus.READY.value
        assert detail.has_html
        assert detail.has_desktop_screenshot
        assert detail.has_mobile_screenshot
        assert detail.screenshot_status == "READY"
        assert detail.provider == "gemini"
        assert detail.preview_html and "Content-Security-Policy" in detail.preview_html
        assert "data:image" in (detail.html_content or "")

        html_bytes = service.read_html(created.id).encode("utf-8")
        assert b"Northwind Cafe" in html_bytes
        desktop = service.read_screenshot(created.id, "desktop")
        assert desktop.startswith(b"\x89PNG")

        refined = service.refine(
            created.id,
            MockupRefine(instructions="Improve hero spacing.", provider="groq"),
        )
        assert refined.version == 2
        assert refined.status == MockupStatus.GENERATING.value

        def groq_handler(request: httpx.Request) -> httpx.Response:
            assert "api.groq.com" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({"html": _sample_html("Northwind Cafe Refined")})
                            }
                        }
                    ]
                },
            )

        with httpx.Client(transport=httpx.MockTransport(groq_handler)) as client:
            asyncio.run(service.execute(refined.id, client=client, capture=fake_capture))

        v2 = service.detail(refined.id)
        assert v2.status == MockupStatus.READY.value
        assert v2.version == 2
        assert "Refined" in (v2.html_content or "")
        # Original version preserved
        v1 = service.detail(created.id)
        assert v1.version == 1
        assert "Refined" not in (v1.html_content or "")

        # Screenshot failure keeps HTML
        failed_create = service.create(
            MockupCreate(
                lead_id=lead.id,
                guide_mode="none",
                provider="gemini",
                goal="quotes",
            )
        )

        def boom(_html: str) -> tuple[bytes, bytes]:
            raise AppError(code="SCREENSHOT_INVALID", message="Capture failed.", status_code=500)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            asyncio.run(service.execute(failed_create.id, client=client, capture=boom))
        failed = service.detail(failed_create.id)
        assert failed.status == MockupStatus.READY.value
        assert failed.has_html
        assert failed.screenshot_status == "FAILED"

        # Explicit retry with switch provider after failure path
        bad = service.create(
            MockupCreate(lead_id=lead.id, guide_mode="none", provider="gemini", goal="calls")
        )

        def fail_ai(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": {"message": "rate"}})

        with httpx.Client(transport=httpx.MockTransport(fail_ai)) as client:
            asyncio.run(service.execute(bad.id, client=client, capture=fake_capture))
        assert service.detail(bad.id).status == MockupStatus.FAILED.value
        assert service.detail(bad.id).error_code == "AI_RATE_LIMITED"

        retried = service.retry(bad.id, MockupRetry(provider="groq"))
        assert retried.status == MockupStatus.GENERATING.value
        assert retried.provider == "groq"
        with httpx.Client(transport=httpx.MockTransport(groq_handler)) as client:
            asyncio.run(service.execute(retried.id, client=client, capture=fake_capture))
        assert service.detail(retried.id).status == MockupStatus.READY.value
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_create_rejects_unknown_lead(tmp_path: Path) -> None:
    settings = _settings(storage_dir=tmp_path)
    session = Mock()
    session.get.return_value = None
    service = MockupService(session, settings, tmp_path)
    with pytest.raises(AppError) as caught:
        service.create(
            MockupCreate(lead_id=uuid4(), provider="gemini", goal="calls", guide_mode="none")
        )
    assert caught.value.code == "LEAD_NOT_FOUND"


def test_eligibility_rules() -> None:
    from app.services.mockup_eligibility import evaluate_mockup_eligibility

    bare = Lead(business_name="No Site Cafe", lead_status=LeadStatus.NEW.value)
    allowed = evaluate_mockup_eligibility(bare, None)
    assert allowed.allowed is True
    assert allowed.reason == "no_website"

    with_site = Lead(
        business_name="Has Site",
        lead_status=LeadStatus.NEW.value,
        website_url="https://example.com",
        website_status="present",
    )
    blocked = evaluate_mockup_eligibility(with_site, None)
    assert blocked.allowed is False

    weak = WebsiteAudit(
        lead_id=uuid4(),
        url="https://example.com",
        status=AuditStatus.COMPLETED.value,
        design_score=40,
    )
    ok = evaluate_mockup_eligibility(with_site, weak)
    assert ok.allowed is True
    assert ok.reason == "weak_design"

    strong = WebsiteAudit(
        lead_id=uuid4(),
        url="https://example.com",
        status=AuditStatus.COMPLETED.value,
        design_score=72,
    )
    denied = evaluate_mockup_eligibility(with_site, strong)
    assert denied.allowed is False

