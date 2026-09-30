from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import FollowupStatus, LeadStatus
from app.models.followup import Followup
from app.models.lead import Lead
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
