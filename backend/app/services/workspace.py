from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models import (
    BrandProfile,
    Followup,
    Lead,
    Mockup,
    OutreachMessage,
    OutreachTemplate,
)
from app.models.enums import AuditStatus, LeadStatus, MockupStatus, OutreachStatus
from app.models.website_audit import WebsiteAudit
from app.schemas.workspace import (
    AnalyticsRead,
    FollowupRead,
    LabelCount,
    MockupRead,
    OutreachMessageRead,
    OutreachTemplateRead,
    StatusCount,
)


class WorkspaceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_mockups(self, lead_id: UUID | None = None) -> list[MockupRead]:
        statement = (
            select(
                Mockup.id,
                Mockup.lead_id,
                Lead.business_name,
                Lead.city,
                Mockup.title,
                Mockup.status,
                Mockup.version,
                Mockup.notes,
                Mockup.prompt,
                BrandProfile.primary_color,
                Mockup.completed_at,
                Mockup.created_at,
            )
            .join(Lead, Lead.id == Mockup.lead_id)
            .outerjoin(BrandProfile, BrandProfile.lead_id == Mockup.lead_id)
            .order_by(Mockup.created_at.desc())
        )
        if lead_id is not None:
            statement = statement.where(Mockup.lead_id == lead_id)
        return [
            MockupRead.model_validate(row, from_attributes=True)
            for row in self.session.execute(statement)
        ]

    def list_messages(self, lead_id: UUID | None = None) -> list[OutreachMessageRead]:
        statement = self._messages().order_by(OutreachMessage.created_at.desc())
        if lead_id is not None:
            statement = statement.where(OutreachMessage.lead_id == lead_id)
        return [
            OutreachMessageRead.model_validate(row, from_attributes=True)
            for row in self.session.execute(statement)
        ]

    def get_message(self, message_id: UUID) -> OutreachMessageRead | None:
        statement = self._messages().where(OutreachMessage.id == message_id)
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return OutreachMessageRead.model_validate(row, from_attributes=True)

    def _messages(self):
        return (
            select(
                OutreachMessage.id,
                OutreachMessage.lead_id,
                Lead.business_name,
                OutreachMessage.channel,
                Lead.email.label("recipient_email"),
                OutreachMessage.subject,
                OutreachMessage.message,
                OutreachMessage.status,
                OutreachMessage.sent_at,
                OutreachMessage.opened_at,
                OutreachMessage.replied_at,
                OutreachMessage.created_at,
            )
            .join(Lead, Lead.id == OutreachMessage.lead_id)
        )

    def list_templates(self) -> list[OutreachTemplateRead]:
        statement = select(OutreachTemplate).order_by(OutreachTemplate.name.asc())
        return [
            OutreachTemplateRead.model_validate(row, from_attributes=True)
            for row in self.session.scalars(statement)
        ]

    def list_followups(self) -> list[FollowupRead]:
        statement = self._followups().order_by(Followup.scheduled_for.asc())
        return [
            FollowupRead.model_validate(row, from_attributes=True)
            for row in self.session.execute(statement)
        ]

    def get_followup(self, followup_id: UUID) -> FollowupRead | None:
        statement = self._followups().where(Followup.id == followup_id)
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return FollowupRead.model_validate(row, from_attributes=True)

    def _followups(self):
        return select(
            Followup.id,
            Followup.lead_id,
            Lead.business_name,
            Lead.city,
            Followup.scheduled_for,
            Followup.type,
            Followup.status,
            Followup.notes,
            Followup.completed_at,
        ).join(Lead, Lead.id == Followup.lead_id)

    def analytics(self) -> AnalyticsRead:
        status_rows = self.session.execute(
            select(Lead.lead_status, func.count()).group_by(Lead.lead_status)
        ).all()
        counts = {status: int(count) for status, count in status_rows}
        by_status = [
            StatusCount(status=status.value, count=counts.get(status.value, 0))
            for status in LeadStatus
        ]
        return AnalyticsRead(
            leads=sum(item.count for item in by_status),
            audits_completed=self._count(
                WebsiteAudit, WebsiteAudit.status == AuditStatus.COMPLETED.value
            ),
            mockups_ready=self._count(Mockup, Mockup.status == MockupStatus.READY.value),
            contacted=self._count(
                OutreachMessage,
                OutreachMessage.status.in_(
                    [
                        OutreachStatus.SENT.value,
                        OutreachStatus.OPENED.value,
                        OutreachStatus.REPLIED.value,
                    ]
                ),
            ),
            replies=self._count(
                OutreachMessage, OutreachMessage.status == OutreachStatus.REPLIED.value
            ),
            meetings=counts.get(LeadStatus.MEETING.value, 0),
            proposals=counts.get(LeadStatus.PROPOSAL.value, 0),
            wins=counts.get(LeadStatus.WON.value, 0),
            losses=counts.get(LeadStatus.LOST.value, 0),
            by_status=by_status,
            by_industry=self._grouped(Lead.industry),
            by_city=self._grouped(Lead.city),
            by_source=self._grouped(Lead.source),
            high_scores=self._count(Lead, Lead.lead_score >= 70),
            websites_missing=self._count(Lead, Lead.website_status == "missing"),
        )

    def _count(self, model: type[object], *criteria: object) -> int:
        statement = select(func.count()).select_from(model).where(*criteria)
        return int(self.session.scalar(statement) or 0)

    def _grouped(self, column: InstrumentedAttribute[str | None]) -> list[LabelCount]:
        amount = func.count().label("amount")
        statement = (
            select(column, amount)
            .where(column.is_not(None))
            .group_by(column)
            .order_by(amount.desc(), column.asc())
        )
        return [
            LabelCount(label=str(label), count=int(count))
            for label, count in self.session.execute(statement)
            if label
        ]
