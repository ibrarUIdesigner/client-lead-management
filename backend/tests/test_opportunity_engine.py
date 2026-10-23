from app.models.lead import Lead
from app.models.website_audit import WebsiteAudit
from app.services.opportunity_engine import OpportunityEngine
from app.services.signals import SignalDetector


def test_opportunity_engine_analysis_and_scoring():
    detector = SignalDetector()
    engine = OpportunityEngine()

    lead = Lead(
        business_name="Elite Dental Clinic",
        industry="Dental",
        website_url="https://elitedental.test",
        email="hello@elitedental.test",
    )
    audit = WebsiteAudit(
        lead_id=lead.id,
        url="https://elitedental.test",
        performance_score=40,
        mobile_score=45,
        is_mobile_responsive=False,
        has_clear_cta=False,
        has_contact_form=False,
        overall_score=45,
        raw_analysis={"lcp_ms": 5000, "cta_labels": []},
    )

    signals = detector.detect_all(lead, audit=audit, research=None)
    opportunities = engine.analyze_opportunities(lead, signals, audit=audit, research=None)
    assert len(opportunities) >= 2

    # Check opportunity structure
    booking_opp = next((o for o in opportunities if "booking" in o.problem.lower()), None)
    assert booking_opp is not None
    assert booking_opp.impact == "high"
    assert booking_opp.confidence > 0.8
    assert booking_opp.recommended_solution != ""

    score_result = engine.calculate_score(lead, signals, audit=audit, research=None)
    assert score_result.total_score >= 70
    assert score_result.tier in {"high", "medium"}
    assert len(score_result.breakdown) >= 4

    # Verify explainability: sum of points equals total_score
    calculated_sum = min(100, max(0, sum(f.points for f in score_result.breakdown)))
    assert score_result.total_score == calculated_sum
