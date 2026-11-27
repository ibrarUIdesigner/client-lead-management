"""Login-free pages that prospects open from emails."""

from fastapi import APIRouter, Request
from sqlalchemy import select
from starlette.responses import Response

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.models.enums import MockupStatus
from app.models.mockup import Mockup
from app.services.mockup_html import wrap_for_srcdoc

router = APIRouter(tags=["public"])


@router.get("/m/{token}")
def public_mockup(token: str, request: Request, session: SessionDep) -> Response:
    if not 16 <= len(token) <= 64:
        raise AppError(code="NOT_FOUND", message="That page could not be found.", status_code=404)
    mockup = session.scalar(select(Mockup).where(Mockup.public_token == token))
    if mockup is None or mockup.status != MockupStatus.READY.value or not mockup.html_content:
        raise AppError(code="NOT_FOUND", message="That page could not be found.", status_code=404)
    return Response(
        content=wrap_for_srcdoc(mockup.html_content).encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": (
                "default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; "
                "font-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            ),
            "Cache-Control": "private, max-age=300",
        },
    )
