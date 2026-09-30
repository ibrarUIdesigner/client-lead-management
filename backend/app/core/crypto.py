from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _fernet(settings: Settings) -> Fernet:
    key = (settings.token_encryption_key or "").strip()
    if not key:
        if settings.app_env == "production":
            raise AppError(
                code="TOKEN_ENCRYPTION_UNCONFIGURED",
                message="Set TOKEN_ENCRYPTION_KEY before connecting Gmail.",
                status_code=503,
            )
        # Deterministic local-only key so restarts can still decrypt tokens in development.
        digest = hashlib.sha256(b"client-acquisition-dev-token-key").digest()
        key = base64.urlsafe_b64encode(digest).decode("ascii")
        logger.warning("token_encryption_using_dev_key")
    try:
        return Fernet(key.encode("ascii") if isinstance(key, str) else key)
    except Exception as exc:
        # Accept raw 32-byte urlsafe base64 Fernet keys, or derive from any secret string.
        if len(key) == 44:
            raise AppError(
                code="TOKEN_ENCRYPTION_INVALID",
                message="TOKEN_ENCRYPTION_KEY must be a valid Fernet key.",
                status_code=503,
            ) from exc
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str, settings: Settings) -> str:
    return _fernet(settings).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str, settings: Settings) -> str:
    try:
        return _fernet(settings).decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            code="TOKEN_DECRYPT_FAILED",
            message="Stored Gmail credentials could not be decrypted. Reconnect Gmail.",
            status_code=503,
        ) from exc


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode("ascii")
