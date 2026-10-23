"""Sales knowledge loader and manager.

Loads markdown playbooks from backend/app/sales/ and provides structured
guidelines and prompts to agentic services (Scout, Writer, Handler, Strategist).
Automatically refreshes when files on disk are modified.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SALES_DIR = Path(__file__).resolve().parent.parent / "sales"

_BANNED_WORDS = [
    "i hope this email finds you well",
    "in today's fast-paced digital world",
    "game-changer",
    "game changer",
    "synergy",
    "cutting-edge",
    "cutting edge",
    "unleash",
    "streamline",
    "leverage",
    "delve",
    "robust",
    "transformative",
    "bespoke",
    "spearhead",
    "revolutionary",
]


class KnowledgeService:
    def __init__(self, sales_dir: Path | None = None) -> None:
        self.sales_dir = sales_dir or SALES_DIR
        self._cache: dict[str, tuple[float, str]] = {}

    def get_playbook(self, filename: str) -> str:
        """Load a markdown playbook by filename with mtime-based cache invalidation."""
        path = self.sales_dir / filename
        if not path.is_file():
            logger.warning("Sales playbook not found at %s", path)
            return ""

        try:
            mtime = path.stat().st_mtime
            cached = self._cache.get(filename)
            if cached is not None and cached[0] == mtime:
                return cached[1]

            content = path.read_text(encoding="utf-8")
            self._cache[filename] = (mtime, content)
            return content
        except Exception as exc:
            logger.error("Failed to read playbook %s: %s", filename, exc)
            return ""

    def list_playbooks(self) -> list[str]:
        """List all available markdown playbook filenames."""
        if not self.sales_dir.is_dir():
            return []
        return sorted([p.name for p in self.sales_dir.glob("*.md")])

    def get_email_frameworks(self) -> str:
        return self.get_playbook("EmailFrameworks.md")

    def get_signal_playbook(self) -> str:
        return self.get_playbook("SignalPlaybook.md")

    def get_lead_qualification(self) -> str:
        return self.get_playbook("LeadQualification.md")

    def get_objection_handling(self) -> str:
        return self.get_playbook("ObjectionHandling.md")

    def get_followup_strategy(self) -> str:
        return self.get_playbook("FollowupStrategy.md")

    def get_offer_strategy(self) -> str:
        return self.get_playbook("OfferStrategy.md")

    @staticmethod
    def get_banned_words() -> list[str]:
        return list(_BANNED_WORDS)

    def format_framework_context(self, framework_name: str | None = None) -> str:
        """Extract guidelines for email drafting prompts."""
        base = self.get_email_frameworks()
        banned_str = ", ".join(f'"{w}"' for w in _BANNED_WORDS)
        lines = [
            "=== SALES KNOWLEDGE & EMAIL FRAMEWORK DIRECTIVES ===",
            "Word count: Strictly between 50 and 85 words for initial outreach.",
            "Tone: Plain, professional human, calm, direct peer-to-peer. No hype, no fake enthusiasm.",
            f"BANNED WORDS AND PHRASES (strictly forbidden): {banned_str}.",
            "Call to action: Ask ONE low-friction question (e.g. 'Would you be open to taking a look?').",
        ]
        if framework_name:
            lines.append(f"Target Framework: {framework_name.upper()}")
        return "\n".join(lines)


# Default singleton instance for fast access across services
sales_knowledge = KnowledgeService()
