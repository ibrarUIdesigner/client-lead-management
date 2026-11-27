"""Learn from results and shift effort toward what works, slowly and with guardrails.

What counts as success: positive replies, interested prospects, meetings and clients.
Opens and clicks are never used. Each sent email earns points for the best thing that
came of it, and a market, angle or writing style is judged by points per email sent.

Guardrails (all of them on purpose):
  - Nothing moves until enough emails exist: 30 in total, 15 for the thing being judged.
  - A thing with too little data drifts back toward neutral instead of keeping a guess.
  - Each daily update changes any multiplier by at most 10 percent.
  - Multipliers stay between 0.5 and 2.0.
  - Discovery always keeps an exploration share, and you can pin or avoid anything.
  - Setting ``learning_enabled`` off freezes every multiplier at neutral.

The multipliers are stored in ``app_settings`` and every change is kept in a short
history so the page can say what moved and why.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.automation import OutreachAttempt
from app.services.automation_config import AutomationConfig
from app.services.place_listings import category_label

logger = logging.getLogger(__name__)

KEY_STATE = "learning_state"
OUTCOME_POINTS = {"positive": 1.0, "interested": 2.0, "meeting": 4.0, "won": 10.0}
MIN_TOTAL_SENDS = 30
MIN_KEY_SENDS = 15
PRIOR_SENDS = 20
MAX_DAILY_STEP = 0.10
FACTOR_MIN, FACTOR_MAX = 0.5, 2.0
PIN_BOOST = 1.5
HISTORY_LIMIT = 30
KINDS = ("category", "country", "strategy", "tone", "style")


def norm(kind: str, value: str | None) -> str:
    text = (value or "").strip()
    if kind == "category":
        return category_label(text).casefold() if text else ""
    return text.casefold()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class LearningState:
    """Current multipliers. Anything not listed is neutral (1.0)."""

    factors: dict[str, dict[str, float]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    updated_on: str | None = None
    enabled: bool = True
    pinned_categories: frozenset[str] = frozenset()
    pinned_countries: frozenset[str] = frozenset()
    avoid_countries: frozenset[str] = frozenset()

    def factor(self, kind: str, value: str | None) -> float:
        key = norm(kind, value)
        pinned = (kind == "category" and key in self.pinned_categories) or (
            kind == "country" and key in self.pinned_countries
        )
        learned = self.factors.get(kind, {}).get(key, 1.0) if self.enabled else 1.0
        return max(learned, PIN_BOOST) if pinned else learned

    def market(self, category: str | None, country: str | None) -> float:
        """One multiplier for a category in a country (geometric mean, so neither counts twice)."""
        return math.sqrt(self.factor("category", category) * self.factor("country", country))


NEUTRAL = LearningState()


def state_from_config(stored: dict[str, Any] | None, config: AutomationConfig | None) -> LearningState:
    stored = stored or {}
    return LearningState(
        factors={k: {a: float(b) for a, b in v.items()} for k, v in stored.get("factors", {}).items()},
        history=list(stored.get("history", [])),
        updated_on=stored.get("updated_on"),
        enabled=True if config is None else config.learning_enabled,
        pinned_categories=frozenset(norm("category", c) for c in (config.pinned_categories if config else [])),
        pinned_countries=frozenset(norm("country", c) for c in (config.pinned_countries if config else [])),
        avoid_countries=frozenset(norm("country", c) for c in (config.excluded_countries if config else [])),
    )


def load_state(session: Session, config: AutomationConfig | None = None) -> LearningState:
    if config is None:
        from app.services.automation_config import get_config

        config = get_config(session)
    row = session.get(AppSetting, KEY_STATE)
    return state_from_config(row.value if row is not None and isinstance(row.value, dict) else None, config)


# ----------------------------------------------------------------------- the data


@dataclass
class _Cohort:
    sent: int = 0
    points: float = 0.0


def _points(outcome: str) -> float:
    return OUTCOME_POINTS.get(outcome, 0.0)


def gather(session: Session) -> tuple[dict[str, dict[str, _Cohort]], _Cohort]:
    """Points and sends for every category, country, angle, tone and style (first emails only)."""
    rows = session.execute(
        select(
            OutreachAttempt.category,
            OutreachAttempt.country,
            OutreachAttempt.strategy,
            OutreachAttempt.framework,
            OutreachAttempt.outcome,
            func.count(),
        )
        .where(OutreachAttempt.kind == "first")
        .group_by(
            OutreachAttempt.category,
            OutreachAttempt.country,
            OutreachAttempt.strategy,
            OutreachAttempt.framework,
            OutreachAttempt.outcome,
        )
    ).all()
    cohorts: dict[str, dict[str, _Cohort]] = {kind: {} for kind in KINDS}
    overall = _Cohort()
    for category, country, strategy, framework, outcome, count in rows:
        count = int(count)
        points = _points(outcome) * count
        overall.sent += count
        overall.points += points
        tone, _, style = (framework or "").partition("/")
        for kind, value in (
            ("category", category),
            ("country", country),
            ("strategy", strategy),
            ("tone", tone),
            ("style", style if style and style != "default" else ""),
        ):
            key = norm(kind, value)
            if not key:
                continue
            cohort = cohorts[kind].setdefault(key, _Cohort())
            cohort.sent += count
            cohort.points += points
    return cohorts, overall


def target_factor(cohort: _Cohort, overall_rate: float) -> float:
    """Where this thing's multiplier is heading. Neutral until there is enough evidence."""
    if cohort.sent < MIN_KEY_SENDS or overall_rate <= 0:
        return 1.0
    smoothed = (cohort.points + PRIOR_SENDS * overall_rate) / (cohort.sent + PRIOR_SENDS)
    return _clamp(smoothed / overall_rate, FACTOR_MIN, FACTOR_MAX)


def step_toward(current: float, target: float) -> float:
    """Move at most 10 percent per update."""
    if current <= 0:
        current = 1.0
    ratio = _clamp(target / current, 1 - MAX_DAILY_STEP, 1 + MAX_DAILY_STEP)
    return _clamp(current * ratio, FACTOR_MIN, FACTOR_MAX)


def update_learning(session: Session, config: AutomationConfig, today: date | None = None) -> dict[str, Any]:
    """Run once a day. Returns a summary of what moved."""
    today = today or datetime.now(UTC).date()
    if not config.learning_enabled:
        return {"status": "off"}
    cohorts, overall = gather(session)
    if overall.sent < MIN_TOTAL_SENDS:
        return {
            "status": "waiting for data",
            "sent": overall.sent,
            "needed": MIN_TOTAL_SENDS,
        }
    overall_rate = overall.points / overall.sent
    row = session.get(AppSetting, KEY_STATE)
    stored = row.value if row is not None and isinstance(row.value, dict) else {}
    previous: dict[str, dict[str, float]] = {k: dict(v) for k, v in stored.get("factors", {}).items()}
    history: list[dict[str, Any]] = list(stored.get("history", []))

    factors: dict[str, dict[str, float]] = {}
    moves: list[dict[str, Any]] = []
    for kind in KINDS:
        keys = set(cohorts[kind]) | set(previous.get(kind, {}))
        factors[kind] = {}
        for key in keys:
            current = previous.get(kind, {}).get(key, 1.0)
            cohort = cohorts[kind].get(key, _Cohort())
            new = step_toward(current, target_factor(cohort, overall_rate))
            if abs(new - 1.0) < 0.005 and key not in previous.get(kind, {}):
                continue
            factors[kind][key] = round(new, 4)
            if abs(new - current) >= 0.01:
                moves.append(
                    {
                        "date": today.isoformat(),
                        "kind": kind,
                        "name": key,
                        "from": round(current, 2),
                        "to": round(new, 2),
                        "sent": cohort.sent,
                        "points": round(cohort.points, 1),
                    }
                )
    history = (moves + history)[:HISTORY_LIMIT]
    payload = {"factors": factors, "history": history, "updated_on": today.isoformat()}
    if row is None:
        session.add(AppSetting(key=KEY_STATE, value=payload))
    else:
        row.value = payload
    session.flush()
    return {"status": "updated", "sent": overall.sent, "moves": len(moves)}


def maybe_update_learning(session_factory: Any, config: AutomationConfig, now: datetime | None = None) -> str:
    """Once a day, at most. Safe to call on every tick."""
    from app.models.enums import AutomationRunStatus
    from app.services.automation_config import claim_run, finish_run

    now = now or datetime.now(UTC)
    day = now.date()
    with session_factory() as session:
        run = claim_run(session, "learning", f"learning:{day.isoformat()}", now)
        if run is None:
            session.commit()
            return "already ran today"
        try:
            summary = update_learning(session, config, day)
            finish_run(session, run, AutomationRunStatus.OK, summary=summary)
            result = str(summary["status"])
        except Exception as exc:
            logger.exception("learning_update_failed")
            finish_run(session, run, AutomationRunStatus.FAILED, error=str(exc) or "Learning failed.")
            result = "failed"
        session.commit()
    return result


# ------------------------------------------------------------------------ choices


def weighted_choice(options: tuple[str, ...], weights: list[float], u: float) -> str:
    """Pick by weight using a fixed random number ``u`` in [0, 1), so the pick is repeatable."""
    total = sum(weights)
    point = u * total
    running = 0.0
    for option, weight in zip(options, weights, strict=True):
        running += weight
        if point < running:
            return option
    return options[-1]


def summary_for_ui(state: LearningState, limit: int = 6) -> dict[str, Any]:
    """The strongest and weakest multipliers and the latest moves, for the Automation page."""
    flat = [
        {"kind": kind, "name": name, "factor": factor}
        for kind, values in state.factors.items()
        for name, factor in values.items()
        if abs(factor - 1.0) >= 0.02
    ]
    flat.sort(key=lambda item: item["factor"], reverse=True)
    return {
        "enabled": state.enabled,
        "updated_on": state.updated_on,
        "boosted": [f for f in flat if f["factor"] > 1.0][:limit],
        "reduced": [f for f in reversed(flat) if f["factor"] < 1.0][:limit],
        "recent_moves": state.history[:10],
        "min_total_sends": MIN_TOTAL_SENDS,
        "min_key_sends": MIN_KEY_SENDS,
    }
