from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.values import EMAIL_RE, URL_RE


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class ContactCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    linkedin_url: str | None = None
    is_primary: bool = False

    @field_validator("job_title", "email", "phone", "linkedin_url", mode="before")
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is not None and EMAIL_RE.fullmatch(value) is None:
            raise ValueError("Enter a valid email.")
        return value

    @field_validator("linkedin_url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is not None and URL_RE.match(value) is None:
            raise ValueError("Start the address with http:// or https://.")
        return value


class ContactUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    job_title: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    linkedin_url: str | None = None
    is_primary: bool | None = None

    @field_validator("job_title", "email", "phone", "linkedin_url", mode="before")
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is not None and EMAIL_RE.fullmatch(value) is None:
            raise ValueError("Enter a valid email.")
        return value

    @field_validator("linkedin_url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is not None and URL_RE.match(value) is None:
            raise ValueError("Start the address with http:// or https://.")
        return value


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    name: str | None
    job_title: str | None
    email: str | None
    phone: str | None
    linkedin_url: str | None
    is_primary: bool
    created_at: datetime
    updated_at: datetime
