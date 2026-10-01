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

    @field_validator("requirements")
    @classmethod
    def plain_requirements(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _plain(value)


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
    design_guide_id: UUID | None
    design_guide_name: str | None
    prompt: str

    @classmethod
    def from_mockup(cls, mockup: object) -> Self:
        return cls.model_validate(mockup, from_attributes=True)
