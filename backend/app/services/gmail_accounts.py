from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.errors import AppError
from app.integrations.gmail import GmailApiError, GmailClient, require_gmail_oauth_settings
from app.models.enums import GmailAccountStatus
from app.models.gmail import GmailAccount, GmailOAuthState
from app.schemas.gmail import GmailConnectStart, GmailStatusRead

logger = logging.getLogger(__name__)

_STATE_TTL = timedelta(minutes=15)
_TOKEN_SKEW = timedelta(minutes=2)


class GmailAccountService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        client: GmailClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.client = client or GmailClient(self.settings)

    def status(self) -> GmailStatusRead:
        account = self.get_active_account(include_needs_reauth=True)
        configured = self.settings.gmail_oauth_configured
        if account is None:
            return GmailStatusRead(configured=configured, connected=False)
        return GmailStatusRead(
            configured=configured,
            connected=account.status != GmailAccountStatus.DISCONNECTED.value,
            email=account.email,
            status=account.status,
            last_synced_at=account.last_synced_at,
            last_error=account.last_error,
            sync_enabled=account.sync_enabled,
            needs_reauth=account.status == GmailAccountStatus.NEEDS_REAUTH.value,
        )

    def start_connect(self) -> GmailConnectStart:
        require_gmail_oauth_settings(self.settings)
        self._purge_expired_states()
        state = secrets.token_urlsafe(32)
        self.session.add(
            GmailOAuthState(
                state=state,
                expires_at=datetime.now(UTC) + _STATE_TTL,
            )
        )
        self.session.flush()
        return GmailConnectStart(authorization_url=self.client.authorization_url(state))

    def complete_oauth(self, *, code: str | None, state: str | None, error: str | None) -> str:
        frontend = self.settings.gmail_frontend_redirect_url.rstrip("/")
        if error:
            logger.warning("gmail_oauth_denied")
            return f"{frontend}?gmail=denied"
        if not code or not state:
            return f"{frontend}?gmail=invalid"
        require_gmail_oauth_settings(self.settings)
        oauth_state = self.session.scalar(
            select(GmailOAuthState).where(GmailOAuthState.state == state)
        )
        if oauth_state is None or oauth_state.expires_at < datetime.now(UTC):
            logger.warning("gmail_oauth_state_invalid")
            return f"{frontend}?gmail=invalid_state"
        self.session.delete(oauth_state)
        try:
            tokens = self.client.exchange_code(code)
            email = self.client.fetch_profile_email(tokens.access_token)
            profile = self.client.get_profile(tokens.access_token)
            history_id = str(profile.get("historyId") or "") or None
        except GmailApiError:
            logger.warning("gmail_oauth_exchange_failed")
            return f"{frontend}?gmail=error"

        account = self.session.scalar(select(GmailAccount).where(GmailAccount.email == email))
        if account is None:
            account = GmailAccount(email=email)
            self.session.add(account)

        if not tokens.refresh_token and not account.encrypted_refresh_token:
            logger.warning("gmail_oauth_missing_refresh_token email=%s", email)
            return f"{frontend}?gmail=missing_refresh"

        account.status = GmailAccountStatus.ACTIVE.value
        account.sync_enabled = True
        account.last_error = None
        account.scopes = tokens.scopes
        account.token_expires_at = tokens.expires_at
        account.encrypted_access_token = encrypt_secret(tokens.access_token, self.settings)
        if tokens.refresh_token:
            account.encrypted_refresh_token = encrypt_secret(tokens.refresh_token, self.settings)
        if history_id:
            account.history_id = history_id
        self.session.flush()
        logger.info("gmail_connected account_id=%s", account.id)
        return f"{frontend}?gmail=connected"

    def disconnect(self) -> GmailStatusRead:
        account = self.get_active_account(include_needs_reauth=True)
        if account is None:
            return self.status()
        account.status = GmailAccountStatus.DISCONNECTED.value
        account.sync_enabled = False
        account.encrypted_access_token = None
        account.encrypted_refresh_token = None
        account.token_expires_at = None
        account.history_id = None
        account.last_error = None
        self.session.flush()
        logger.info("gmail_disconnected account_id=%s", account.id)
        return self.status()

    def get_active_account(self, *, include_needs_reauth: bool = False) -> GmailAccount | None:
        statuses = [GmailAccountStatus.ACTIVE.value]
        if include_needs_reauth:
            statuses.append(GmailAccountStatus.NEEDS_REAUTH.value)
        return self.session.scalar(
            select(GmailAccount)
            .where(GmailAccount.status.in_(statuses))
            .order_by(GmailAccount.updated_at.desc())
            .limit(1)
        )

    def require_active_account(self) -> GmailAccount:
        account = self.get_active_account(include_needs_reauth=True)
        if account is None or account.status == GmailAccountStatus.DISCONNECTED.value:
            raise AppError(
                code="GMAIL_NOT_CONNECTED",
                message="Connect Gmail in Settings before sending or syncing.",
                status_code=409,
            )
        if account.status == GmailAccountStatus.NEEDS_REAUTH.value:
            raise AppError(
                code="GMAIL_NEEDS_REAUTH",
                message="Gmail authorization expired. Reconnect Gmail in Settings.",
                status_code=409,
            )
        return account

    def access_token_for(self, account: GmailAccount) -> str:
        if not account.encrypted_access_token:
            self._mark_needs_reauth(account, "Missing access token.")
            raise AppError(
                code="GMAIL_NEEDS_REAUTH",
                message="Gmail authorization expired. Reconnect Gmail in Settings.",
                status_code=409,
            )
        access = decrypt_secret(account.encrypted_access_token, self.settings)
        expires = account.token_expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires is None or expires > datetime.now(UTC) + _TOKEN_SKEW:
            return access
        return self._refresh(account)

    def _refresh(self, account: GmailAccount) -> str:
        if not account.encrypted_refresh_token:
            self._mark_needs_reauth(account, "Missing refresh token.")
            raise AppError(
                code="GMAIL_NEEDS_REAUTH",
                message="Gmail authorization expired. Reconnect Gmail in Settings.",
                status_code=409,
            )
        refresh = decrypt_secret(account.encrypted_refresh_token, self.settings)
        try:
            tokens = self.client.refresh_access_token(refresh)
        except GmailApiError as exc:
            if exc.status_code == 400 or exc.code in {"OAUTH_TOKEN_FAILED", "GMAIL_UNAUTHORIZED"}:
                self._mark_needs_reauth(account, "Refresh token rejected.")
                raise AppError(
                    code="GMAIL_NEEDS_REAUTH",
                    message="Gmail authorization expired. Reconnect Gmail in Settings.",
                    status_code=409,
                ) from exc
            raise AppError(
                code="GMAIL_REFRESH_FAILED",
                message="Could not refresh the Gmail connection. Try again shortly.",
                status_code=502,
            ) from exc
        account.encrypted_access_token = encrypt_secret(tokens.access_token, self.settings)
        if tokens.refresh_token:
            account.encrypted_refresh_token = encrypt_secret(tokens.refresh_token, self.settings)
        account.token_expires_at = tokens.expires_at
        account.status = GmailAccountStatus.ACTIVE.value
        account.last_error = None
        self.session.flush()
        logger.info("gmail_token_refreshed account_id=%s", account.id)
        return tokens.access_token

    def _mark_needs_reauth(self, account: GmailAccount, reason: str) -> None:
        account.status = GmailAccountStatus.NEEDS_REAUTH.value
        account.last_error = reason
        account.sync_enabled = False
        self.session.flush()
        logger.warning("gmail_needs_reauth account_id=%s", account.id)

    def _purge_expired_states(self) -> None:
        expired = list(
            self.session.scalars(
                select(GmailOAuthState).where(GmailOAuthState.expires_at < datetime.now(UTC))
            )
        )
        for row in expired:
            self.session.delete(row)
