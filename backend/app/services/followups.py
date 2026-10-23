from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import FollowupStatus, LeadStatus
from app.models.followup import Followup
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.repositories.activities import ActivityRepository
from app.repositories.leads import LeadRepository
from app.schemas.outreach import FollowupCreate, FollowupUpdate
from app.schemas.workspace import FollowupRead
from app.services.persistence import flush_or_reject
from app.services.workspace import WorkspaceService

_OPEN = {FollowupStatus.SCHEDULED.value, FollowupStatus.DUE.value}


class FollowupService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.activities = ActivityRepository(session)
        self.workspace = WorkspaceService(session)

    def create(self, data: FollowupCreate) -> FollowupRead:
        lead = self._require_lead(data.lead_id)
        self._require_outreach(lead.id, data.outreach_id)
        when = _aware(data.scheduled_for)
        followup = Followup(
            lead_id=lead.id,
            outreach_id=data.outreach_id,
            scheduled_for=when,
            type=data.type or "email",
            status=_open_status(when),
            notes=data.notes,
        )
        self.session.add(followup)
        flush_or_reject(self.session)
        self._sync_next_followup(lead)
        if lead.lead_status == LeadStatus.CONTACTED.value:
            previous = lead.lead_status
            lead.lead_status = LeadStatus.FOLLOW_UP.value
            self.activities.add(
                lead.id,
                "status_changed",
                "Status changed",
                description=f"{previous} to {lead.lead_status}",
                details={"from": previous, "to": lead.lead_status},
            )
        self.activities.add(
            lead.id,
            "followup_scheduled",
            "Follow-up scheduled",
            description=when.date().isoformat(),
        )
        self.session.commit()
        return self._read(followup.id)

    def update(self, followup_id: UUID, data: FollowupUpdate) -> FollowupRead:
        followup = self._require_open(followup_id)
        changes = data.model_dump(exclude_unset=True)
        if "scheduled_for" in changes and changes["scheduled_for"] is not None:
            when = _aware(changes["scheduled_for"])
            changes["scheduled_for"] = when
            changes["status"] = _open_status(when)
        for key, value in changes.items():
            setattr(followup, key, value)
        flush_or_reject(self.session)
        lead = self._require_lead(followup.lead_id)
        self._sync_next_followup(lead)
        if changes:
            self.activities.add(
                followup.lead_id,
                "followup_rescheduled",
                "Follow-up rescheduled",
                description=followup.scheduled_for.date().isoformat(),
            )
        self.session.commit()
        return self._read(followup.id)

    def complete(self, followup_id: UUID) -> FollowupRead:
        followup = self._require(followup_id)
        if followup.status == FollowupStatus.COMPLETED.value:
            return self._read(followup.id)
        if followup.status == FollowupStatus.CANCELLED.value:
            raise AppError(
                code="FOLLOWUP_CLOSED",
                message="That follow-up was cancelled.",
                status_code=409,
            )
        followup.status = FollowupStatus.COMPLETED.value
        followup.completed_at = datetime.now(UTC)
        flush_or_reject(self.session)
        lead = self._require_lead(followup.lead_id)
        self._sync_next_followup(lead)
        self.activities.add(
            followup.lead_id,
            "followup_completed",
            "Follow-up completed",
            description=followup.scheduled_for.date().isoformat(),
        )
        self.session.commit()
        return self._read(followup.id)

    def cancel(self, followup_id: UUID) -> None:
        followup = self._require(followup_id)
        if followup.status == FollowupStatus.COMPLETED.value:
            raise AppError(
                code="FOLLOWUP_CLOSED",
                message="That follow-up is already finished.",
                status_code=409,
            )
        if followup.status == FollowupStatus.CANCELLED.value:
            return
        followup.status = FollowupStatus.CANCELLED.value
        flush_or_reject(self.session)
        lead = self._require_lead(followup.lead_id)
        self._sync_next_followup(lead)
        self.activities.add(
            followup.lead_id,
            "followup_cancelled",
            "Follow-up cancelled",
            description=followup.scheduled_for.date().isoformat(),
        )
        self.session.commit()

    def generate_followup_draft(self, followup_id: UUID) -> dict[str, Any]:
        followup = self._require(followup_id)
        lead = self._require_lead(followup.lead_id)

        statement = select(func.count()).where(
            Followup.lead_id == lead.id,
            Followup.status == FollowupStatus.COMPLETED.value,
        )
        completed_count = self.session.scalar(statement) or 0
        sequence_step = min(3, completed_count + 1)

        original_msg = None
        if followup.outreach_id:
            original_msg = self.session.get(OutreachMessage, followup.outreach_id)
        if not original_msg:
            stmt = (
                select(OutreachMessage)
                .where(OutreachMessage.lead_id == lead.id)
                .order_by(OutreachMessage.created_at.desc())
            )
            rows = list(self.session.scalars(stmt))
            original_msg = rows[0] if rows else None

        orig_subj = (
            original_msg.subject
            if original_msg and original_msg.subject
            else f"Homepage design for {lead.business_name}"
        )
        clean_subj = orig_subj if orig_subj.lower().startswith("re:") else f"Re: {orig_subj}"

        mockup_stmt = select(Mockup).where(Mockup.lead_id == lead.id).order_by(Mockup.version.desc())
        m_rows = list(self.session.scalars(mockup_stmt))
        mockup = m_rows[0] if m_rows else None
        mockup_url = f"/mockups/{mockup.id}" if mockup else None

        first_name = lead.business_name.split()[0] if lead.business_name else "there"
        sender_name = "Ibrar"

        if sequence_step == 1:
            body = (
                f"Hi {first_name},\n\n"
                f"Following up briefly on my earlier note about {lead.business_name}'s website.\n\n"
            )
            if mockup_url:
                body += (
                    f"In case you missed it, I had put together a quick preview concept showing a cleaner mobile layout with a direct booking section:\n"
                    f"{mockup_url}\n\n"
                )
            else:
                body += (
                    "I'd love to share a couple of quick observations on how tightening the mobile conversion flow could help capture more inquiries.\n\n"
                )
            body += f"Would you be open to taking a quick look this week?\n\nBest,\n{sender_name}"
            strategy_label = "Day 4: Value Bump with Mockup Preview"
        elif sequence_step == 2:
            ind = lead.industry or "businesses"
            loc = lead.city or "your area"
            body = (
                f"Hi {first_name},\n\n"
                f"One trend we're seeing across {ind} in {loc} is that over 60% of bookings happen outside typical working hours via mobile.\n\n"
                f"Without an easy way to request a quote or book online, those prospective clients usually bounce over to the next provider.\n\n"
                f"Happy to walk you through how the concept we designed solves that. Are you free for 5 minutes Thursday?\n\nBest,\n{sender_name}"
            )
            strategy_label = "Day 10: Market Trend & Mobile Friction Angle"
        else:
            body = (
                f"Hi {first_name},\n\n"
                f"I know you're busy running {lead.business_name}, so I won't clutter your inbox further.\n\n"
                f"If you ever decide to refresh your website or improve mobile inquiries down the road, feel free to reach out anytime.\n\n"
                f"Wishing you and the team continued success!\n\nBest,\n{sender_name}"
            )
            strategy_label = "Day 20: Graceful Breakup"

        return {
            "followup_id": str(followup.id),
            "lead_id": str(lead.id),
            "sequence_step": sequence_step,
            "strategy": strategy_label,
            "subject": clean_subj,
            "body": body,
        }

    def _sync_next_followup(self, lead: Lead) -> None:
        statement = (
            select(Followup.scheduled_for)
            .where(Followup.lead_id == lead.id, Followup.status.in_(_OPEN))
            .order_by(Followup.scheduled_for.asc())
            .limit(1)
        )
        lead.next_followup_at = self.session.scalar(statement)

    def _require_outreach(self, lead_id: UUID, outreach_id: UUID | None) -> None:
        if outreach_id is None:
            return
        message = self.session.get(OutreachMessage, outreach_id)
        if message is None or message.lead_id != lead_id:
            raise AppError(
                code="OUTREACH_NOT_FOUND",
                message="That outreach could not be found.",
                status_code=404,
            )

    def _require_open(self, followup_id: UUID) -> Followup:
        followup = self._require(followup_id)
        if followup.status == FollowupStatus.COMPLETED.value:
            raise AppError(
                code="FOLLOWUP_CLOSED",
                message="Completed follow-ups stay in the history. Schedule a new one instead.",
                status_code=409,
            )
        if followup.status == FollowupStatus.CANCELLED.value:
            raise AppError(
                code="FOLLOWUP_CLOSED",
                message="That follow-up was cancelled.",
                status_code=409,
            )
        return followup

    def _require_lead(self, lead_id: UUID) -> Lead:
        lead = self.leads.get(lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )
        return lead

    def _require(self, followup_id: UUID) -> Followup:
        followup = self.session.get(Followup, followup_id)
        if followup is None:
            raise AppError(
                code="FOLLOWUP_NOT_FOUND",
                message="That follow-up could not be found.",
                status_code=404,
            )
        return followup

    def _read(self, followup_id: UUID) -> FollowupRead:
        followup = self.workspace.get_followup(followup_id)
        if followup is None:
            raise AppError(
                code="FOLLOWUP_NOT_FOUND",
                message="That follow-up could not be found.",
                status_code=404,
            )
        return followup


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _open_status(when: datetime) -> str:
    if when <= datetime.now(UTC):
        return FollowupStatus.DUE.value
    return FollowupStatus.SCHEDULED.value
