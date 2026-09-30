from uuid import UUID

from fastapi import APIRouter, Header
from fastapi.responses import RedirectResponse

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.schemas.gmail import (
    GmailConnectStart,
    GmailStatusRead,
    GmailSyncResult,
    LeadEmailRead,
    LeadEmailReplyRequest,
    LeadEmailSendRequest,
    LeadEmailThreadSummary,
)
from app.services.gmail_accounts import GmailAccountService
from app.services.gmail_mail import GmailMailService
from app.services.gmail_sync import GmailSyncService

router = APIRouter(tags=["gmail"])


@router.get("/gmail/status", response_model=GmailStatusRead)
def gmail_status(session: SessionDep) -> GmailStatusRead:
    return GmailAccountService(session).status()


@router.get("/gmail/oauth/start", response_model=GmailConnectStart)
def gmail_oauth_start(session: SessionDep) -> GmailConnectStart:
    return GmailAccountService(session).start_connect()


@router.get("/gmail/oauth/callback")
def gmail_oauth_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    url = GmailAccountService(session).complete_oauth(code=code, state=state, error=error)
    session.commit()
    return RedirectResponse(url=url, status_code=302)


@router.post("/gmail/disconnect", response_model=GmailStatusRead)
def gmail_disconnect(session: SessionDep) -> GmailStatusRead:
    return GmailAccountService(session).disconnect()


@router.post("/gmail/sync", response_model=GmailSyncResult)
def gmail_sync(session: SessionDep) -> GmailSyncResult:
    return GmailSyncService(session, get_settings()).sync_active_account()


@router.get("/leads/{lead_id}/emails", response_model=LeadEmailThreadSummary)
def list_lead_emails(lead_id: UUID, session: SessionDep) -> LeadEmailThreadSummary:
    return GmailMailService(session).list_for_lead(lead_id)


@router.post("/leads/{lead_id}/emails/mark-read", response_model=LeadEmailThreadSummary)
def mark_lead_emails_read(lead_id: UUID, session: SessionDep) -> LeadEmailThreadSummary:
    return GmailMailService(session).mark_read(lead_id)


@router.post("/leads/{lead_id}/emails/send", response_model=LeadEmailRead, status_code=201)
def send_lead_email(
    lead_id: UUID,
    data: LeadEmailSendRequest,
    session: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> LeadEmailRead:
    return GmailMailService(session).send(lead_id, data, idempotency_key=idempotency_key)


@router.post(
    "/leads/{lead_id}/emails/{email_id}/reply",
    response_model=LeadEmailRead,
    status_code=201,
)
def reply_lead_email(
    lead_id: UUID,
    email_id: UUID,
    data: LeadEmailReplyRequest,
    session: SessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> LeadEmailRead:
    return GmailMailService(session).reply(
        lead_id,
        email_id,
        data,
        idempotency_key=idempotency_key,
    )
