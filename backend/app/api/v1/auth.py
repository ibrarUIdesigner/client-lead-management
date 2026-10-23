import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
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
def login(data: LoginRequest, request: Request) -> LoginResponse:
    settings: Settings = request.app.state.settings
    req_email = data.email.strip().lower()
    cfg_email = settings.auth_email.strip().lower()

    if req_email != cfg_email or data.password != settings.auth_password:
        raise AppError(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
            status_code=401,
        )

    token = create_access_token(req_email, settings)
    return LoginResponse(access_token=token, email=req_email)


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


@router.post("/logout")
def logout() -> dict[str, bool]:
    return {"success": True}
