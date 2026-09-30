from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.place_listings import category_is_valid


class DiscoverySearchCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=120)
    country: str = Field(min_length=2, max_length=120)
    use_openstreetmap: bool = True
    use_google: bool = True
    use_yelp: bool = True
    use_yell: bool = True
    use_businesslist: bool = True
    use_epages: bool = True

    @field_validator("category", "city", "country")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("Use letters, numbers, and regular punctuation.")
        return value

    @field_validator("category")
    @classmethod
    def known_category_shape(cls, value: str) -> str:
        if not category_is_valid(value):
            raise ValueError("Use letters, numbers, and regular punctuation.")
        return value

    @model_validator(mode="after")
    def require_source(self) -> Self:
        if not any(
            (
                self.use_openstreetmap,
                self.use_google,
                self.use_yelp,
                self.use_yell,
                self.use_businesslist,
                self.use_epages,
            )
        ):
            raise ValueError("Choose at least one source.")
        return self


class DiscoverySearchUpdate(BaseModel):
    is_active: bool | None = None
    use_openstreetmap: bool | None = None
    use_google: bool | None = None
    use_yelp: bool | None = None
    use_yell: bool | None = None
    use_businesslist: bool | None = None
    use_epages: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if all(
            value is None
            for value in (
                self.is_active,
                self.use_openstreetmap,
                self.use_google,
                self.use_yelp,
                self.use_yell,
                self.use_businesslist,
                self.use_epages,
            )
        ):
            raise ValueError("Choose what to change.")
        return self


class DiscoverySearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    city: str
    country: str
    is_active: bool
    use_openstreetmap: bool
    use_google: bool
    use_yelp: bool
    use_yell: bool
    use_businesslist: bool
    use_epages: bool
    created_at: datetime
    last_status: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_found_count: int | None = None
    last_created_count: int | None = None
    last_updated_count: int | None = None
    last_skipped_count: int | None = None
    last_message: str | None = None


class CategoryOption(BaseModel):
    value: str
    label: str


class DiscoveryStatus(BaseModel):
    running: bool
    google_configured: bool
    yelp_configured: bool
    schedule: str
    next_run_at: datetime | None
    categories: list[CategoryOption]
    searches: list[DiscoverySearchRead]
    latest_message: str | None = None


class DiscoveryRunStarted(BaseModel):
    started: bool
