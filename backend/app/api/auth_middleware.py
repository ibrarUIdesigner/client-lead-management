"""Require a valid session on every API route except an explicit public list.

New routes are protected by default. Only the paths below are reachable without a
session: health checks, sign-in, cron routes (they check their own bearer secret),
the Gmail OAuth redirect (it validates its own state), and the public mockup page
that prospects open from an email.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.v1.auth import verify_access_token
from app.core.errors import AppError, error_body

API_PREFIX = "/api/v1"
PUBLIC_EXACT = {
    f"{API_PREFIX}/health",
    f"{API_PREFIX}/auth/login",
    f"{API_PREFIX}/auth/logout",
    f"{API_PREFIX}/gmail/oauth/callback",
}
PUBLIC_PREFIXES = (
    f"{API_PREFIX}/jobs/",
    f"{API_PREFIX}/m/",
    "/docs",
    "/openapi.json",
)


def is_public_path(path: str) -> bool:
    return path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES)


def _token_from(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return request.cookies.get("clm_token") or None


class RequireSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = request.app.state.settings
        if (
            request.method == "OPTIONS"
            or not settings.auth_enabled
            or settings.app_env == "test"
            or is_public_path(request.url.path)
        ):
            return await call_next(request)
        token = _token_from(request)
        try:
            if not token:
                raise AppError(
                    code="UNAUTHORIZED", message="Authentication required.", status_code=401
                )
            verify_access_token(token, settings)
        except AppError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=error_body(exc.code, exc.message, exc.details),
            )
        return await call_next(request)
