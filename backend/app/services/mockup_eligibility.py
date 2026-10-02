"""Rules for when a lead may receive a homepage mockup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.errors import AppError
from app.models.enums import AuditStatus
from app.models.lead import Lead
from app.models.website_audit import WebsiteAudit

DESIGN_SCORE_LIMIT = 50
MockupReason = Literal["no_website", "weak_design", "blocked"]


@dataclass(frozen=True)
class MockupEligibility:
    allowed: bool
    reason: MockupReason
    message: str
    design_score: int | None = None
    has_website: bool = False

    @property
    def scenario(self) -> Literal["new_site", "redesign"]:
        return "new_site" if self.reason == "no_website" else "redesign"


def lead_has_public_website(lead: Lead) -> bool:
    url = (lead.website_url or "").strip()
    if not url:
        return False
    status = (lead.website_status or "").strip().lower()
    if status in {"missing", "social_only"}:
        return False
    return True


def evaluate_mockup_eligibility(
    lead: Lead,
    audit: WebsiteAudit | None,
) -> MockupEligibility:
    """Mockups are for missing websites, or existing sites with design score under 50."""
    if not lead_has_public_website(lead):
        return MockupEligibility(
            allowed=True,
            reason="no_website",
            message=(
                "This business has no website. Generate a homepage from the verified "
                "business details."
            ),
            has_website=False,
        )

    if audit is None or audit.status != AuditStatus.COMPLETED.value:
        return MockupEligibility(
            allowed=False,
            reason="blocked",
            message=(
                "This business has a website. Run a completed audit first. "
                f"Mockups are only offered when the design score is below {DESIGN_SCORE_LIMIT}."
            ),
            has_website=True,
        )

    score = audit.design_score
    if score is None:
        return MockupEligibility(
            allowed=False,
            reason="blocked",
            message=(
                "The latest audit has no design score yet. Re-run the audit, then try again "
                f"if the design score is below {DESIGN_SCORE_LIMIT}."
            ),
            has_website=True,
        )

    if score < DESIGN_SCORE_LIMIT:
        return MockupEligibility(
            allowed=True,
            reason="weak_design",
            message=(
                f"Design score is {score}/100. Generate a clearer homepage mockup for outreach."
            ),
            design_score=score,
            has_website=True,
        )

    return MockupEligibility(
        allowed=False,
        reason="blocked",
        message=(
            f"Design score is {score}/100. Mockups are only created when there is no website, "
            f"or the design score is below {DESIGN_SCORE_LIMIT}."
        ),
        design_score=score,
        has_website=True,
    )


def require_mockup_eligibility(lead: Lead, audit: WebsiteAudit | None) -> MockupEligibility:
    result = evaluate_mockup_eligibility(lead, audit)
    if not result.allowed:
        raise AppError(
            code="MOCKUP_NOT_ELIGIBLE",
            message=result.message,
            status_code=409,
            details={
                "reason": result.reason,
                "design_score": result.design_score,
                "has_website": result.has_website,
                "limit": DESIGN_SCORE_LIMIT,
            },
        )
    return result
