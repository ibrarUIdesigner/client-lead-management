from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.design_markdown import normalize_guide_tags


def _plain(value: str) -> str:
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ValueError("Use letters, numbers, and regular punctuation.")
    return value


class DesignGuideWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=12)
    content: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def plain_name(cls, value: str) -> str:
        return _plain(value)

    @field_validator("description")
    @classmethod
    def plain_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _plain(value) or None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return normalize_guide_tags(value)

    @field_validator("content")
    @classmethod
    def content_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter the design guide.")
        return value.replace("\x00", "")


class DesignGuideSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    tags: list[str]
    updated_at: datetime


class DesignGuideRead(DesignGuideSummary):
    content: str
    created_at: datetime
    blocks: list[dict[str, object]]


class DesignGuideList(BaseModel):
    items: list[DesignGuideSummary]
    tags: list[str]


class DesignGuideTemplate(BaseModel):
    content: str
    blocks: list[dict[str, object]]


class MockupCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    lead_id: UUID
    requirements: str | None = Field(default=None, max_length=4000)
    source_mockup_id: UUID | None = None
    design_guide_id: UUID | None = None
    guide_mode: Literal["keep", "selected", "none"] = "none"
    provider: Literal["gemini", "groq"] = "gemini"
    goal: Literal["calls", "whatsapp", "bookings", "quotes"] = "calls"

    @field_validator("requirements")
    @classmethod
    def plain_requirements(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _plain(value)


class MockupRefine(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    instructions: str = Field(min_length=1, max_length=4000)
    provider: Literal["gemini", "groq"] | None = None

    @field_validator("instructions")
    @classmethod
    def plain_instructions(cls, value: str) -> str:
        return _plain(value)


class MockupRetry(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: Literal["gemini", "groq"]


class MockupEligibilityRead(BaseModel):
    lead_id: UUID
    allowed: bool
    reason: str
    message: str
    design_score: int | None = None
    has_website: bool = False
    limit: int = 50
    scenario: str | None = None


class MockupGuideRead(BaseModel):
    id: UUID
    design_guide_id: UUID | None
    design_guide_name: str | None
    design_guide_snapshot: str | None
    blocks: list[dict[str, object]]


class MockupCreated(BaseModel):
    id: UUID
    lead_id: UUID
    version: int
    status: str
    provider: str | None = None
    goal: str | None = None
    design_guide_id: UUID | None
    design_guide_name: str | None
    prompt: str | None = None

    @classmethod
    def from_mockup(cls, mockup: object) -> Self:
        return cls.model_validate(mockup, from_attributes=True)


class MockupDetail(BaseModel):
    id: UUID
    lead_id: UUID
    business_name: str | None = None
    title: str | None
    status: str
    version: int
    notes: str | None
    prompt: str | None
    provider: str | None
    model_name: str | None = None
    goal: str | None = None
    html_content: str | None = None
    preview_html: str | None = None
    asset_refs: list[dict[str, object]] | None = None
    source_mockup_id: UUID | None = None
    screenshot_status: str | None = None
    error_code: str | None = None
    has_html: bool = False
    has_desktop_screenshot: bool = False
    has_mobile_screenshot: bool = False
    design_guide_id: UUID | None
    design_guide_name: str | None
    completed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_mockup(
        cls,
        mockup: object,
        *,
        business_name: str | None = None,
        include_html: bool = False,
    ) -> Self:
        html = getattr(mockup, "html_content", None) if include_html else None
        preview = None
        if include_html and isinstance(html, str) and html.strip():
            from app.services.mockup_html import wrap_for_srcdoc

            preview = wrap_for_srcdoc(html)
        return cls(
            id=getattr(mockup, "id"),
            lead_id=getattr(mockup, "lead_id"),
            business_name=business_name,
            title=getattr(mockup, "title", None),
            status=getattr(mockup, "status"),
            version=getattr(mockup, "version"),
            notes=getattr(mockup, "notes", None),
            prompt=getattr(mockup, "prompt", None),
            provider=getattr(mockup, "provider", None),
            model_name=getattr(mockup, "model_name", None),
            goal=getattr(mockup, "goal", None),
            html_content=html if include_html else None,
            preview_html=preview,
            asset_refs=getattr(mockup, "asset_refs", None),
            source_mockup_id=getattr(mockup, "source_mockup_id", None),
            screenshot_status=getattr(mockup, "screenshot_status", None),
            error_code=getattr(mockup, "error_code", None),
            has_html=bool(getattr(mockup, "html_content", None)),
            has_desktop_screenshot=bool(getattr(mockup, "desktop_image_url", None)),
            has_mobile_screenshot=bool(getattr(mockup, "mobile_image_url", None)),
            design_guide_id=getattr(mockup, "design_guide_id", None),
            design_guide_name=getattr(mockup, "design_guide_name", None),
            completed_at=getattr(mockup, "completed_at", None),
            created_at=getattr(mockup, "created_at"),
        )
