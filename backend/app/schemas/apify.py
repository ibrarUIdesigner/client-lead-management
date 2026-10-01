from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ACTOR_REF_RE_MESSAGE = "Enter an actor ID or owner/name."


class FieldOption(BaseModel):
    value: str
    label: str


class InputFieldRead(BaseModel):
    key: str
    label: str
    description: str | None = None
    field_type: Literal[
        "string",
        "text",
        "integer",
        "number",
        "boolean",
        "string_list",
        "url_list",
        "enum",
        "json",
        "hidden",
    ]
    required: bool = False
    default_value: Any = None
    options: list[FieldOption] | None = None
    minimum: float | None = None
    maximum: float | None = None
    section: str | None = None
    group: Literal["search", "limit", "other"] = "other"


class PricingRead(BaseModel):
    model: str
    label: str
    details: list[str]
    supports_max_charge: bool
    supports_max_items: bool
    minimal_max_total_charge_usd: float | None = None


class ApifyConnectorRead(BaseModel):
    id: UUID
    display_name: str
    source: str
    description: str | None
    actor_id: str
    last_run_at: datetime | None
    last_run_status: str | None
    has_active_run: bool
    pricing: PricingRead
    fields: list[InputFieldRead]


class ApifyConnectorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=200)

    @field_validator("display_name", "actor_id")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("Use letters, numbers, and regular punctuation.")
        return value


class ApifyRunCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    max_items: int | None = Field(default=None, ge=1, le=1_000_000)
    max_total_charge_usd: float | None = Field(default=None, gt=0, le=100_000)
    client_request_id: str | None = Field(default=None, min_length=8, max_length=64)

    @field_validator("client_request_id")
    @classmethod
    def request_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(not (char.isalnum() or char == "-") for char in value):
            raise ValueError("Use a request id made of letters, numbers, and dashes.")
        return value


class ApifyRunRead(BaseModel):
    id: UUID
    connector_id: UUID
    connector_name: str
    actor_id: str
    apify_run_id: str
    status: str
    status_message: str | None
    started_at: datetime
    finished_at: datetime | None
    result_count: int | None
    usage_total_usd: float | None
    max_items: int | None
    max_total_charge_usd: float | None


class ApifyOverview(BaseModel):
    token_configured: bool
    token_error: str | None = None
    connectors: list[ApifyConnectorRead]
    runs: list[ApifyRunRead]


class PreviewField(BaseModel):
    label: str
    value: str


class DatasetItemRead(BaseModel):
    item_key: str
    title: str
    source_url: str | None
    detail: str | None
    collected_at: datetime
    fields: list[PreviewField]


class DatasetPageRead(BaseModel):
    items: list[DatasetItemRead]
    offset: int
    limit: int
    total: int
    has_next: bool


class ApifyImportRequest(BaseModel):
    item_keys: list[str] = Field(min_length=1, max_length=200)

    @field_validator("item_keys")
    @classmethod
    def keys_are_present(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for key in value:
            text = key.strip()
            if not text or len(text) > 300:
                raise ValueError("Each selected record needs a valid key.")
            if text not in cleaned:
                cleaned.append(text)
        if not cleaned:
            raise ValueError("Select at least one record.")
        return cleaned


class ApifyImportResult(BaseModel):
    created: int
    skipped: int

    @classmethod
    def from_counts(cls, created: int, skipped: int) -> Self:
        return cls(created=created, skipped=skipped)
