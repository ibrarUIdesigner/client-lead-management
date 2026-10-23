from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import AppError


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(request: Request) -> str:
    settings = getattr(request.app.state, "settings", None)
    if settings is None or not getattr(settings, "auth_enabled", True) or getattr(settings, "app_env", "") == "test":
        return getattr(settings, "auth_email", "default")

    auth_header = request.headers.get("authorization")
    token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif request.cookies.get("clm_token"):
        token = request.cookies.get("clm_token")

    if not token:
        raise AppError(code="UNAUTHORIZED", message="Authentication required.", status_code=401)

    from app.api.v1.auth import verify_access_token

    return verify_access_token(token, settings)


CurrentUserDep = Annotated[str, Depends(get_current_user)]

