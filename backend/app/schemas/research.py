from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchSource(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    highlights: list[str] | None = None
    provider: str  # "tavily" or "exa"
    score: float | None = None
    published_date: str | None = None


class StructuredResearchData(BaseModel):
    company_profile: str | None = None
    services_and_offerings: str | None = None
    pain_points_and_gaps: list[str] = Field(default_factory=list)
    digital_presence: str | None = None
    competitors_and_market: str | None = None
    recent_news: list[str] = Field(default_factory=list)
    proactive_solutions: list[str] = Field(default_factory=list)
    provider_used: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None


class LeadResearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    status: str
    query_used: str | None = None
    summary: str | None = None
    research_data: dict[str, object] | None = None
    sources: list[dict[str, object]] | None = None
    error_message: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LeadResearchTrigger(BaseModel):
    force_refresh: bool = False
    custom_query: str | None = None
    preferred_tool: str | None = None  # "tavily" or "exa" (defaults to tavily with exa fallback)
