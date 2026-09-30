from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.contact import Contact
from app.models.enums import AuditStatus, LeadStatus, MockupStatus, OutreachStatus
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage, OutreachTemplate
from app.models.website_audit import WebsiteAudit
from app.repositories.activities import ActivityRepository
from app.repositories.contacts import ContactRepository
from app.repositories.leads import LeadRepository
from app.schemas.outreach import OutreachCreate, OutreachGenerate, OutreachUpdate
from app.schemas.workspace import OutreachMessageRead
from app.services.outreach_copy import compose_outreach, findings_message, next_lead_status
from app.services.persistence import flush_or_reject
from app.services.workspace import WorkspaceService

_EDITABLE = {OutreachStatus.DRAFT.value, OutreachStatus.READY.value}
_ALREADY_SENT = {
    OutreachStatus.SENT.value,
    OutreachStatus.OPENED.value,
    OutreachStatus.REPLIED.value,
}


class OutreachService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.contacts = ContactRepository(session)
        self.activities = ActivityRepository(session)
        self.workspace = WorkspaceService(session)

    def list_for_lead(self, lead_id: UUID) -> list[OutreachMessageRead]:
        self._require_lead(lead_id)
        return self.workspace.list_messages(lead_id)

    def generate(self, lead_id: UUID, data: OutreachGenerate) -> OutreachMessageRead:
        lead = self._require_lead(lead_id)
        contact = self._resolve_contact(lead.id, data.contact_id)
        template = self._template_for_generate(data.template_id)
        subject, body = compose_outreach(
            template.subject if template else None,
            template.body if template else None,
            business=lead.business_name,
            name=contact.name if contact else None,
            industry=lead.industry,
            website=lead.website_url,
            mockup=self._mockup_label(lead.id),
            audit_findings=self._audit_findings(lead.id),
        )
        message = OutreachMessage(
            lead_id=lead.id,
            contact_id=contact.id if contact else None,
            channel=template.channel if template and template.channel else "email",
            subject=subject,
            message=body,
            template_id=template.id if template else None,
            status=OutreachStatus.DRAFT.value,
        )
        self.session.add(message)
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "outreach_drafted",
            "Outreach draft created",
            description=subject,
        )
        self.session.commit()
        return self._read(message.id)

    def create(self, data: OutreachCreate) -> OutreachMessageRead:
        if not (data.subject or data.message):
            return self.generate(
                data.lead_id,
                OutreachGenerate(template_id=data.template_id, contact_id=data.contact_id),
            )
        lead = self._require_lead(data.lead_id)
        contact = self._resolve_contact(lead.id, data.contact_id)
        template = self._require_template(data.template_id) if data.template_id else None
        message = OutreachMessage(
            lead_id=lead.id,
            contact_id=contact.id if contact else None,
            channel=data.channel or "email",
            subject=data.subject,
            message=data.message,
            template_id=template.id if template else None,
            status=OutreachStatus.DRAFT.value,
        )
        self.session.add(message)
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "outreach_drafted",
            "Outreach draft created",
            description=data.subject,
        )
        self.session.commit()
        return self._read(message.id)

    def update(self, message_id: UUID, data: OutreachUpdate) -> OutreachMessageRead:
        message = self._require(message_id)
        self._ensure_editable(message)
        changes = data.model_dump(exclude_unset=True)
        if "contact_id" in changes and changes["contact_id"] is not None:
            contact = self._resolve_contact(message.lead_id, changes["contact_id"])
            changes["contact_id"] = contact.id
        for key, value in changes.items():
            setattr(message, key, value)
        flush_or_reject(self.session)
        if changes:
            self.activities.add(
                message.lead_id,
                "outreach_updated",
                "Outreach draft updated",
                description=message.subject,
            )
        self.session.commit()
        return self._read(message.id)

    def mark_contacted(self, message_id: UUID) -> OutreachMessageRead:
        message = self._require(message_id)
        if message.status in _ALREADY_SENT:
            return self._read(message.id)
        self._reject_cancelled(message)
        self._require_content(message)
        now = datetime.now(UTC)
        message.status = OutreachStatus.SENT.value
        message.sent_at = now
        lead = self._require_lead(message.lead_id)
        lead.last_contacted_at = now
        self._advance(lead, LeadStatus.CONTACTED)
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "outreach_sent",
            "Marked as contacted",
            description=message.subject,
        )
        self.session.commit()
        return self._read(message.id)

    def mark_replied(self, message_id: UUID) -> OutreachMessageRead:
        message = self._require(message_id)
        if message.status == OutreachStatus.REPLIED.value:
            return self._read(message.id)
        self._reject_cancelled(message)
        self._require_content(message)
        now = datetime.now(UTC)
        if message.sent_at is None:
            message.sent_at = now
        message.status = OutreachStatus.REPLIED.value
        message.replied_at = now
        lead = self._require_lead(message.lead_id)
        if lead.last_contacted_at is None:
            lead.last_contacted_at = message.sent_at
        self._advance(lead, LeadStatus.REPLIED)
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "outreach_replied",
            "Reply recorded",
            description=message.subject,
        )
        self.session.commit()
        return self._read(message.id)

    def _advance(self, lead: Lead, target: LeadStatus) -> None:
        updated = next_lead_status(lead.lead_status, target)
        if updated is None:
            return
        previous = lead.lead_status
        lead.lead_status = updated
        self.activities.add(
            lead.id,
            "status_changed",
            "Status changed",
            description=f"{previous} to {updated}",
            details={"from": previous, "to": updated},
        )

    def _template_for_generate(self, template_id: UUID | None) -> OutreachTemplate | None:
        if template_id is not None:
            return self._require_template(template_id)
        statement = (
            select(OutreachTemplate)
            .where(OutreachTemplate.is_active.is_(True))
            .order_by(OutreachTemplate.name.asc())
        )
        templates = list(self.session.scalars(statement))
        intro = next((item for item in templates if item.template_type == "introduction"), None)
        return intro or (templates[0] if templates else None)

    def _require_template(self, template_id: UUID) -> OutreachTemplate:
        template = self.session.get(OutreachTemplate, template_id)
        if template is None:
            raise AppError(
                code="TEMPLATE_NOT_FOUND",
                message="That template could not be found.",
                status_code=404,
            )
        return template

    def _resolve_contact(self, lead_id: UUID, contact_id: UUID | None) -> Contact | None:
        rows = self.contacts.list_for_lead(lead_id)
        if contact_id is None:
            primary = next((item for item in rows if item.is_primary), None)
            return primary or (rows[0] if rows else None)
        match = next((item for item in rows if item.id == contact_id), None)
        if match is None:
            raise AppError(
                code="CONTACT_NOT_FOUND",
                message="That contact could not be found.",
                status_code=404,
            )
        return match

    def _audit_findings(self, lead_id: UUID) -> str | None:
        statement = (
            select(WebsiteAudit)
            .where(WebsiteAudit.lead_id == lead_id)
            .order_by(WebsiteAudit.created_at.desc())
        )
        rows = list(self.session.scalars(statement))
        audit = next((item for item in rows if item.status == AuditStatus.COMPLETED.value), None)
        if audit is None:
            return None
        report = audit.raw_analysis.get("report") if isinstance(audit.raw_analysis, dict) else None
        return findings_message(audit.issues, report)

    def _mockup_label(self, lead_id: UUID) -> str | None:
        ready = self.session.scalar(
            select(Mockup.title)
            .where(
                Mockup.lead_id == lead_id,
                Mockup.status == MockupStatus.READY.value,
                Mockup.title.is_not(None),
            )
            .order_by(Mockup.version.desc())
            .limit(1)
        )
        if isinstance(ready, str) and ready.strip():
            return ready.strip()
        title = self.session.scalar(
            select(Mockup.title)
            .where(Mockup.lead_id == lead_id, Mockup.title.is_not(None))
            .order_by(Mockup.version.desc())
            .limit(1)
        )
        if isinstance(title, str) and title.strip():
            return title.strip()
        return None

    def _require_lead(self, lead_id: UUID) -> Lead:
        lead = self.leads.get(lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )
        return lead

    def _require(self, message_id: UUID) -> OutreachMessage:
        message = self.session.get(OutreachMessage, message_id)
        if message is None:
            raise AppError(
                code="OUTREACH_NOT_FOUND",
                message="That outreach could not be found.",
                status_code=404,
            )
        return message

    def _read(self, message_id: UUID) -> OutreachMessageRead:
        message = self.workspace.get_message(message_id)
        if message is None:
            raise AppError(
                code="OUTREACH_NOT_FOUND",
                message="That outreach could not be found.",
                status_code=404,
            )
        return message

    def _ensure_editable(self, message: OutreachMessage) -> None:
        if message.status == OutreachStatus.CANCELLED.value:
            self._reject_cancelled(message)
        if message.status not in _EDITABLE:
            raise AppError(
                code="OUTREACH_NOT_EDITABLE",
                message="Sent outreach stays as the record of what you sent.",
                status_code=409,
            )

    def _reject_cancelled(self, message: OutreachMessage) -> None:
        if message.status == OutreachStatus.CANCELLED.value:
            raise AppError(
                code="OUTREACH_CANCELLED",
                message="That outreach was cancelled.",
                status_code=409,
            )

    def _require_content(self, message: OutreachMessage) -> None:
        if not (message.subject or "").strip() or not (message.message or "").strip():
            raise AppError(
                code="OUTREACH_INCOMPLETE",
                message="Add a subject and message before you record this email.",
                status_code=422,
            )
