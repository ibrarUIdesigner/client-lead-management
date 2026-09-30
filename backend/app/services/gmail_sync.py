from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.integrations.gmail import (
    GmailApiError,
    GmailClient,
    ParsedGmailMessage,
    sanitize_email_html,
)
from app.models.enums import (
    EmailClassification,
    EmailDirection,
    FollowupStatus,
    GmailAccountStatus,
    LeadStatus,
    OutreachStatus,
)
from app.models.followup import Followup
from app.models.gmail import GmailAccount, LeadEmail
from app.models.lead import Lead
from app.models.outreach import OutreachMessage
from app.repositories.activities import ActivityRepository
from app.schemas.gmail import GmailSyncResult
from app.services.gmail_accounts import GmailAccountService
from app.services.gmail_classify import classify_inbound_message
from app.services.outreach_copy import next_lead_status
from app.services.persistence import flush_or_reject

logger = logging.getLogger(__name__)

_OPEN_FOLLOWUPS = {FollowupStatus.SCHEDULED.value, FollowupStatus.DUE.value}
_MSG_ID_RE = re.compile(r"<[^>]+>")


class GmailSyncService:
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
        self.activities = ActivityRepository(session)

    def sync_active_account(self) -> GmailSyncResult:
        account = self.accounts.get_active_account()
        if account is None or not account.sync_enabled:
            return GmailSyncResult()
        return self.sync_account(account)

    def sync_account(self, account: GmailAccount) -> GmailSyncResult:
        result = GmailSyncResult(account_email=account.email)
        try:
            access = self.accounts.access_token_for(account)
        except AppError as exc:
            if exc.code == "GMAIL_NEEDS_REAUTH":
                return result
            raise

        history_reset = False
        message_ids: list[str] = []
        latest_history_id = account.history_id

        if account.history_id:
            try:
                message_ids, latest_history_id = self._history_message_ids(
                    access,
                    start_history_id=account.history_id,
                )
            except GmailApiError as exc:
                if exc.status_code == 404 or exc.code == "GMAIL_NOT_FOUND":
                    logger.warning("gmail_history_expired account_id=%s", account.id)
                    history_reset = True
                    message_ids = self._recent_inbox_message_ids(access)
                    profile = self.client.get_profile(access)
                    latest_history_id = str(profile.get("historyId") or "") or account.history_id
                elif exc.code == "GMAIL_UNAUTHORIZED":
                    self.accounts._mark_needs_reauth(account, "Sync unauthorized.")
                    return result
                else:
                    account.last_error = "Sync failed talking to Gmail."
                    flush_or_reject(self.session)
                    raise AppError(
                        code="GMAIL_SYNC_FAILED",
                        message="Gmail sync failed. It will retry on the next interval.",
                        status_code=502,
                    ) from exc
        else:
            history_reset = True
            message_ids = self._recent_inbox_message_ids(access)
            profile = self.client.get_profile(access)
            latest_history_id = str(profile.get("historyId") or "") or None

        for message_id in message_ids:
            existing = self.session.scalar(
                select(LeadEmail).where(
                    LeadEmail.gmail_account_id == account.id,
                    LeadEmail.gmail_message_id == message_id,
                )
            )
            if existing is not None:
                result.skipped += 1
                continue
            try:
                parsed = self.client.get_message(access, message_id)
            except GmailApiError as exc:
                if exc.code == "GMAIL_UNAUTHORIZED":
                    self.accounts._mark_needs_reauth(account, "Message fetch unauthorized.")
                    break
                logger.warning("gmail_message_fetch_failed message_id=%s", message_id)
                continue
            try:
                with self.session.begin_nested():
                    outcome = self._process_message(account, parsed)
            except IntegrityError:
                logger.info("gmail_sync_duplicate_skipped message_id=%s", message_id)
                result.skipped += 1
                continue
            except AppError as exc:
                if exc.code == "VALIDATION_ERROR":
                    # Unique constraint surfaced through flush_or_reject.
                    logger.info("gmail_sync_duplicate_skipped message_id=%s", message_id)
                    result.skipped += 1
                    continue
                raise
            result.processed += 1
            if outcome == "matched":
                result.matched += 1
            elif outcome == "ambiguous":
                result.ambiguous += 1
            else:
                result.skipped += 1

        account.history_id = latest_history_id
        account.last_synced_at = datetime.now(UTC)
        account.last_error = None
        try:
            flush_or_reject(self.session)
            self.session.commit()
        except AppError:
            self.session.rollback()
            raise
        result.history_reset = history_reset
        logger.info(
            "gmail_sync_completed account_id=%s processed=%s matched=%s ambiguous=%s",
            account.id,
            result.processed,
            result.matched,
            result.ambiguous,
        )
        return result

    def _history_message_ids(
        self,
        access: str,
        *,
        start_history_id: str,
    ) -> tuple[list[str], str | None]:
        page_token: str | None = None
        ids: list[str] = []
        latest = start_history_id
        while True:
            payload = self.client.list_history(
                access,
                start_history_id=start_history_id,
                page_token=page_token,
            )
            for entry in payload.get("history") or []:
                if not isinstance(entry, dict):
                    continue
                for added in entry.get("messagesAdded") or []:
                    if not isinstance(added, dict):
                        continue
                    message = added.get("message") or {}
                    mid = message.get("id")
                    if isinstance(mid, str) and mid:
                        ids.append(mid)
            next_history = payload.get("historyId")
            if isinstance(next_history, str | int):
                latest = str(next_history)
            page_token = payload.get("nextPageToken")
            if not isinstance(page_token, str) or not page_token:
                break
        seen: set[str] = set()
        ordered: list[str] = []
        for mid in ids:
            if mid in seen:
                continue
            seen.add(mid)
            ordered.append(mid)
        return ordered, latest

    def _recent_inbox_message_ids(self, access: str) -> list[str]:
        payload = self.client.list_messages(access, query="newer_than:14d", max_results=100)
        ids: list[str] = []
        for item in payload.get("messages") or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.append(item["id"])
        return ids

    def _process_message(self, account: GmailAccount, parsed: ParsedGmailMessage) -> str:
        if not parsed.gmail_message_id or not parsed.gmail_thread_id:
            return "skipped"

        our_email = account.email.lower()
        sender = (parsed.sender_email or "").lower()
        is_ours = sender == our_email or "SENT" in parsed.label_ids

        # Persist our own outbound messages that were sent outside the app.
        if is_ours:
            return self._store_external_outbound(account, parsed)

        matches = self._match_leads(account.id, parsed)
        if len(matches) > 1:
            self._store_inbound(
                account,
                parsed,
                lead_id=None,
                classification=EmailClassification.AMBIGUOUS,
                needs_review=True,
            )
            return "ambiguous"
        if len(matches) == 0:
            return "skipped"

        lead_id = matches[0]
        classification = classify_inbound_message(
            subject=parsed.subject,
            body_text=parsed.body_text or parsed.snippet,
            sender_email=parsed.sender_email,
        ).classification
        self._store_inbound(
            account,
            parsed,
            lead_id=lead_id,
            classification=classification,
            needs_review=False,
        )
        self._apply_lead_effects(lead_id, classification, parsed)
        return "matched"

    def _match_leads(self, account_id: UUID, parsed: ParsedGmailMessage) -> list[UUID]:
        lead_ids: set[UUID] = set()

        by_thread = list(
            self.session.scalars(
                select(LeadEmail.lead_id).where(
                    LeadEmail.gmail_account_id == account_id,
                    LeadEmail.gmail_thread_id == parsed.gmail_thread_id,
                    LeadEmail.lead_id.is_not(None),
                )
            )
        )
        for lead_id in by_thread:
            if lead_id is not None:
                lead_ids.add(lead_id)

        ref_ids = _extract_message_ids(
            " ".join(part for part in [parsed.in_reply_to or "", parsed.references or ""] if part)
        )
        if ref_ids:
            referenced = list(
                self.session.scalars(
                    select(LeadEmail.lead_id).where(
                        LeadEmail.gmail_account_id == account_id,
                        LeadEmail.rfc_message_id.in_(ref_ids),
                        LeadEmail.lead_id.is_not(None),
                    )
                )
            )
            # References are supporting evidence: only keep leads already matched by thread,
            # or use references when thread has no prior lead email yet.
            if lead_ids:
                lead_ids = {item for item in referenced if item in lead_ids} or lead_ids
            else:
                for lead_id in referenced:
                    if lead_id is not None:
                        lead_ids.add(lead_id)

        return list(lead_ids)

    def _store_external_outbound(
        self,
        account: GmailAccount,
        parsed: ParsedGmailMessage,
    ) -> str:
        matches = self._match_leads(account.id, parsed)
        lead_id = matches[0] if len(matches) == 1 else None
        needs_review = len(matches) > 1
        row = LeadEmail(
            lead_id=lead_id,
            gmail_account_id=account.id,
            direction=EmailDirection.OUTBOUND.value,
            classification=(
                EmailClassification.AMBIGUOUS.value
                if needs_review
                else EmailClassification.OUTGOING.value
            ),
            recipient_email=parsed.recipient_email,
            sender_email=parsed.sender_email or account.email,
            subject=parsed.subject,
            body_text=parsed.body_text or parsed.snippet,
            body_html=sanitize_email_html(parsed.body_html),
            gmail_message_id=parsed.gmail_message_id,
            gmail_thread_id=parsed.gmail_thread_id,
            rfc_message_id=parsed.rfc_message_id,
            in_reply_to=parsed.in_reply_to,
            references_header=parsed.references,
            occurred_at=parsed.internal_date,
            is_unread=False,
            needs_review=needs_review,
        )
        self.session.add(row)
        self.session.flush()
        if lead_id is not None and not needs_review:
            lead = self.session.get(Lead, lead_id)
            if lead is not None:
                lead.last_contacted_at = parsed.internal_date
                self._advance(lead, LeadStatus.CONTACTED)
        if needs_review:
            return "ambiguous"
        return "matched" if lead_id else "skipped"

    def _store_inbound(
        self,
        account: GmailAccount,
        parsed: ParsedGmailMessage,
        *,
        lead_id: UUID | None,
        classification: EmailClassification,
        needs_review: bool,
    ) -> LeadEmail:
        row = LeadEmail(
            lead_id=lead_id,
            gmail_account_id=account.id,
            direction=EmailDirection.INBOUND.value,
            classification=classification.value,
            recipient_email=parsed.recipient_email or account.email,
            sender_email=parsed.sender_email,
            subject=parsed.subject,
            body_text=parsed.body_text or parsed.snippet,
            body_html=sanitize_email_html(parsed.body_html),
            gmail_message_id=parsed.gmail_message_id,
            gmail_thread_id=parsed.gmail_thread_id,
            rfc_message_id=parsed.rfc_message_id,
            in_reply_to=parsed.in_reply_to,
            references_header=parsed.references,
            occurred_at=parsed.internal_date,
            is_unread=classification == EmailClassification.HUMAN_REPLY,
            needs_review=needs_review,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def _apply_lead_effects(
        self,
        lead_id: UUID,
        classification: EmailClassification,
        parsed: ParsedGmailMessage,
    ) -> None:
        lead = self.session.get(Lead, lead_id)
        if lead is None:
            return

        if classification == EmailClassification.HUMAN_REPLY:
            lead.last_replied_at = parsed.internal_date
            lead.email_unread = True
            self._advance(lead, LeadStatus.REPLIED)
            self._pause_followups(lead, reason="Human reply received")
            self._mark_outreach_replied(lead.id, parsed)
            self.activities.add(
                lead.id,
                "gmail_human_reply",
                "Lead replied by email",
                description=parsed.subject,
            )
            return

        if classification == EmailClassification.OUT_OF_OFFICE:
            self.activities.add(
                lead.id,
                "gmail_out_of_office",
                "Out-of-office reply recorded",
                description=parsed.subject,
            )
            return

        if classification == EmailClassification.BOUNCE:
            failed = parsed.recipient_email or lead.email
            lead.email_suppressed = True
            lead.suppressed_email = failed
            self._mark_outreach_bounced(lead.id)
            self.activities.add(
                lead.id,
                "gmail_bounce",
                "Email bounce recorded",
                description=failed,
                details={"suppressed_email": failed},
            )
            return

        if classification == EmailClassification.OPT_OUT:
            lead.do_not_contact = True
            previous = lead.lead_status
            if previous not in {
                LeadStatus.WON.value,
                LeadStatus.LOST.value,
                LeadStatus.DO_NOT_CONTACT.value,
            }:
                lead.lead_status = LeadStatus.DO_NOT_CONTACT.value
                self.activities.add(
                    lead.id,
                    "status_changed",
                    "Status changed",
                    description=f"{previous} to {lead.lead_status}",
                    details={"from": previous, "to": lead.lead_status},
                )
            self._cancel_followups(lead, reason="Opt-out received")
            self.activities.add(
                lead.id,
                "gmail_opt_out",
                "Lead opted out of contact",
                description=parsed.subject,
            )

    def _pause_followups(self, lead: Lead, *, reason: str) -> None:
        # Pause pending follow-ups by cancelling open ones after a human reply.
        self._cancel_followups(lead, reason=reason)

    def _cancel_followups(self, lead: Lead, *, reason: str) -> None:
        rows = list(
            self.session.scalars(
                select(Followup).where(
                    Followup.lead_id == lead.id,
                    Followup.status.in_(_OPEN_FOLLOWUPS),
                )
            )
        )
        if not rows:
            return
        for row in rows:
            row.status = FollowupStatus.CANCELLED.value
        lead.next_followup_at = None
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "followup_cancelled",
            "Follow-ups cancelled",
            description=reason,
        )

    def _mark_outreach_replied(self, lead_id: UUID, parsed: ParsedGmailMessage) -> None:
        statement = (
            select(OutreachMessage)
            .where(
                OutreachMessage.lead_id == lead_id,
                OutreachMessage.status.in_(
                    [
                        OutreachStatus.SENT.value,
                        OutreachStatus.OPENED.value,
                    ]
                ),
            )
            .order_by(OutreachMessage.sent_at.desc())
        )
        message = self.session.scalars(statement).first()
        if message is None:
            return
        message.status = OutreachStatus.REPLIED.value
        message.replied_at = parsed.internal_date

    def _mark_outreach_bounced(self, lead_id: UUID) -> None:
        statement = (
            select(OutreachMessage)
            .where(
                OutreachMessage.lead_id == lead_id,
                OutreachMessage.status == OutreachStatus.SENT.value,
            )
            .order_by(OutreachMessage.sent_at.desc())
        )
        message = self.session.scalars(statement).first()
        if message is None:
            return
        message.status = OutreachStatus.BOUNCED.value

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


def sync_all_gmail_accounts(
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    session = session_factory()
    try:
        accounts = list(
            session.scalars(
                select(GmailAccount).where(
                    GmailAccount.status == GmailAccountStatus.ACTIVE.value,
                    GmailAccount.sync_enabled.is_(True),
                )
            )
        )
        for account in accounts:
            try:
                GmailSyncService(session, settings).sync_account(account)
            except Exception:
                logger.exception("gmail_sync_account_failed account_id=%s", account.id)
                session.rollback()
    finally:
        session.close()


def _extract_message_ids(header_value: str) -> list[str]:
    return [match.group(0) for match in _MSG_ID_RE.finditer(header_value)]
