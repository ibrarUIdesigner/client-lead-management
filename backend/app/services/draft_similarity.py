"""Catch emails that read like the ones already sent."""

from __future__ import annotations

import re

SIMILAR_AT = 0.5
_WORD = re.compile(r"[a-z0-9']+")


def strip_signature(body: str) -> str:
    """Drop the contact block at the end, which is the same in every email."""
    blocks = [b for b in re.split(r"\n\s*\n", (body or "").strip()) if b.strip()]
    if len(blocks) > 2:
        last = blocks[-1]
        if len(last) < 300 and ("@" in last or "http" in last or "+" in last):
            blocks = blocks[:-1]
    return "\n\n".join(blocks)


def shingles(text: str, size: int = 4) -> set[tuple[str, ...]]:
    words = _WORD.findall(strip_signature(text).lower())
    if len(words) < size:
        return {tuple(words)} if words else set()
    return {tuple(words[i : i + size]) for i in range(len(words) - size + 1)}


def similarity(a: str, b: str) -> float:
    """Share of four-word phrases the two emails have in common (0 to 1)."""
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def most_similar(body: str, recent: list[str]) -> float:
    return max((similarity(body, other) for other in recent), default=0.0)
