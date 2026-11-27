"""Decide whether a discovered business is worth keeping, and say why not if it is not."""

from __future__ import annotations

import re

from app.services.automation_config import AutomationConfig, ExclusionSet
from app.services.place_listings import FoundBusiness

REASON_LABELS = {
    "excluded": "On your do-not-contact list",
    "chain": "National chain",
    "no_contact": "No way to contact them",
    "not_preferred": "Not a preferred opportunity",
    "low_score": "Below the score threshold",
}

# Large chains and franchises. They do not buy a website from a freelancer.
_CHAINS = (
    "mcdonald",
    "starbucks",
    "subway",
    "kfc",
    "burger king",
    "domino",
    "pizza hut",
    "walmart",
    "walgreens",
    "cvs",
    "7-eleven",
    "costa coffee",
    "greggs",
    "tesco",
    "sainsbury",
    "dunkin",
    "wendy",
    "taco bell",
    "hilton",
    "marriott",
    "holiday inn",
    "hyatt",
    "best western",
    "planet fitness",
    "anytime fitness",
    "gold's gym",
    "h&r block",
    "re/max",
    "remax",
    "keller williams",
    "century 21",
    "coldwell banker",
    "jiffy lube",
    "midas",
    "nando",
    "pizza express",
)
_CHAIN_RE = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(name) for name in _CHAINS) + r")(?![a-z0-9])",
    re.IGNORECASE,
)


def is_chain(name: str) -> bool:
    return _CHAIN_RE.search(name or "") is not None


def reject_reason(
    business: FoundBusiness,
    config: AutomationConfig,
    exclusions: ExclusionSet,
) -> str | None:
    """None means keep. Otherwise a short code from REASON_LABELS."""
    if exclusions.match(
        name=business.name,
        website=business.website_url,
        email=business.email,
        category=business.industry,
    ):
        return "excluded"
    if is_chain(business.name):
        return "chain"
    if not (business.email or business.phone or business.website_url):
        return "no_contact"
    has_site = business.website_status == "present"
    wants = set(config.business_types)
    if wants:
        wants_no_site = "no_website" in wants
        wants_redesign = bool(wants & {"outdated", "slow", "ux"})
        if not has_site and not wants_no_site:
            return "not_preferred"
        if has_site and not wants_redesign:
            return "not_preferred"
    if business.lead_score < config.min_score:
        return "low_score"
    return None
