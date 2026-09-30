from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import LeadStatus
from app.schemas.contacts import ContactRead
from app.schemas.values import EMAIL_RE, URL_RE, normalize_tags

URL_FIELDS = (
    "website_url",
    "linkedin_url",
    "instagram_url",
    "facebook_url",
    "google_maps_url",
)


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class LeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    business_name: str = Field(min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=120)
    description: str | None = None
    country: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    website_url: str | None = None
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    linkedin_url: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    google_maps_url: str | None = None
    lead_status: LeadStatus = LeadStatus.NEW
    source: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator(
        "industry",
        "description",
        "country",
        "city",
        "website_url",
        "email",
        "phone",
        "linkedin_url",
        "instagram_url",
        "facebook_url",
        "google_maps_url",
        "source",
        "notes",
        mode="before",
    )
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is not None and EMAIL_RE.fullmatch(value) is None:
            raise ValueError("Enter a valid email.")
        return value

    @field_validator(*URL_FIELDS)
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is not None and URL_RE.match(value) is None:
            raise ValueError("Start the address with http:// or https://.")
        return value

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class LeadUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=120)
    description: str | None = None
    country: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    website_url: str | None = None
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    linkedin_url: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    google_maps_url: str | None = None
    lead_status: LeadStatus | None = None
    source: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = None
    notes: str | None = None

    @field_validator(
        "industry",
        "description",
        "country",
        "city",
        "website_url",
        "email",
        "phone",
        "linkedin_url",
        "instagram_url",
        "facebook_url",
        "google_maps_url",
        "source",
        "notes",
        mode="before",
    )
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is not None and EMAIL_RE.fullmatch(value) is None:
            raise ValueError("Enter a valid email.")
        return value

    @field_validator(*URL_FIELDS)
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is not None and URL_RE.match(value) is None:
            raise ValueError("Start the address with http:// or https://.")
        return value

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_tags(value)


class LeadStatusUpdate(BaseModel):
    lead_status: LeadStatus


class BulkLeadUpdate(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=100)
    lead_status: LeadStatus | None = None
    add_tags: list[str] = Field(default_factory=list)

    @field_validator("add_tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.lead_status is None and not self.add_tags:
            raise ValueError("Choose a status or at least one tag.")
        return self


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_name: str
    slug: str | None
    industry: str | None
    description: str | None
    country: str | None
    city: str | None
    website_url: str | None
    website_status: str | None
    website_quality_score: int | None
    email: str | None
    phone: str | None
    linkedin_url: str | None
    instagram_url: str | None
    facebook_url: str | None
    google_maps_url: str | None
    lead_score: int | None
    lead_status: str
    source: str | None
    tags: list[str]
    notes: str | None
    last_contacted_at: datetime | None
    next_followup_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def tags_list(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    type: str
    title: str
    description: str | None
    details: dict[str, object] | None
    created_at: datetime


class LeadDetail(LeadRead):
    contacts: list[ContactRead]
    activities: list[ActivityRead]


class CsvPreviewRow(BaseModel):
    row_number: int
    business_name: str
    industry: str | None = None
    city: str | None = None
    country: str | None = None
    website_url: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class InvalidCsvRow(BaseModel):
    row_number: int
    message: str


class LeadImportResult(BaseModel):
    dry_run: bool
    created: int
    valid_rows: list[CsvPreviewRow]
    invalid_rows: list[InvalidCsvRow]


class BulkLeadResult(BaseModel):
    items: list[LeadRead]
