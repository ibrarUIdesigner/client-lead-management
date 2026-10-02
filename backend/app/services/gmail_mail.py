from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.integrations.gmail import (
    GmailApiError,
    GmailAttachment,
    GmailClient,
    sanitize_email_html,
)
from app.models.enums import (
    EmailClassification,
    EmailDirection,
    LeadStatus,
    MockupStatus,
    OutreachStatus,
)
from app.models.gmail import LeadEmail
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.models.website_audit import WebsiteAudit
from app.repositories.activities import ActivityRepository
from app.repositories.leads import LeadRepository
from app.schemas.gmail import (
    LeadEmailRead,
    LeadEmailReplyRequest,
    LeadEmailSendRequest,
    LeadEmailThreadSummary,
)
from app.services.gmail_accounts import GmailAccountService
from app.services.outreach_copy import next_lead_status
from app.services.persistence import flush_or_reject
from app.services.storage import read_screenshot, resolve_storage_path

logger = logging.getLogger(__name__)


class GmailMailService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        client: GmailClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.accounts = GmailAccountService(session, self.settings, client)
        self.client = client or self.accounts.client
        self.leads = LeadRepository(session)
        self.activities = ActivityRepository(session)

    def list_for_lead(self, lead_id: UUID) -> LeadEmailThreadSummary:
        lead = self._require_lead(lead_id)
        rows = list(
            self.session.scalars(
                select(LeadEmail)
                .where(LeadEmail.lead_id == lead_id)
                .order_by(LeadEmail.occurred_at.asc(), LeadEmail.created_at.asc())
            )
        )
        unread = sum(1 for row in rows if row.is_unread)
        return LeadEmailThreadSummary(
            last_contacted_at=lead.last_contacted_at,
            last_replied_at=lead.last_replied_at,
            next_followup_at=lead.next_followup_at,
            email_unread=lead.email_unread,
            do_not_contact=lead.do_not_contact,
            email_suppressed=lead.email_suppressed,
            unread_count=unread,
            items=[self._read(row) for row in rows],
        )

    def mark_read(self, lead_id: UUID) -> LeadEmailThreadSummary:
        lead = self._require_lead(lead_id)
        rows = list(
            self.session.scalars(
                select(LeadEmail).where(
                    LeadEmail.lead_id == lead_id,
                    LeadEmail.is_unread.is_(True),
                )
            )
        )
        for row in rows:
            row.is_unread = False
        lead.email_unread = False
        flush_or_reject(self.session)
        self.session.commit()
        return self.list_for_lead(lead_id)

    def send(
        self,
        lead_id: UUID,
        data: LeadEmailSendRequest,
        *,
        idempotency_key: str | None = None,
    ) -> LeadEmailRead:
        lead = self._require_lead(lead_id)
        self._assert_can_send(lead)
        key = idempotency_key or data.idempotency_key
        if key:
            existing = self.session.scalar(
                select(LeadEmail).where(LeadEmail.idempotency_key == key)
            )
            if existing is not None:
                return self._read(existing)

        account = self.accounts.require_active_account()
        recipient = (data.to or lead.email or "").strip().lower()
        if not recipient:
            raise AppError(
                code="EMAIL_RECIPIENT_REQUIRED",
                message="Add a recipient email before sending.",
                status_code=422,
            )
        if lead.email_suppressed and lead.suppressed_email == recipient:
            raise AppError(
                code="EMAIL_SUPPRESSED",
                message="Sending to this address is suppressed after a bounce.",
                status_code=409,
            )

        outreach = None
        if data.outreach_message_id is not None:
            outreach = self.session.get(OutreachMessage, data.outreach_message_id)
            if outreach is None or outreach.lead_id != lead.id:
                raise AppError(
                    code="OUTREACH_NOT_FOUND",
                    message="That outreach could not be found.",
                    status_code=404,
                )
            prior = self.session.scalar(
                select(LeadEmail).where(
                    LeadEmail.outreach_message_id == outreach.id,
                    LeadEmail.direction == EmailDirection.OUTBOUND.value,
                )
            )
            if prior is not None:
                return self._read(prior)

        attachments = self._load_attachments(
            lead.id,
            audit_id=data.attachment_audit_id,
            mockup_ids=data.attachment_mockup_ids,
        )
        access = self.accounts.access_token_for(account)
        try:
            sent = self.client.send_message(
                access,
                to=recipient,
                subject=data.subject,
                body_text=data.body,
                from_email=account.email,
                attachments=attachments,
            )
        except GmailApiError as exc:
            if exc.code == "GMAIL_UNAUTHORIZED":
                self.accounts._mark_needs_reauth(account, "Send rejected authorization.")
                raise AppError(
                    code="GMAIL_NEEDS_REAUTH",
                    message="Gmail authorization expired. Reconnect Gmail in Settings.",
                    status_code=409,
                ) from exc
            raise AppError(
                code="GMAIL_SEND_FAILED",
                message="Gmail accepted the connection but could not send this email.",
                status_code=502,
            ) from exc

        gmail_message_id = str(sent.get("id") or "")
        gmail_thread_id = str(sent.get("threadId") or "")
        if not gmail_message_id or not gmail_thread_id:
            raise AppError(
                code="GMAIL_SEND_FAILED",
                message="Gmail did not return a message id after sending.",
                status_code=502,
            )

        # Fetch the stored message for RFC Message-ID; send acceptance is not delivery proof.
        rfc_message_id = None
        try:
            parsed = self.client.get_message(access, gmail_message_id)
            rfc_message_id = parsed.rfc_message_id
        except GmailApiError:
            logger.warning("gmail_send_fetch_metadata_failed message_id=%s", gmail_message_id)

        now = datetime.now(UTC)
        row = LeadEmail(
            lead_id=lead.id,
            gmail_account_id=account.id,
            outreach_message_id=outreach.id if outreach else None,
            direction=EmailDirection.OUTBOUND.value,
            classification=EmailClassification.OUTGOING.value,
            recipient_email=recipient,
            sender_email=account.email,
            subject=data.subject,
            body_text=data.body,
            body_html=None,
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            rfc_message_id=rfc_message_id,
            occurred_at=now,
            is_unread=False,
            needs_review=False,
            idempotency_key=key,
        )
        self.session.add(row)
        lead.last_contacted_at = now
        self._advance_lead(lead, LeadStatus.CONTACTED)
        if outreach is not None:
            outreach.status = OutreachStatus.SENT.value
            outreach.sent_at = now
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "gmail_sent",
            "Email sent via Gmail",
            description=data.subject,
            details={
                "gmail_message_id": gmail_message_id,
                "gmail_thread_id": gmail_thread_id,
                "recipient": recipient,
            },
        )
        self.session.commit()
        logger.info(
            "gmail_sent account_id=%s lead_id=%s message_id=%s",
            account.id,
            lead.id,
            gmail_message_id,
        )
        return self._read(row)

    def reply(
        self,
        lead_id: UUID,
        email_id: UUID,
        data: LeadEmailReplyRequest,
        *,
        idempotency_key: str | None = None,
    ) -> LeadEmailRead:
        lead = self._require_lead(lead_id)
        self._assert_can_send(lead)
        parent = self.session.get(LeadEmail, email_id)
        if parent is None or parent.lead_id != lead.id:
            raise AppError(
                code="EMAIL_NOT_FOUND",
                message="That email could not be found.",
                status_code=404,
            )
        key = idempotency_key or data.idempotency_key
        if key:
            existing = self.session.scalar(
                select(LeadEmail).where(LeadEmail.idempotency_key == key)
            )
            if existing is not None:
                return self._read(existing)

        account = self.accounts.require_active_account()
        if parent.gmail_account_id != account.id:
            raise AppError(
                code="GMAIL_ACCOUNT_MISMATCH",
                message="That conversation belongs to a different Gmail account.",
                status_code=409,
            )

        if parent.direction == EmailDirection.INBOUND.value:
            recipient = parent.sender_email
        else:
            recipient = parent.recipient_email
        recipient = (recipient or lead.email or "").strip().lower()
        if not recipient:
            raise AppError(
                code="EMAIL_RECIPIENT_REQUIRED",
                message="Could not determine the reply recipient.",
                status_code=422,
            )
        subject = data.subject or parent.subject or ""
        if subject and not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        references = " ".join(
            part
            for part in [parent.references_header or "", parent.rfc_message_id or ""]
            if part
        ).strip() or None
        access = self.accounts.access_token_for(account)
        try:
            sent = self.client.send_message(
                access,
                to=recipient,
                subject=subject or "Re:",
                body_text=data.body,
                from_email=account.email,
                thread_id=parent.gmail_thread_id,
                in_reply_to=parent.rfc_message_id,
                references=references,
            )
        except GmailApiError as exc:
            if exc.code == "GMAIL_UNAUTHORIZED":
                self.accounts._mark_needs_reauth(account, "Reply rejected authorization.")
                raise AppError(
                    code="GMAIL_NEEDS_REAUTH",
                    message="Gmail authorization expired. Reconnect Gmail in Settings.",
                    status_code=409,
                ) from exc
            raise AppError(
                code="GMAIL_SEND_FAILED",
                message="Gmail could not send this reply.",
                status_code=502,
            ) from exc

        gmail_message_id = str(sent.get("id") or "")
        gmail_thread_id = str(sent.get("threadId") or parent.gmail_thread_id)
        rfc_message_id = None
        try:
            parsed = self.client.get_message(access, gmail_message_id)
            rfc_message_id = parsed.rfc_message_id
        except GmailApiError:
            logger.warning("gmail_reply_fetch_metadata_failed message_id=%s", gmail_message_id)

        now = datetime.now(UTC)
        row = LeadEmail(
            lead_id=lead.id,
            gmail_account_id=account.id,
            direction=EmailDirection.OUTBOUND.value,
            classification=EmailClassification.OUTGOING.value,
            recipient_email=recipient,
            sender_email=account.email,
            subject=subject,
            body_text=data.body,
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            rfc_message_id=rfc_message_id,
            in_reply_to=parent.rfc_message_id,
            references_header=references,
            occurred_at=now,
            idempotency_key=key,
        )
        self.session.add(row)
        lead.last_contacted_at = now
        self._advance_lead(lead, LeadStatus.CONTACTED)
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "gmail_replied",
            "Reply sent via Gmail",
            description=subject,
            details={"gmail_message_id": gmail_message_id, "thread_id": gmail_thread_id},
        )
        self.session.commit()
        return self._read(row)

    def _assert_can_send(self, lead: Lead) -> None:
        if lead.do_not_contact or lead.lead_status == LeadStatus.DO_NOT_CONTACT.value:
            raise AppError(
                code="DO_NOT_CONTACT",
                message="This lead is marked do not contact.",
                status_code=409,
            )

    def _advance_lead(self, lead: Lead, target: LeadStatus) -> None:
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

    def _load_attachments(
        self,
        lead_id: UUID,
        *,
        audit_id: UUID | None,
        mockup_ids: list[UUID],
    ) -> list[GmailAttachment]:
        attachments: list[GmailAttachment] = []
        if audit_id is not None:
            audit = self.session.get(WebsiteAudit, audit_id)
            if audit is None or audit.lead_id != lead_id:
                raise AppError(
                    code="AUDIT_NOT_FOUND",
                    message="That audit could not be found.",
                    status_code=404,
                )
            variant = "desktop" if audit.desktop_screenshot_url else "mobile"
            relative = audit.desktop_screenshot_url or audit.mobile_screenshot_url
            content = read_screenshot(
                self.settings.storage_dir,
                relative,
                audit.raw_analysis,
                variant,
            )
            if content:
                attachments.append(
                    GmailAttachment(
                        filename=f"audit-{audit.id}.png",
                        content_type="image/png",
                        content=self._limit_attachment(content),
                    )
                )
        for mockup_id in mockup_ids:
            mockup = self.session.get(Mockup, mockup_id)
            if mockup is None or mockup.lead_id != lead_id:
                raise AppError(
                    code="MOCKUP_NOT_FOUND",
                    message="That mockup could not be found.",
                    status_code=404,
                )
            if mockup.status != MockupStatus.READY.value:
                raise AppError(
                    code="MOCKUP_NOT_READY",
                    message="Only ready mockups can be attached to email.",
                    status_code=409,
                )
            lead = self.session.get(Lead, lead_id)
            slug = _safe_filename(lead.business_name if lead else "mockup")
            attached = False
            for variant, relative in (
                ("desktop", mockup.desktop_image_url or mockup.image_url or mockup.thumbnail_url),
                ("mobile", mockup.mobile_image_url),
            ):
                if not relative:
                    continue
                path = resolve_storage_path(self.settings.storage_dir, relative)
                if not path.is_file():
                    continue
                attachments.append(
                    GmailAttachment(
                        filename=f"{slug}-mockup-v{mockup.version}-{variant}.png",
                        content_type="image/png",
                        content=self._limit_attachment(self._read_attachment_bytes(path)),
                    )
                )
                attached = True
            if not attached:
                raise AppError(
                    code="MOCKUP_SCREENSHOT_MISSING",
                    message=(
                        "That mockup has no screenshot to attach yet. "
                        "Open the mockup and retry screenshot capture first."
                    ),
                    status_code=409,
                )
        return attachments

    def _read_attachment_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def _limit_attachment(self, content: bytes) -> bytes:
        if len(content) > 20 * 1024 * 1024:
            raise AppError(
                code="ATTACHMENT_TOO_LARGE",
                message="Attachments must be under 20 MB.",
                status_code=413,
            )
        return content

    def _require_lead(self, lead_id: UUID) -> Lead:
        lead = self.leads.get(lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )
        return lead

    def _read(self, row: LeadEmail) -> LeadEmailRead:
        return LeadEmailRead(
            id=row.id,
            lead_id=row.lead_id,
            gmail_account_id=row.gmail_account_id,
            outreach_message_id=row.outreach_message_id,
            direction=row.direction,
            classification=row.classification,
            recipient_email=row.recipient_email,
            sender_email=row.sender_email,
            subject=row.subject,
            body_text=row.body_text,
            body_html=sanitize_email_html(row.body_html),
            gmail_message_id=row.gmail_message_id,
            gmail_thread_id=row.gmail_thread_id,
            rfc_message_id=row.rfc_message_id,
            occurred_at=row.occurred_at,
            is_unread=row.is_unread,
            needs_review=row.needs_review,
            created_at=row.created_at,
        )


def _safe_filename(value: str | None) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-" for char in (value or "mockup")
    )
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned[:48] or "mockup").lower()
