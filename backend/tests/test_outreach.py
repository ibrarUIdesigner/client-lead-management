from unittest.mock import Mock
from uuid import uuid4

from app.models.enums import LeadStatus
from app.services.outreach_copy import (
    compose_outreach,
    findings_message,
    findings_text,
    next_lead_status,
)
from tests.test_leads_api import _client


def test_compose_outreach_fills_the_business_and_contact() -> None:
    subject, body = compose_outreach(
        "A clearer homepage for {business}",
        "Hi {name},\n\nI put together a homepage concept for {business}. {findings}\n",
        business="Northwind Cafe",
        name="Ada",
        industry="Cafe",
        website="https://northwind.example",
        mockup="Homepage v2",
        audit_findings="Poor mobile UX",
    )

    assert subject == "A clearer homepage for Northwind Cafe"
    assert "Hi Ada," in body
    assert "Poor mobile UX" in body
    assert "{business}" not in body


def test_compose_outreach_adds_audit_findings_when_the_template_omits_them() -> None:
    _subject, body = compose_outreach(
        "Hello {business}",
        "Hi {name},\n\nHappy to walk through a homepage concept.\n",
        business="Northwind Cafe",
        name=None,
        industry=None,
        website=None,
        mockup=None,
        audit_findings="Poor mobile UX and No clear call to action",
    )

    assert "Hi there," in body
    assert "What stood out: Poor mobile UX and No clear call to action." in body


def test_findings_message_is_written_from_the_audit_report() -> None:
    text = findings_message(
        [{"title": "Ignored title", "detail": "This should not be used."}],
        [
            {"title": "Weak CTA", "detail": "No clear call to action was found."},
            {"title": "Slow", "detail": "The page took more than 4 seconds to load"},
        ],
    )

    assert text is not None
    assert "A few things stood out:" in text
    assert "No clear call to action was found." in text
    assert "The page took more than 4 seconds to load." in text
    assert "Ignored title" not in text


def test_builtin_email_uses_the_findings() -> None:
    findings = findings_message(
        None,
        [{"title": "Weak CTA", "detail": "No clear call to action was found."}],
    )
    subject, body = compose_outreach(
        None,
        None,
        business="AL-Tuaam",
        name=None,
        industry="Cafe",
        website="https://altuaam.com/",
        mockup=None,
        audit_findings=findings,
    )

    assert subject == "A clearer homepage for AL-Tuaam"
    assert "I looked at the AL-Tuaam website." in body
    assert "No clear call to action was found." in body


def test_findings_text_uses_the_first_two_issue_titles() -> None:
    text = findings_text(
        [
            {"title": "Poor mobile UX"},
            {"title": "No clear call to action"},
            {"title": "Thin content"},
        ]
    )

    assert text == "Poor mobile UX and No clear call to action"


def test_next_lead_status_moves_forward_only() -> None:
    assert next_lead_status("MOCKUP_READY", LeadStatus.CONTACTED) == "CONTACTED"
    assert next_lead_status("CONTACTED", LeadStatus.CONTACTED) is None
    assert next_lead_status("REPLIED", LeadStatus.CONTACTED) is None
    assert next_lead_status("WON", LeadStatus.REPLIED) is None
    assert next_lead_status("FOLLOW_UP", LeadStatus.REPLIED) == "REPLIED"


def test_generate_outreach_reports_a_missing_lead() -> None:
    session = Mock()
    session.get.return_value = None
    lead_id = uuid4()

    with _client(session) as client:
        response = client.post(f"/api/v1/leads/{lead_id}/outreach/generate", json={})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LEAD_NOT_FOUND"


def test_schedule_followup_requires_a_time() -> None:
    with _client(Mock()) as client:
        response = client.post("/api/v1/followups", json={"lead_id": str(uuid4())})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
