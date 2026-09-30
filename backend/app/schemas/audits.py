from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    url: str | None
    status: str
    desktop_screenshot_url: str | None = Field(default=None, exclude=True)
    mobile_screenshot_url: str | None = Field(default=None, exclude=True)
    has_desktop_screenshot: bool = False
    has_mobile_screenshot: bool = False
    performance_score: int | None
    design_score: int | None
    mobile_score: int | None
    ux_score: int | None
    seo_score: int | None
    overall_score: int | None
    has_ssl: bool | None
    is_mobile_responsive: bool | None
    has_clear_cta: bool | None
    has_contact_form: bool | None
    has_social_proof: bool | None
    has_modern_navigation: bool | None
    issues: list[dict[str, object]]
    recommendations: list[dict[str, object]]
    raw_analysis: dict[str, object] | None
    completed_at: datetime | None
    created_at: datetime

    @field_validator("issues", "recommendations", mode="before")
    @classmethod
    def empty_list(cls, value: object) -> list[object]:
        if isinstance(value, list):
            return value
        return []

    @model_validator(mode="after")
    def screenshot_flags(self) -> Self:
        self.has_desktop_screenshot = bool(self.desktop_screenshot_url)
        self.has_mobile_screenshot = bool(self.mobile_screenshot_url)
        return self
