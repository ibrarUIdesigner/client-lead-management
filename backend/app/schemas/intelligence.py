"""Pydantic schemas for Lead Intelligence, Signals, Opportunities, and Next Best Action."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SignalRead(BaseModel):
    name: str
    type: str
    source: str
    confidence: float
    evidence: str
    detected_at: str


class OpportunityRead(BaseModel):
    problem: str
    evidence: str
    source: str
    recommended_solution: str
    impact: str
    confidence: float


class ScoreFactorRead(BaseModel):
    label: str
    points: int
    category: str
    reason: str


class OpportunityScoreRead(BaseModel):
    total_score: int
    tier: str
    tier_label: str
    breakdown: list[ScoreFactorRead]


class SalesStrategyRead(BaseModel):
    primary_opportunity: str
    recommended_framework: str
    mockup_focus: str
    outreach_angle: str
    suggested_offer: str
    settled_price: int


class NextActionRead(BaseModel):
    action: str
    reason: str
    confidence: float
    cta_label: str
    target_tab: str
    priority: str
    draft_available: bool = False


class LeadIntelligenceRead(BaseModel):
    lead_id: str
    business_name: str
    industry: str | None = None
    location: str | None = None
    website_url: str | None = None
    has_website: bool
    lead_status: str
    opportunity_score: OpportunityScoreRead
    signals: list[SignalRead]
    opportunities: list[OpportunityRead]
    strategy: SalesStrategyRead
    next_action: NextActionRead
    audit_summary: dict[str, Any] | None = None
    research_summary: dict[str, Any] | None = None
    mockup_status: str | None = None
    latest_mockup_id: str | None = None
    outreach_status: str | None = None
    conversation_summary: dict[str, Any] | None = None
