from app.models.lead import Lead
from app.models.website_audit import WebsiteAudit
from app.services.signals import SignalDetector


def test_detect_no_website_signal():
    detector = SignalDetector()
    lead = Lead(business_name="Acme Roofs", industry="Roofing", website_url=None)
    signals = detector.detect_all(lead, audit=None, research=None)
    names = [s.name for s in signals]
    assert "NO_WEBSITE" in names
    no_web = next(s for s in signals if s.name == "NO_WEBSITE")
    assert no_web.type == "website"
    assert no_web.confidence >= 0.95
    assert "Acme Roofs" in no_web.evidence


def test_detect_website_friction_signals():
    detector = SignalDetector()
    lead = Lead(
        business_name="Bright Smile Dental",
        industry="Dental",
        website_url="https://brightsmile.test",
        email="contact@brightsmile.test",
    )
    audit = WebsiteAudit(
        lead_id=lead.id,
        url="https://brightsmile.test",
        performance_score=38,
        mobile_score=42,
        is_mobile_responsive=False,
        has_clear_cta=False,
        has_contact_form=False,
        raw_analysis={"lcp_ms": 4800, "cta_labels": []},
    )
    signals = detector.detect_all(lead, audit=audit, research=None)
    names = {s.name for s in signals}
    assert "SLOW_WEBSITE" in names
    assert "POOR_MOBILE_UX" in names
    assert "NO_CLEAR_CTA" in names
    assert "MISSING_BOOKING" in names
    assert "HIGH_INTENT" in names
