"""The four outreach angles and the writing styles used to keep emails from sounding alike."""

from __future__ import annotations

import hashlib
from uuid import UUID

STRATEGY_GUIDANCE: dict[str, str] = {
    "no_website": (
        "ANGLE: this business has no website. Build the email around customers who look "
        "for them online and find nothing to click. If a mockup link is given, say you "
        "sketched a homepage for them and show the link. Do not claim to have reviewed a "
        "site, because there is none."
    ),
    "outdated": (
        "ANGLE: their website looks dated. Name ONE concrete design finding from the "
        "overview, and explain in plain words that visitors judge a business by how its "
        "site looks. Offer a modern homepage concept (link it if one is given). Never "
        "insult the current site."
    ),
    "slow": (
        "ANGLE: their website is slow or poor on phones. Quote the one measured number "
        "from the overview in plain words, and tie it to visitors leaving before they "
        "call or book. Offer a faster mobile-first page. Do not use technical jargon."
    ),
    "ux": (
        "ANGLE: visitors have trouble taking the next step (contacting or booking). Name "
        "ONE specific finding from the overview and describe what it costs the business "
        "in inquiries. Offer a clearer page with an obvious way to get in touch."
    ),
    "other": (
        "ANGLE: general improvement. Choose the single sharpest, verified point in the "
        "overview and build the email around it. Do not pad with generic claims."
    ),
}

STYLE_HINTS: dict[str, str] = {
    "question": "STYLE: open with a short question about how their customers find or reach them.",
    "observation": "STYLE: open with a one-line observation about their trade or area, then the point.",
    "finding": "STYLE: open directly with the specific finding, no warm-up sentence.",
    "mockup_first": "STYLE: open by saying you put together a quick concept for them. If no link is given, open with the finding instead.",
    "outcome": "STYLE: open with the result they could get (more calls, more bookings), then how.",
    "local": "STYLE: open with something local to their city or neighbourhood, then the point.",
}
STYLE_KEYS = tuple(STYLE_HINTS)
TONES = ("professional", "warm", "direct")


EXPLORE_SHARE = 0.25


def _pick(lead_id: UUID | str, learning: object | None, avoid: tuple[str, str] | None, salt: int) -> tuple[str, str]:
    digest = hashlib.sha256(f"{lead_id}:{salt}".encode("utf-8")).digest()
    tones = tuple(t for t in TONES if not avoid or t != avoid[0])
    styles = tuple(k for k in STYLE_KEYS if not avoid or k != avoid[1])
    if learning is None or getattr(learning, "enabled", True) is False:
        return tones[digest[0] % len(tones)], styles[digest[1] % len(styles)]
    from app.services.learning import weighted_choice

    # A quarter of picks ignore the results so every option keeps being tested.
    explore = digest[2] / 256 < EXPLORE_SHARE
    tone_weights = [1.0 if explore else learning.factor("tone", t) for t in tones]  # type: ignore[attr-defined]
    style_weights = [1.0 if explore else learning.factor("style", k) for k in styles]  # type: ignore[attr-defined]
    return (
        weighted_choice(tones, tone_weights, digest[0] / 256),
        weighted_choice(styles, style_weights, digest[1] / 256),
    )


def pick_variant(
    lead_id: UUID | str, *, shift: int = 0, learning: object | None = None
) -> tuple[str, str]:
    """A stable tone and style for this lead.

    Without learning the pick is spread evenly. With learning, tones and styles that earned
    more positive replies are chosen more often. ``shift`` asks for a retry: the tone and
    the style both differ from the first pick.
    """
    first = _pick(lead_id, learning, None, 0)
    if shift == 0:
        return first
    return _pick(lead_id, learning, first, shift)


def variant_label(tone: str, style: str | None) -> str:
    return f"{tone}/{style or 'default'}"[:32]
