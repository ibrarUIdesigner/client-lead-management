"""Central Lead Intelligence Layer.

Unifies Business data, Website Audits, Market Research, Signals, and Opportunities
into a cohesive sales intelligence model. Formulates the shared sales strategy that
drives both Mockup generation and Outreach email copywriting in lockstep.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import AuditStatus, MockupStatus, OutreachStatus, ResearchStatus
from app.models.followup import Followup
from app.models.gmail import LeadEmail
from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.models.website_audit import WebsiteAudit
from app.services.opportunity_engine import (
    Opportunity,
    OpportunityEngine,
    OpportunityScoreResult,
)
from app.services.signals import Signal, SignalDetector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NextAction:
    action: str
    reason: str
    confidence: float
    cta_label: str
    target_tab: str  # "overview" | "audit" | "research" | "mockups" | "outreach"
    priority: str  # "critical" | "high" | "medium" | "low"
    draft_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "cta_label": self.cta_label,
            "target_tab": self.target_tab,
            "priority": self.priority,
            "draft_available": self.draft_available,
        }


@dataclass(frozen=True)
class SalesStrategy:
    primary_opportunity: str
    recommended_framework: str  # "mockup_led" | "audit_led" | "research_led" | "opportunity_led"
    mockup_focus: str
    outreach_angle: str
    suggested_offer: str
    settled_price: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_opportunity": self.primary_opportunity,
            "recommended_framework": self.recommended_framework,
            "mockup_focus": self.mockup_focus,
            "outreach_angle": self.outreach_angle,
            "suggested_offer": self.suggested_offer,
            "settled_price": self.settled_price,
        }


@dataclass(frozen=True)
class LeadIntelligence:
    lead_id: str
    business_name: str
    industry: str | None
    location: str | None
    website_url: str | None
    has_website: bool
    lead_status: str
    opportunity_score: OpportunityScoreResult
    signals: list[Signal]
    opportunities: list[Opportunity]
    strategy: SalesStrategy
    next_action: NextAction
    audit_summary: dict[str, Any] | None
    research_summary: dict[str, Any] | None
    mockup_status: str | None
    latest_mockup_id: str | None
    outreach_status: str | None
    conversation_summary: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "business_name": self.business_name,
            "industry": self.industry,
            "location": self.location,
            "website_url": self.website_url,
            "has_website": self.has_website,
            "lead_status": self.lead_status,
            "opportunity_score": self.opportunity_score.to_dict(),
            "signals": [s.to_dict() for s in self.signals],
            "opportunities": [o.to_dict() for o in self.opportunities],
            "strategy": self.strategy.to_dict(),
            "next_action": self.next_action.to_dict(),
            "audit_summary": self.audit_summary,
            "research_summary": self.research_summary,
            "mockup_status": self.mockup_status,
            "latest_mockup_id": self.latest_mockup_id,
            "outreach_status": self.outreach_status,
            "conversation_summary": self.conversation_summary,
        }


class LeadIntelligenceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.signal_detector = SignalDetector()
        self.opportunity_engine = OpportunityEngine()

    def get_intelligence(self, lead_id: UUID) -> LeadIntelligence:
        lead = self.session.get(Lead, lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )

        # Retrieve related data
        audit = self._get_latest_audit(lead_id)
        research = self._get_research(lead_id)
        mockup = self._get_latest_mockup(lead_id)
        latest_message = self._get_latest_outreach(lead_id)
        latest_email = self._get_latest_email(lead_id)
        followups = self._get_open_followups(lead_id)

        # 1. Detect Signals
        signals = self.signal_detector.detect_all(lead, audit, research)

        # 2. Extract Opportunities
        opportunities = self.opportunity_engine.analyze_opportunities(
            lead, signals, audit, research
        )

        # 3. Calculate Explainable Opportunity Score
        score = self.opportunity_engine.calculate_score(lead, signals, audit, research)

        # Update lead_score on model if out of sync
        if lead.lead_score != score.total_score:
            lead.lead_score = score.total_score

        # 4. Formulate Unified Sales Strategy (connecting Mockup & Outreach)
        strategy = self._formulate_strategy(lead, signals, opportunities, mockup)

        # 5. Formulate Next Best Action
        next_action = self._formulate_next_action(
            lead=lead,
            audit=audit,
            research=research,
            mockup=mockup,
            latest_message=latest_message,
            latest_email=latest_email,
            followups=followups,
            strategy=strategy,
        )

        # Format summaries
        has_website = bool(lead.website_url) and lead.website_status != "missing"
        loc = ", ".join(part for part in (lead.city, lead.country) if part and part.strip())

        audit_summary = None
        if audit:
            audit_summary = {
                "id": str(audit.id),
                "status": audit.status,
                "overall_score": audit.overall_score,
                "performance_score": audit.performance_score,
                "mobile_score": audit.mobile_score,
                "ux_score": audit.ux_score,
                "issues_count": len(audit.issues) if isinstance(audit.issues, list) else 0,
            }

        research_summary = None
        if research:
            research_summary = {
                "id": str(research.id),
                "status": research.status,
                "summary": research.summary,
                "has_opportunities": bool(
                    isinstance(research.research_data, dict)
                    and research.research_data.get("high_impact_opportunities")
                ),
            }

        conversation_summary = None
        if latest_email:
            conversation_summary = {
                "latest_direction": latest_email.direction,
                "classification": latest_email.classification,
                "subject": latest_email.subject,
                "occurred_at": latest_email.occurred_at.isoformat(),
                "is_unread": latest_email.is_unread,
            }

        return LeadIntelligence(
            lead_id=str(lead.id),
            business_name=lead.business_name,
            industry=lead.industry,
            location=loc or None,
            website_url=lead.website_url,
            has_website=has_website,
            lead_status=lead.lead_status or "NEW",
            opportunity_score=score,
            signals=signals,
            opportunities=opportunities,
            strategy=strategy,
            next_action=next_action,
            audit_summary=audit_summary,
            research_summary=research_summary,
            mockup_status=mockup.status if mockup else None,
            latest_mockup_id=str(mockup.id) if mockup else None,
            outreach_status=latest_message.status if latest_message else None,
            conversation_summary=conversation_summary,
        )

    def _formulate_strategy(
        self,
        lead: Lead,
        signals: list[Signal],
        opportunities: list[Opportunity],
        mockup: Mockup | None,
    ) -> SalesStrategy:
        sig_names = {s.name for s in signals}
        has_website = bool(lead.website_url) and lead.website_status != "missing"

        # Determine framework and angles
        if not has_website:
            framework = "opportunity_led"
            primary_opp = "No official website found; business is missing searchers and quote requests."
            mockup_focus = "Create complete single-page digital storefront with high-visibility contact capture."
            outreach_angle = "Offer to build a clean, modern digital presence for a flat $850."
            suggested_offer = (
                f"I can create a professional website for {lead.business_name}, with a clear homepage "
                "and a simple way for customers to get in touch. The settled price for that first site is $850."
            )
            price = 850
        elif mockup and mockup.status == MockupStatus.READY.value:
            framework = "mockup_led"
            primary_opp = opportunities[0].problem if opportunities else "Website needs clear conversion path."
            mockup_focus = "Showcase generated homepage concept with sticky booking and verified customer reviews."
            outreach_angle = "Present the custom homepage concept specifically created for their business."
            suggested_offer = (
                f"I created a quick homepage concept for {lead.business_name} showing how your services "
                "could be positioned with a cleaner mobile booking path."
            )
            price = 750
        elif "SLOW_WEBSITE" in sig_names or "POOR_MOBILE_UX" in sig_names:
            framework = "audit_led"
            primary_opp = "Mobile performance delay and layout friction hurt visitor retention."
            mockup_focus = "Fast-loading mobile-first layout with instant touch-friendly call/quote buttons."
            outreach_angle = "Cite specific mobile load time and button friction observed during the audit."
            suggested_offer = (
                f"I can optimize {lead.business_name}'s website so mobile visitors find services quickly "
                "and reach out without friction. The settled price for this repair is $750."
            )
            price = 750
        elif "MISSING_BOOKING" in sig_names or "WEAK_SERVICE_PRESENTATION" in sig_names:
            framework = "research_led"
            primary_opp = "Appointment-driven customer action is not supported or services are buried."
            mockup_focus = "Prominent online scheduling section and dedicated featured service cards."
            outreach_angle = "Highlight modern booking expectations seen across regional competitors."
            suggested_offer = (
                f"I can update {lead.business_name}'s homepage to feature a direct booking workflow. "
                "The settled price is $750."
            )
            price = 750
        else:
            framework = "problem_solution"
            primary_opp = opportunities[0].problem if opportunities else "General conversion refresh opportunity."
            mockup_focus = "Modernized hero with clear primary action and proof points."
            outreach_angle = "Direct observation of clarity improvements for their homepage."
            suggested_offer = (
                f"I can tighten {lead.business_name}'s homepage to make the next step obvious for customers. "
                "The settled price for this refresh is $550."
            )
            price = 550

        return SalesStrategy(
            primary_opportunity=primary_opp,
            recommended_framework=framework,
            mockup_focus=mockup_focus,
            outreach_angle=outreach_angle,
            suggested_offer=suggested_offer,
            settled_price=price,
        )

    def _formulate_next_action(
        self,
        lead: Lead,
        audit: WebsiteAudit | None,
        research: LeadResearch | None,
        mockup: Mockup | None,
        latest_message: OutreachMessage | None,
        latest_email: LeadEmail | None,
        followups: list[Followup],
        strategy: SalesStrategy,
    ) -> NextAction:
        now = datetime.now(UTC)

        # 1. Unread Inbound Reply (Highest Priority)
        if lead.email_unread or (latest_email and latest_email.is_unread):
            cls = latest_email.classification if latest_email else "HUMAN_REPLY"
            return NextAction(
                action="Respond to Inbound Reply",
                reason=f"Prospect sent a reply classified as '{cls}'. Respond promptly to maintain momentum.",
                confidence=0.98,
                cta_label="Open Conversation & Review Suggested Draft",
                target_tab="outreach",
                priority="critical",
                draft_available=True,
            )

        # 2. Closed / Won / Do Not Contact
        if lead.lead_status == "WON":
            return NextAction(
                action="Deliver Services & Onboarding",
                reason="Deal closed successfully. Deliver agreed website scope and cultivate client relationship.",
                confidence=1.0,
                cta_label="View Client Record",
                target_tab="overview",
                priority="low",
            )
        if lead.lead_status in {"LOST", "DO_NOT_CONTACT"} or lead.do_not_contact:
            return NextAction(
                action="Archived / Closed",
                reason="Lead marked as closed or flagged Do Not Contact. No outreach required.",
                confidence=1.0,
                cta_label="View Details",
                target_tab="overview",
                priority="low",
            )

        # 3. Scheduled / Due Follow-up
        due_followup = next(
            (f for f in followups if f.scheduled_for <= now or f.status == "DUE"),
            None,
        )
        if due_followup or (lead.next_followup_at and lead.next_followup_at <= now):
            return NextAction(
                action="Send Scheduled Follow-up",
                reason="Follow-up check-in is due today. Sequence-based re-engagement increases reply rate.",
                confidence=0.92,
                cta_label="Review & Send Follow-up",
                target_tab="outreach",
                priority="high",
                draft_available=True,
            )

        # 4. Outreach Draft Waiting for Human Review
        if latest_message and latest_message.status in {OutreachStatus.DRAFT.value, OutreachStatus.READY.value}:
            return NextAction(
                action="Review & Approve Email Draft",
                reason=f"Outreach draft generated using '{strategy.recommended_framework}' framework awaiting approval.",
                confidence=0.95,
                cta_label="Review Draft",
                target_tab="outreach",
                priority="high",
                draft_available=True,
            )

        # 5. Mockup Ready -> Draft Outreach
        if mockup and mockup.status == MockupStatus.READY.value and not latest_message:
            return NextAction(
                action="Draft Mockup-Led Outreach",
                reason="Custom homepage concept is ready. Draft cold email citing the mockup.",
                confidence=0.94,
                cta_label="Draft Personalized Email",
                target_tab="outreach",
                priority="high",
            )

        # 6. Research Complete (or No Website) -> Generate Mockup
        has_website = bool(lead.website_url) and lead.website_status != "missing"
        research_done = research and research.status == ResearchStatus.COMPLETED.value
        audit_done = audit and audit.status == AuditStatus.COMPLETED.value

        if (not has_website or (audit_done and research_done)) and (not mockup or mockup.status != MockupStatus.READY.value):
            return NextAction(
                action="Generate Concept Mockup",
                reason=f"Intelligence gathered. Generate customized homepage concept focusing on {strategy.mockup_focus}.",
                confidence=0.90,
                cta_label="Generate Mockup",
                target_tab="mockups",
                priority="high",
            )

        # 7. Audit Done -> Run Lead Research
        if audit_done and not research_done:
            return NextAction(
                action="Research Business & Competitors",
                reason="Audit complete. Gather market context and competitor gaps with Tavily/Exa.",
                confidence=0.88,
                cta_label="Run Research",
                target_tab="research",
                priority="medium",
            )

        # 8. Has Website -> Run Website Audit
        if has_website and not audit_done:
            return NextAction(
                action="Run Website Audit",
                reason="Initiate Chromium deep audit to uncover mobile speed, CTA, and UX bottlenecks.",
                confidence=0.85,
                cta_label="Start Audit",
                target_tab="audit",
                priority="medium",
            )

        # Default: Qualify & Plan
        return NextAction(
            action="Qualify Lead & Formulate Strategy",
            reason="Review business details and initiate intelligence gathering.",
            confidence=0.80,
            cta_label="Inspect Lead",
            target_tab="overview",
            priority="medium",
        )

    def _get_latest_audit(self, lead_id: UUID) -> WebsiteAudit | None:
        statement = (
            select(WebsiteAudit)
            .where(WebsiteAudit.lead_id == lead_id)
            .order_by(WebsiteAudit.created_at.desc())
        )
        rows = list(self.session.scalars(statement))
        return rows[0] if rows else None

    def _get_research(self, lead_id: UUID) -> LeadResearch | None:
        statement = select(LeadResearch).where(LeadResearch.lead_id == lead_id)
        return self.session.scalar(statement)

    def _get_latest_mockup(self, lead_id: UUID) -> Mockup | None:
        statement = (
            select(Mockup)
            .where(Mockup.lead_id == lead_id)
            .order_by(Mockup.created_at.desc())
        )
        rows = list(self.session.scalars(statement))
        return rows[0] if rows else None

    def _get_latest_outreach(self, lead_id: UUID) -> OutreachMessage | None:
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.lead_id == lead_id)
            .order_by(OutreachMessage.created_at.desc())
        )
        rows = list(self.session.scalars(statement))
        return rows[0] if rows else None

    def _get_latest_email(self, lead_id: UUID) -> LeadEmail | None:
        statement = (
            select(LeadEmail)
            .where(LeadEmail.lead_id == lead_id)
            .order_by(LeadEmail.occurred_at.desc())
        )
        rows = list(self.session.scalars(statement))
        return rows[0] if rows else None

    def _get_open_followups(self, lead_id: UUID) -> list[Followup]:
        statement = (
            select(Followup)
            .where(
                Followup.lead_id == lead_id,
                Followup.status.in_(["SCHEDULED", "DUE"]),
            )
            .order_by(Followup.scheduled_for.asc())
        )
        return list(self.session.scalars(statement))
