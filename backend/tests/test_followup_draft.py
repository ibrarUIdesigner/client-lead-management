from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

from app.models.followup import Followup
from app.models.lead import Lead
from app.models.outreach import OutreachMessage
from app.services.followups import FollowupService


def test_generate_day4_followup_with_mockup():
    session = Mock()
    lead = Lead(
        id=uuid4(),
        business_name="Horizon Roofing",
        industry="Roofing",
        website_url="https://horizonroofs.test",
        lead_status="CONTACTED",
    )
    msg = OutreachMessage(
        id=uuid4(),
        lead_id=lead.id,
        subject="Quick idea for Horizon Roofing website",
        message="Original pitch text",
    )
    followup = Followup(
        id=uuid4(),
        lead_id=lead.id,
        outreach_id=msg.id,
        scheduled_for=datetime.now(UTC),
        status="SCHEDULED",
    )

    session.get.side_effect = lambda model, ident: {
        (Followup, followup.id): followup,
        (Lead, lead.id): lead,
        (OutreachMessage, msg.id): msg,
    }.get((model, ident))

    session.scalar.return_value = 0  # 0 completed followups -> step 1
    session.scalars.return_value = []

    service = FollowupService(session)
    draft = service.generate_followup_draft(followup.id)

    assert draft["sequence_step"] == 1
    assert "Re: Quick idea for Horizon Roofing website" in draft["subject"]
    assert "Following up briefly" in draft["body"]
