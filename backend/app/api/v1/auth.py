import hmac
import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, EmailStr

from app.core.config import Settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.errors import AppError

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class UserResponse(BaseModel):
    email: str
    authenticated: bool


def create_access_token(email: str, settings: Settings, expires_in_seconds: int = 86400 * 30) -> str:
    payload = {
        "email": email.strip().lower(),
        "exp": int(time.time()) + expires_in_seconds,
    }
    return encrypt_secret(json.dumps(payload), settings)


def verify_access_token(token: str, settings: Settings) -> str:
    try:
        raw = decrypt_secret(token, settings)
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Malformed payload")
        if data.get("exp", 0) < time.time():
            raise AppError(code="AUTH_EXPIRED", message="Session has expired. Please log in again.", status_code=401)
        email = data.get("email")
        if not email or not isinstance(email, str):
            raise ValueError("Missing email")
        return email
    except AppError:
        raise
    except Exception:
        raise AppError(code="AUTH_INVALID", message="Invalid authentication token.", status_code=401) from None


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request, response: Response) -> LoginResponse:
    settings: Settings = request.app.state.settings
    req_email = data.email.strip().lower()
    cfg_email = settings.auth_email.strip().lower()

    if not settings.auth_configured:
        raise AppError(
            code="AUTH_NOT_CONFIGURED",
            message="Set AUTH_PASSWORD in the server environment to enable sign-in.",
            status_code=503,
        )
    password_ok = hmac.compare_digest(
        data.password.encode("utf-8"), settings.auth_password.encode("utf-8")
    )
    if req_email != cfg_email or not password_ok:
        raise AppError(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
            status_code=401,
        )

    token = create_access_token(req_email, settings)
    # The cookie lets <img> tags load protected screenshots. The bearer token still
    # works for API calls.
    response.set_cookie(
        "clm_token",
        token,
        max_age=86400 * 30,
        httponly=True,
        secure=request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https",
        samesite="lax",
        path="/",
    )
    return LoginResponse(access_token=token, email=req_email)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie("clm_token", path="/")


@router.get("/me", response_model=UserResponse)
def get_me(request: Request, authorization: Annotated[str | None, Header()] = None) -> UserResponse:
    settings: Settings = request.app.state.settings
    if not settings.auth_enabled or settings.app_env == "test":
        return UserResponse(email=settings.auth_email, authenticated=True)

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise AppError(code="UNAUTHORIZED", message="Authentication required.", status_code=401)

    email = verify_access_token(token, settings)
    return UserResponse(email=email, authenticated=True)
