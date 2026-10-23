from unittest.mock import Mock
from uuid import uuid4

from app.models.lead import Lead
from app.services.reply_handler import ReplyHandlerService


def test_classify_pricing_objection():
    session = Mock()
    lead = Lead(
        id=uuid4(),
        business_name="Radiant Skin Spa",
        industry="Spa",
        website_url="https://radiantskin.test",
        lead_status="CONTACTED",
    )
    session.get.return_value = lead
    session.scalars.return_value = []

    service = ReplyHandlerService(session)
    analysis = service.analyze_and_process_reply(
        lead.id,
        subject="Re: Homepage concept",
        body_text="Sounds interesting. How much does this redesign cost?",
        sender_email="owner@radiantskin.test",
    )

    assert analysis.intent == "Pricing"
    assert "cost" in analysis.summary.lower() or "price" in analysis.summary.lower()
    assert analysis.suggested_response_body is not None
    assert "$750" in analysis.suggested_response_body or "$850" in analysis.suggested_response_body


def test_classify_unsubscribe_and_opt_out():
    session = Mock()
    lead = Lead(
        id=uuid4(),
        business_name="Old Town Auto",
        industry="Auto",
        website_url="https://oldtown.test",
        lead_status="CONTACTED",
    )
    session.get.return_value = lead
    session.scalars.return_value = []

    service = ReplyHandlerService(session)
    analysis = service.analyze_and_process_reply(
        lead.id,
        subject="Re: Web services",
        body_text="Please remove me from your list and unsubscribe.",
        sender_email="contact@oldtown.test",
    )

    assert analysis.intent == "Unsubscribe"
    assert lead.do_not_contact is True
    assert lead.lead_status == "DO_NOT_CONTACT"


def test_classify_meeting_request():
    session = Mock()
    lead = Lead(
        id=uuid4(),
        business_name="Metro Legal Group",
        industry="Legal",
        website_url="https://metrolegal.test",
        lead_status="CONTACTED",
    )
    session.get.return_value = lead
    session.scalars.return_value = []

    service = ReplyHandlerService(session)
    analysis = service.analyze_and_process_reply(
        lead.id,
        subject="Re: Homepage",
        body_text="Let's hop on a call this Thursday to discuss.",
        sender_email="partner@metrolegal.test",
    )

    assert analysis.intent == "Meeting Request"
    assert analysis.suggested_stage == "Meeting Requested"
    assert lead.lead_status == "REPLIED"
