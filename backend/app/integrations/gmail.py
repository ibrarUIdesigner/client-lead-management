from __future__ import annotations

import base64
import email.utils
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "email",
)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.code = code


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: str | None


@dataclass(frozen=True)
class GmailAttachment:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class ParsedGmailMessage:
    gmail_message_id: str
    gmail_thread_id: str
    rfc_message_id: str | None
    in_reply_to: str | None
    references: str | None
    subject: str | None
    sender_email: str | None
    recipient_email: str | None
    body_text: str | None
    body_html: str | None
    label_ids: tuple[str, ...]
    internal_date: datetime
    snippet: str | None


class GmailClient:
    """Thin Gmail REST client with retries and safe logging (no bodies/tokens)."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport

    def authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.google_oauth_client_id,
            "redirect_uri": self.settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> OAuthTokens:
        data = self._token_request(
            {
                "code": code,
                "client_id": self.settings.google_oauth_client_id,
                "client_secret": self.settings.google_oauth_client_secret,
                "redirect_uri": self.settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            }
        )
        return self._tokens_from_payload(data)

    def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        data = self._token_request(
            {
                "refresh_token": refresh_token,
                "client_id": self.settings.google_oauth_client_id,
                "client_secret": self.settings.google_oauth_client_secret,
                "grant_type": "refresh_token",
            }
        )
        tokens = self._tokens_from_payload(data)
        return OAuthTokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token or refresh_token,
            expires_at=tokens.expires_at,
            scopes=tokens.scopes,
        )

    def fetch_profile_email(self, access_token: str) -> str:
        payload = self._request("GET", USERINFO_URL, access_token=access_token)
        email = payload.get("email")
        if not isinstance(email, str) or "@" not in email:
            raise GmailApiError("Google account email was missing.", code="EMAIL_MISSING")
        return email.lower()

    def get_profile(self, access_token: str) -> dict[str, Any]:
        return self._request("GET", f"{GMAIL_API}/profile", access_token=access_token)

    def send_message(
        self,
        access_token: str,
        *,
        to: str,
        subject: str,
        body_text: str,
        from_email: str,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
        references: str | None = None,
        attachments: list[GmailAttachment] | None = None,
    ) -> dict[str, Any]:
        raw = self._build_raw_message(
            to=to,
            subject=subject,
            body_text=body_text,
            from_email=from_email,
            in_reply_to=in_reply_to,
            references=references,
            attachments=attachments or [],
        )
        payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        return self._request(
            "POST",
            f"{GMAIL_API}/messages/send",
            access_token=access_token,
            json_body=payload,
        )

    def list_history(
        self,
        access_token: str,
        *,
        start_history_id: str,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "startHistoryId": start_history_id,
            "historyTypes": "messageAdded",
        }
        if page_token:
            params["pageToken"] = page_token
        return self._request(
            "GET",
            f"{GMAIL_API}/history",
            access_token=access_token,
            params=params,
        )

    def list_messages(
        self,
        access_token: str,
        *,
        query: str | None = None,
        page_token: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {"maxResults": max_results}
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token
        return self._request(
            "GET",
            f"{GMAIL_API}/messages",
            access_token=access_token,
            params=params,
        )

    def get_message(self, access_token: str, message_id: str) -> ParsedGmailMessage:
        payload = self._request(
            "GET",
            f"{GMAIL_API}/messages/{message_id}",
            access_token=access_token,
            params={"format": "full"},
        )
        return parse_gmail_message(payload)

    def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            response = client.post(TOKEN_URL, data=form)
        if response.status_code >= 400:
            logger.warning("gmail_token_exchange_failed status=%s", response.status_code)
            raise GmailApiError(
                "Google authorization failed.",
                status_code=response.status_code,
                code="OAUTH_TOKEN_FAILED",
            )
        data = response.json()
        if not isinstance(data, dict):
            raise GmailApiError("Unexpected token response.", code="OAUTH_TOKEN_INVALID")
        return data

    def _tokens_from_payload(self, data: dict[str, Any]) -> OAuthTokens:
        access = data.get("access_token")
        if not isinstance(access, str) or not access:
            raise GmailApiError("Access token missing.", code="OAUTH_TOKEN_INVALID")
        refresh = data.get("refresh_token")
        expires_in = data.get("expires_in")
        expires_at = None
        if isinstance(expires_in, int | float):
            expires_at = datetime.now(UTC).replace(microsecond=0)
            expires_at = datetime.fromtimestamp(time.time() + float(expires_in), tz=UTC)
        scope = data.get("scope")
        return OAuthTokens(
            access_token=access,
            refresh_token=refresh if isinstance(refresh, str) else None,
            expires_at=expires_at,
            scopes=scope if isinstance(scope, str) else None,
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        access_token: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        retries = self.settings.gmail_api_max_retries
        delay = 1.0
        last_error: GmailApiError | None = None
        for attempt in range(retries):
            try:
                with httpx.Client(transport=self._transport, timeout=45.0) as client:
                    response = client.request(
                        method,
                        url,
                        headers={"Authorization": f"Bearer {access_token}"},
                        params=params,
                        json=json_body,
                    )
                if response.status_code == 401:
                    raise GmailApiError(
                        "Gmail authorization expired.",
                        status_code=401,
                        code="GMAIL_UNAUTHORIZED",
                    )
                if response.status_code == 404:
                    raise GmailApiError(
                        "Gmail resource not found.",
                        status_code=404,
                        code="GMAIL_NOT_FOUND",
                        retryable=False,
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    raise GmailApiError(
                        "Gmail API temporarily unavailable.",
                        status_code=response.status_code,
                        retryable=True,
                        code="GMAIL_RATE_LIMITED"
                        if response.status_code == 429
                        else "GMAIL_SERVER_ERROR",
                    )
                if response.status_code >= 400:
                    logger.warning(
                        "gmail_api_error method=%s status=%s",
                        method,
                        response.status_code,
                    )
                    raise GmailApiError(
                        "Gmail API request failed.",
                        status_code=response.status_code,
                        code="GMAIL_API_ERROR",
                    )
                data = response.json()
                if not isinstance(data, dict):
                    raise GmailApiError("Unexpected Gmail response.", code="GMAIL_API_ERROR")
                return data
            except GmailApiError as exc:
                last_error = exc
                if not exc.retryable or attempt >= retries - 1:
                    raise
                logger.info(
                    "gmail_api_retry attempt=%s status=%s",
                    attempt + 1,
                    exc.status_code,
                )
                time.sleep(delay)
                delay = min(delay * 2, 20.0)
            except httpx.HTTPError as exc:
                last_error = GmailApiError(
                    "Gmail network error.",
                    retryable=True,
                    code="GMAIL_NETWORK",
                )
                if attempt >= retries - 1:
                    raise last_error from exc
                time.sleep(delay)
                delay = min(delay * 2, 20.0)
        assert last_error is not None
        raise last_error

    def _build_raw_message(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        from_email: str,
        in_reply_to: str | None,
        references: str | None,
        attachments: list[GmailAttachment],
    ) -> str:
        if attachments:
            message: MIMEMultipart | MIMEText = MIMEMultipart()
            message.attach(MIMEText(body_text, "plain", "utf-8"))
            for item in attachments:
                part = MIMEApplication(item.content, Name=item.filename)
                part.add_header("Content-Disposition", "attachment", filename=item.filename)
                if item.content_type:
                    part.set_type(item.content_type)
                message.attach(part)
        else:
            message = MIMEText(body_text, "plain", "utf-8")
        message["To"] = to
        message["From"] = from_email
        message["Subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        return encoded.rstrip("=")


def parse_gmail_message(payload: dict[str, Any]) -> ParsedGmailMessage:
    headers = _header_map(payload)
    internal_ms = payload.get("internalDate")
    if isinstance(internal_ms, str) and internal_ms.isdigit():
        internal_date = datetime.fromtimestamp(int(internal_ms) / 1000, tz=UTC)
    elif isinstance(internal_ms, int | float):
        internal_date = datetime.fromtimestamp(float(internal_ms) / 1000, tz=UTC)
    else:
        internal_date = datetime.now(UTC)
    label_ids = payload.get("labelIds") or []
    labels = tuple(str(item) for item in label_ids if isinstance(item, str))
    text_body, html_body = _extract_bodies(payload.get("payload") or {})
    return ParsedGmailMessage(
        gmail_message_id=str(payload.get("id") or ""),
        gmail_thread_id=str(payload.get("threadId") or ""),
        rfc_message_id=_normalize_msg_id(headers.get("message-id")),
        in_reply_to=headers.get("in-reply-to"),
        references=headers.get("references"),
        subject=headers.get("subject"),
        sender_email=_extract_address(headers.get("from")),
        recipient_email=_extract_address(headers.get("to")),
        body_text=text_body,
        body_html=html_body,
        label_ids=labels,
        internal_date=internal_date,
        snippet=payload.get("snippet") if isinstance(payload.get("snippet"), str) else None,
    )


def _header_map(payload: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    payload_headers = (payload.get("payload") or {}).get("headers") or []
    if not isinstance(payload_headers, list):
        return headers
    for item in payload_headers:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if isinstance(name, str) and isinstance(value, str):
            headers[name.lower()] = value
    return headers


def _extract_address(value: str | None) -> str | None:
    if not value:
        return None
    _name, addr = email.utils.parseaddr(value)
    addr = addr.strip().lower()
    return addr or None


def _normalize_msg_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return cleaned
    if cleaned:
        return f"<{cleaned.strip('<>')}>"
    return None


def _extract_bodies(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    text_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = str(part.get("mimeType") or "")
        body = part.get("body") or {}
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, str) and data:
            decoded = _decode_body(data)
            if mime.startswith("text/plain"):
                text_parts.append(decoded)
            elif mime.startswith("text/html"):
                html_parts.append(decoded)
        for child in part.get("parts") or []:
            if isinstance(child, dict):
                walk(child)

    walk(payload)
    return (
        "\n".join(text_parts).strip() or None,
        "\n".join(html_parts).strip() or None,
    )


def _decode_body(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""


_SCRIPT_RE = re.compile(r"(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>")
_TAG_EVENT_RE = re.compile(r"(?i)\son[a-z]+\s*=")
_JS_URL_RE = re.compile(r"(?i)(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2")


def sanitize_email_html(html: str | None) -> str | None:
    if not html:
        return None
    cleaned = _SCRIPT_RE.sub("", html)
    cleaned = _TAG_EVENT_RE.sub(" ", cleaned)
    cleaned = _JS_URL_RE.sub("", cleaned)
    return cleaned.strip() or None


def require_gmail_oauth_settings(settings: Settings) -> None:
    if not settings.gmail_oauth_configured:
        raise AppError(
            code="GMAIL_OAUTH_UNCONFIGURED",
            message="Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET to connect Gmail.",
            status_code=503,
        )
