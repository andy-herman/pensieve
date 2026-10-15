"""Garden v1: derive per-card freshness and a single board-health score.

Pure-function module. No I/O, no global state. Called from the API layer
to enrich dashboard payloads (``freshness`` + ``is_overdue``) and to back
the ``GET /api/board/health`` endpoint.

Design notes (see ``brainstorms/02-board-tending-game.md`` + plan):
- Freshness is DERIVED from ``Memory.last_tended_at`` (backfilled to
  ``enriched_at`` when missing during reconstruction). It is NOT stored
  on the Memory model — keeps the schema clean of Garden concepts.
- "Tending" = a deliberate user action (column move, edit, vial post/skip,
  regenerate). Auto-sync must NEVER bump ``last_tended_at``.
- Closed cards are NEUTRAL freshness-wise. They get ``closed`` (no Vial yet,
  pending-closure-capture chevron is the signal) or ``closed_vialed`` (a
  CAPTURED Vial exists — skipped Vials do not earn this state).
- ``capture_pct`` in the health formula counts only CAPTURED Vials. Skipping
  every closure must not artificially inflate the score.
- ``clean_streak_d`` is wired through as a parameter but always 0 in v1.
  Real daily-snapshot streak tracking lands in v2 alongside quest state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal, Optional

from pensieve.store.schema import Memory

# --- thresholds (days since last_tended_at, for OPEN cards only) -------------
FRESH_MAX_DAYS = 3   # < 3d => fresh
ACTIVE_MAX_DAYS = 8  # 3..<8d => active
STALE_MAX_DAYS = 30  # 8..<=30d => stale; > 30d => ghost
GHOST_MIN_DAYS = 31  # documentation alias for > STALE_MAX_DAYS


FreshnessState = Literal[
    "fresh",
    "active",
    "stale",
    "ghost",
    "closed",
    "closed_vialed",
]


def _as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Coerce naive datetimes to aware UTC. Outlook can deliver naive values.

    Returns ``None`` unchanged. Naive datetimes are assumed UTC (best
    available guess; Outlook task dates land here as naive).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _now_utc(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return _as_aware_utc(now)  # type: ignore[return-value]


def _age_days(tended: Optional[datetime], now: datetime) -> Optional[int]:
    tended_aware = _as_aware_utc(tended)
    if tended_aware is None:
        return None
    delta = now - tended_aware
    return delta.days


def derive_freshness(
    memory: Memory,
    now: Optional[datetime] = None,
    *,
    has_captured_vial: bool = False,
) -> FreshnessState:
    """Return the per-card freshness state.

    ``has_captured_vial`` should be True iff the memory has at least one
    Vial with capture_kind == "captured" (NOT skipped).
    """
    now_u = _now_utc(now)
    if memory.column == "closed":
        return "closed_vialed" if has_captured_vial else "closed"

    tended = memory.last_tended_at or memory.enriched_at
    age = _age_days(tended, now_u)
    if age is None:
        return "active"  # fall-through; shouldn't happen post-backfill
    if age > STALE_MAX_DAYS:
        return "ghost"
    if age >= ACTIVE_MAX_DAYS:
        return "stale"
    if age >= FRESH_MAX_DAYS:
        return "active"
    return "fresh"


def is_overdue(memory: Memory, now: Optional[datetime] = None) -> bool:
    """True iff the card has a past due_date AND is still open."""
    if memory.due_date is None or memory.column == "closed":
        return False
    now_u = _now_utc(now)
    due = _as_aware_utc(memory.due_date)
    if due is None:
        return False
    return due < now_u


@dataclass
class HealthTerms:
    stale_pct: float
    stale_count: int
    ghost_count: int
    overdue_count: int
    capture_pct: float
    clean_streak_d: int
    quest_bonus: int


def compute_board_health(
    memories: Iterable[Memory],
    now: Optional[datetime] = None,
    *,
    captured_counts: Optional[dict[str, int]] = None,
    clean_streak_d: int = 0,
    quest_bonus: int = 0,
) -> dict:
    """Return ``{score, terms, counts, computed_at}``.

    Formula (clamped 0..100):
        100 - %open_stale*30 - overdue*5 - ghost*10
            + capture_pct*10 + clean_streak_d (cap 10) + quest_bonus

    ``captured_counts`` maps memory_id -> count of CAPTURED Vials.
    Skipped Vials are not counted (they do not earn capture credit).
    """
    captured_counts = captured_counts or {}
    now_u = _now_utc(now)
    mems = list(memories)

    open_mems = [m for m in mems if m.column != "closed"]
    closed_mems = [m for m in mems if m.column == "closed"]

    stale_count = 0
    ghost_count = 0
    overdue_count = 0
    for m in open_mems:
        # captured-vial doesn't affect open-card freshness; safe to pass False
        f = derive_freshness(m, now_u, has_captured_vial=False)
        if f == "stale":
            stale_count += 1
        elif f == "ghost":
            ghost_count += 1
        if is_overdue(m, now_u):
            overdue_count += 1

    open_total = max(len(open_mems), 1)
    closed_total = max(len(closed_mems), 1)
    stale_pct = stale_count / open_total
    captured_closed = sum(
        1 for m in closed_mems if captured_counts.get(m.id, 0) > 0
    )
    capture_pct = captured_closed / closed_total

    streak_bonus = max(0, min(10, int(clean_streak_d)))

    score = 100.0
    score -= stale_pct * 30.0
    score -= overdue_count * 5.0
    score -= ghost_count * 10.0
    score += capture_pct * 10.0
    score += float(streak_bonus)
    score += float(quest_bonus)
    score = max(0.0, min(100.0, score))

    return {
        "score": round(score),
        "terms": {
            "stale_pct": round(stale_pct, 3),
            "stale_count": stale_count,
            "ghost_count": ghost_count,
            "overdue_count": overdue_count,
            "capture_pct": round(capture_pct, 3),
            "clean_streak_d": int(clean_streak_d),
            "quest_bonus": int(quest_bonus),
        },
        "counts": {
            "open": len(open_mems),
            "closed": len(closed_mems),
            "captured_closed": captured_closed,
        },
        "computed_at": now_u.isoformat(),
    }


def board_health_tier(score: int) -> Literal["green", "yellow", "red"]:
    """UI helper: pill color tier from numeric score."""
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"
