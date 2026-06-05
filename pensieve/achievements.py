"""Garden v3: state-derivable achievement evaluation.

Pure-function module. No I/O. Persistence (the unlocked-set with timestamps)
lives in :mod:`pensieve.achievement_state`; the API layer glues them
together via ``GET /api/achievements``.

Once unlocked, achievements stay unlocked. ``evaluate()`` returns the set
of achievement IDs that SHOULD currently be unlocked given the input
state — ``merge_unlocked`` in :mod:`pensieve.achievement_state` adds any
new IDs to the persisted set with a ``now`` timestamp without ever
removing previously-unlocked badges.

The original brainstorm called for some event-based achievements
(Custodian needed "first ghost buried", Storm needed "5 closures in a
day"). Both are derivable from current state:

- **Custodian**: a closed memory whose ``completed_at - enriched_at``
  delta exceeded 30 days was, by definition, a ghost at close-time
  (it had been around longer than the ghost threshold; if it had
  been tended in between, that tend would have happened on a card
  that was already at risk of going ghost — and closing a "would-have-
  been-a-ghost-soon" card still counts as custodianship).
- **Storm**: count ``completed_at`` timestamps grouped by UTC day;
  any day with >= 5 closures unlocks the badge.

Clean Week + Streak Keeper need the clean-day history written by
:mod:`pensieve.quest_state` (introduced in Garden v2), passed in via the
``history`` kwarg as a list of ``{"date","clean"}`` rows oldest-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from pensieve import garden
from pensieve.store.schema import Memory, Vial

GHOST_AT_CLOSE_DAYS = 30
SCRIBE_THRESHOLD = 10
CENTURION_THRESHOLD = 100
STORM_THRESHOLD = 5
CLEAN_WEEK_DAYS = 7
STREAK_KEEPER_DAYS = 30
SHARPSHOOTER_HEALTH = 95


@dataclass(frozen=True)
class Achievement:
    id: str
    emoji: str
    name: str
    description: str
    requires_others: bool = False  # used only by Gardener (depends on all others)


ACHIEVEMENTS: list[Achievement] = [
    Achievement("sprout", "\U0001F331", "Sprout", "First memory created"),
    Achievement("scribe", "\U0001F4DC", "Scribe", "10 captured Vials"),
    Achievement("centurion", "\U0001F31F", "Centurion", "100 lifetime captured Vials"),
    Achievement("custodian", "\U0001F9F9", "Custodian", "First ghost buried"),
    Achievement("storm", "\u26A1", "Storm", "5 cards closed in a single day"),
    Achievement("clean-week", "\U0001F3C6", "Clean Week", "7 consecutive clean-board days"),
    Achievement("streak-keeper", "\U0001F525", "Streak Keeper", "30 consecutive clean-board days"),
    Achievement("sharpshooter", "\U0001F3AF", "Sharpshooter", "Hit 95+ board health"),
    Achievement(
        "gardener", "\U0001F333", "Gardener",
        "Unlock all other achievements",
        requires_others=True,
    ),
]

ACHIEVEMENT_IDS = [a.id for a in ACHIEVEMENTS]


def _captured_count(vials: Iterable[Vial]) -> int:
    return sum(1 for v in vials if (v.capture_kind or "captured") == "captured")


def _has_custodian(memories: Iterable[Memory]) -> bool:
    for m in memories:
        if (m.column or "memory") != "closed":
            continue
        closed = garden._as_aware_utc(m.completed_at)
        born = garden._as_aware_utc(m.enriched_at)
        if closed is None or born is None:
            continue
        if (closed - born).days > GHOST_AT_CLOSE_DAYS:
            return True
    return False


def _has_storm(memories: Iterable[Memory]) -> bool:
    closures_by_day: dict[str, int] = {}
    for m in memories:
        if (m.column or "memory") != "closed":
            continue
        closed = garden._as_aware_utc(m.completed_at)
        if closed is None:
            continue
        key = closed.strftime("%Y-%m-%d")
        closures_by_day[key] = closures_by_day.get(key, 0) + 1
    return any(count >= STORM_THRESHOLD for count in closures_by_day.values())


def _longest_clean_run(history: list[dict]) -> int:
    """Longest run of consecutive ``clean: True`` entries anywhere in history.

    Does NOT require the run to end at "today" — Clean Week / Streak Keeper
    are lifetime achievements, not "still going" badges.
    """
    best = 0
    cur = 0
    for entry in history or []:
        if entry.get("clean"):
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def evaluate(
    memories: Iterable[Memory],
    vials: Iterable[Vial],
    *,
    current_health: Optional[int] = None,
    history: Optional[list[dict]] = None,
) -> set[str]:
    """Return the set of achievement IDs that SHOULD be unlocked right now.

    Idempotent. Caller (achievement_state.merge_unlocked) decides whether
    each ID is a new unlock vs. one that was already in the persisted set.
    """
    mems = list(memories)
    vs = list(vials)
    history = history or []
    unlocked: set[str] = set()

    captured = _captured_count(vs)

    if mems:
        unlocked.add("sprout")
    if captured >= SCRIBE_THRESHOLD:
        unlocked.add("scribe")
    if captured >= CENTURION_THRESHOLD:
        unlocked.add("centurion")
    if _has_custodian(mems):
        unlocked.add("custodian")
    if _has_storm(mems):
        unlocked.add("storm")

    longest_run = _longest_clean_run(history)
    if longest_run >= CLEAN_WEEK_DAYS:
        unlocked.add("clean-week")
    if longest_run >= STREAK_KEEPER_DAYS:
        unlocked.add("streak-keeper")
    if current_health is not None and current_health >= SHARPSHOOTER_HEALTH and mems:
        unlocked.add("sharpshooter")

    # Gardener unlocks last and requires every other achievement first.
    other_ids = {a.id for a in ACHIEVEMENTS if not a.requires_others}
    if other_ids.issubset(unlocked):
        unlocked.add("gardener")

    return unlocked


def definitions() -> list[dict]:
    """Serializable list of all achievement definitions for the frontend."""
    return [
        {
            "id": a.id,
            "emoji": a.emoji,
            "name": a.name,
            "description": a.description,
        }
        for a in ACHIEVEMENTS
    ]


def _today_start(now: datetime) -> datetime:
    aware = garden._as_aware_utc(now)
    assert aware is not None
    return aware.replace(hour=0, minute=0, second=0, microsecond=0)


def build_level_summary(
    memories: Iterable[Memory],
    vials: Iterable[Vial],
    *,
    now: datetime,
    history: Optional[list[dict]] = None,
) -> dict:
    """Garden v3 weekly level-summary.

    Returns counts + health delta + streak for the trailing 7 days
    (relative to ``now``). Designed to be embedded in the Friday digest
    (Issue #3) when that ships — for v3 we just expose the endpoint.

    ``history`` rows can carry an optional ``"health_score"`` integer
    (added by quest_state day-rollover). If absent for the comparison
    week, the delta is reported as ``None``.
    """
    now_aware = garden._as_aware_utc(now)
    assert now_aware is not None
    today = _today_start(now_aware)
    week_start = today - timedelta(days=7)
    prev_week_start = today - timedelta(days=14)

    mems = list(memories)
    vs = list(vials)
    history = history or []

    closed_this_week = 0
    closed_prev_week = 0
    for m in mems:
        if (m.column or "memory") != "closed":
            continue
        closed_at = garden._as_aware_utc(m.completed_at)
        if closed_at is None:
            continue
        if week_start <= closed_at < today + timedelta(days=1):
            closed_this_week += 1
        elif prev_week_start <= closed_at < week_start:
            closed_prev_week += 1

    captured_this_week = 0
    for v in vs:
        if (v.capture_kind or "captured") != "captured":
            continue
        captured_at = garden._as_aware_utc(v.captured_at)
        if captured_at is None:
            continue
        if week_start <= captured_at < today + timedelta(days=1):
            captured_this_week += 1

    capture_rate = (
        round(100.0 * captured_this_week / closed_this_week)
        if closed_this_week
        else None
    )

    # Health delta: compare most recent history entry vs. closest entry ~7d ago
    health_now: Optional[int] = None
    health_prev: Optional[int] = None
    if history:
        last = history[-1]
        if isinstance(last.get("health_score"), int):
            health_now = int(last["health_score"])
        # Walk backward to find an entry from 7 days ago (or earliest > 7d).
        target = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        for entry in history:
            if entry.get("date", "") <= target and isinstance(
                entry.get("health_score"), int
            ):
                health_prev = int(entry["health_score"])
                break
    health_delta = (
        health_now - health_prev
        if (health_now is not None and health_prev is not None)
        else None
    )

    # Compute current clean streak (consecutive days ending at history tail).
    current_streak = 0
    for entry in reversed(history):
        if entry.get("clean"):
            current_streak += 1
        else:
            break

    return {
        "week_start": week_start.isoformat(),
        "week_end": today.isoformat(),
        "closed_this_week": closed_this_week,
        "closed_prev_week": closed_prev_week,
        "captured_this_week": captured_this_week,
        "capture_rate_pct": capture_rate,
        "health_now": health_now,
        "health_prev_week": health_prev,
        "health_delta": health_delta,
        "current_streak_d": current_streak,
        "longest_streak_d": _longest_clean_run(history),
    }
