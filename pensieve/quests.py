"""Garden v2: daily quests — pure-function generation + completion check.

No I/O, no global state. The persistence layer (today's row, clean-day
history) lives in :mod:`pensieve.quest_state`. The API layer
(:mod:`pensieve.api.server`) glues them together: ``GET /api/quests``
generates if missing for today and auto-evaluates pending completions;
every tending endpoint calls ``_maybe_complete_quests`` after the
``last_tended_at`` bump succeeds.

Design notes (see ``brainstorms/02-board-tending-game.md``):
- Generator selects up to 3 quests per day, ranked by board impact:
  ghost > stale > yesterday-closures > triage-inbox > hit-95-health.
- Each quest is finishable in <10 minutes of real work.
- Quests do NOT carry over — today's misses are tomorrow's clean slate.
- Completing all 3 grants a +5 transient board-health bonus (wired
  into ``compute_board_health`` via the ``quest_bonus`` kwarg).
- Target-memory disappearance is treated as "tended" — if sync drops
  a target from the store, the quest still completes (rather than
  blocking forever on a phantom row).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal, Optional

from pensieve import garden
from pensieve.store.schema import Memory

QuestKind = Literal[
    "bury-ghost",
    "tend-stale",
    "capture-yesterday-closures",
    "triage-inbox",
    "hit-95-health",
]

MAX_QUESTS_PER_DAY = 3
TRIAGE_INBOX_AGE_DAYS = 3  # cards untended >3d in "memory" column trigger triage
HIT_95_LOWER_BOUND = 90
HIT_95_UPPER_BOUND = 94
HIT_95_TARGET = 95


@dataclass
class Quest:
    """A single daily quest. Serializable to JSON via ``to_dict()``."""

    id: str
    kind: QuestKind
    title: str
    description: str
    target_memory_ids: list[str] = field(default_factory=list)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.completed_at is not None:
            d["completed_at"] = self.completed_at.astimezone(timezone.utc).isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Quest":
        completed_raw = d.get("completed_at")
        completed = None
        if completed_raw:
            try:
                completed = datetime.fromisoformat(str(completed_raw).replace("Z", "+00:00"))
            except ValueError:
                completed = None
        return cls(
            id=str(d.get("id") or ""),
            kind=str(d.get("kind") or ""),  # type: ignore[arg-type]
            title=str(d.get("title") or ""),
            description=str(d.get("description") or ""),
            target_memory_ids=[str(x) for x in (d.get("target_memory_ids") or [])],
            completed_at=completed,
        )

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None


def _day_key(now: datetime) -> str:
    """Return ``YYYY-MM-DD`` for the date the quest day belongs to (UTC)."""
    return garden._as_aware_utc(now).strftime("%Y-%m-%d")  # type: ignore[union-attr]


def _today_start(now: datetime) -> datetime:
    """Midnight UTC for the day ``now`` falls in."""
    aware = garden._as_aware_utc(now)
    assert aware is not None
    return aware.replace(hour=0, minute=0, second=0, microsecond=0)


def _yesterday_window(now: datetime) -> tuple[datetime, datetime]:
    """``[yesterday_midnight, today_midnight)`` in UTC."""
    today = _today_start(now)
    return today - timedelta(days=1), today


def _was_tended_today(memory: Memory, now: datetime) -> bool:
    tended = garden._as_aware_utc(memory.last_tended_at)
    if tended is None:
        return False
    return tended >= _today_start(now)


# ----- Quest generation ------------------------------------------------------


def _pick_ghost_target(open_mems: list[Memory], now: datetime) -> Optional[Memory]:
    """First ghost in deterministic order (oldest tended first)."""
    ghosts = [
        m for m in open_mems
        if garden.derive_freshness(m, now, has_captured_vial=False) == "ghost"
    ]
    if not ghosts:
        return None
    ghosts.sort(key=lambda m: garden._as_aware_utc(m.last_tended_at or m.enriched_at) or now)
    return ghosts[0]


def _pick_stale_cluster(
    open_mems: list[Memory], now: datetime
) -> tuple[Optional[str], list[Memory]]:
    """Find the (column, top-3-stale-cards) cluster with the most stale cards.

    Returns (column_name, cards). The column with the highest stale count wins;
    ties broken alphabetically. Returns ``(None, [])`` when no column has
    ≥2 stale cards (we don't generate a single-stale tend quest — that's just
    "tend a card", which isn't interesting).
    """
    by_col: dict[str, list[Memory]] = {}
    for m in open_mems:
        if garden.derive_freshness(m, now, has_captured_vial=False) == "stale":
            by_col.setdefault(m.column or "memory", []).append(m)
    candidates = [(col, cards) for col, cards in by_col.items() if len(cards) >= 2]
    if not candidates:
        return None, []
    candidates.sort(key=lambda x: (-len(x[1]), x[0]))
    col, cards = candidates[0]
    cards.sort(key=lambda m: garden._as_aware_utc(m.last_tended_at or m.enriched_at) or now)
    return col, cards[:3]


def _pick_yesterday_closures(
    closed_mems: list[Memory], captured_counts: dict[str, int], now: datetime
) -> list[Memory]:
    """Closed-yesterday cards that lack a CAPTURED vial."""
    y_start, y_end = _yesterday_window(now)
    out: list[Memory] = []
    for m in closed_mems:
        ca = garden._as_aware_utc(m.completed_at)
        if ca is None:
            continue
        if not (y_start <= ca < y_end):
            continue
        if captured_counts.get(m.id, 0) > 0:
            continue
        out.append(m)
    return out[:3]  # cap


def _pick_triage_target(open_mems: list[Memory], now: datetime) -> Optional[Memory]:
    """First "memory" lane card untended > TRIAGE_INBOX_AGE_DAYS, oldest first."""
    candidates: list[tuple[datetime, Memory]] = []
    for m in open_mems:
        if (m.column or "memory") != "memory":
            continue
        tended = garden._as_aware_utc(m.last_tended_at) or garden._as_aware_utc(m.enriched_at)
        if tended is None:
            continue
        age = (now - tended).days
        if age > TRIAGE_INBOX_AGE_DAYS:
            candidates.append((tended, m))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]


def _quest_id(kind: QuestKind, day_key: str) -> str:
    return f"q-{kind}-{day_key}"


def generate_quests(
    memories: Iterable[Memory],
    now: Optional[datetime] = None,
    *,
    captured_counts: Optional[dict[str, int]] = None,
    current_health: Optional[int] = None,
) -> list[Quest]:
    """Generate up to MAX_QUESTS_PER_DAY quests for today.

    Selection is deterministic given the input — same board produces the same
    quest list within the same day. ``current_health`` is the latest computed
    board-health score; only the ``hit-95-health`` quest uses it.
    """
    now_u = garden._now_utc(now)
    captured_counts = captured_counts or {}
    mems = list(memories)
    open_mems = [m for m in mems if (m.column or "memory") != "closed"]
    closed_mems = [m for m in mems if (m.column or "memory") == "closed"]
    day_key = _day_key(now_u)

    quests: list[Quest] = []
    already_targeted: set[str] = set()  # don't double-target the same memory_id

    # 1) Ghost — single highest-priority target.
    ghost = _pick_ghost_target(open_mems, now_u)
    if ghost is not None:
        title = "Bury or revive a ghost"
        desc = (
            f"'{(ghost.display_title or ghost.title or 'untitled')[:80]}' "
            f"in {ghost.column or 'memory'} has been quiet for over a month. "
            "Tend it (edit, capture a vial, or close it) to put it to rest."
        )
        quests.append(Quest(
            id=_quest_id("bury-ghost", day_key),
            kind="bury-ghost",
            title=title,
            description=desc,
            target_memory_ids=[ghost.id],
        ))
        already_targeted.add(ghost.id)

    # 2) Stale cluster — up to 3 cards in the worst column.
    if len(quests) < MAX_QUESTS_PER_DAY:
        col, cards = _pick_stale_cluster(open_mems, now_u)
        # Exclude any card already targeted (e.g. by the ghost quest).
        cards = [m for m in cards if m.id not in already_targeted]
        # Re-check the ≥2 threshold after exclusion so a single leftover
        # stale doesn't generate a trivial quest.
        if col is not None and len(cards) >= 2:
            n = len(cards)
            quests.append(Quest(
                id=_quest_id("tend-stale", day_key),
                kind="tend-stale",
                title=f"Tend {n} stale card{'s' if n != 1 else ''} in {col}",
                description=(
                    f"{n} card{'s' if n != 1 else ''} in {col} ha"
                    f"{'ve' if n != 1 else 's'} been untouched for over a week. "
                    "Edit, move, or capture a vial to refresh them."
                ),
                target_memory_ids=[m.id for m in cards],
            ))
            already_targeted.update(m.id for m in cards)

    # 3) Yesterday's closures missing captured vials.
    if len(quests) < MAX_QUESTS_PER_DAY:
        closures = _pick_yesterday_closures(closed_mems, captured_counts, now_u)
        closures = [m for m in closures if m.id not in already_targeted]
        if closures:
            n = len(closures)
            quests.append(Quest(
                id=_quest_id("capture-yesterday-closures", day_key),
                kind="capture-yesterday-closures",
                title=f"Capture vials on {n} of yesterday's closures",
                description=(
                    f"{n} card{'s' if n != 1 else ''} closed yesterday without a "
                    "captured vial. A one-sentence vial preserves the win even "
                    "if the source task is later deleted."
                ),
                target_memory_ids=[m.id for m in closures],
            ))
            already_targeted.update(m.id for m in closures)

    # 4) Inbox triage — single oldest "memory" card untended >3d
    #    (must not already be targeted by another quest).
    if len(quests) < MAX_QUESTS_PER_DAY:
        triage = _pick_triage_target(open_mems, now_u)
        if triage is not None and triage.id not in already_targeted:
            quests.append(Quest(
                id=_quest_id("triage-inbox", day_key),
                kind="triage-inbox",
                title="Triage 1 inbox card",
                description=(
                    f"'{(triage.display_title or triage.title or 'untitled')[:80]}' "
                    "has been in the inbox without attention. Move it to dive, "
                    "review, or closed — or edit it to plan next steps."
                ),
                target_memory_ids=[triage.id],
            ))
            already_targeted.add(triage.id)

    # 5) Hit 95+ health — only when close (90..94).
    if (
        len(quests) < MAX_QUESTS_PER_DAY
        and current_health is not None
        and HIT_95_LOWER_BOUND <= current_health <= HIT_95_UPPER_BOUND
    ):
        quests.append(Quest(
            id=_quest_id("hit-95-health", day_key),
            kind="hit-95-health",
            title=f"Hit {HIT_95_TARGET}+ board health today",
            description=(
                f"Board health is at {current_health}. Tend a couple of stale "
                f"cards or capture a vial to push it past {HIT_95_TARGET}."
            ),
            target_memory_ids=[],
        ))

    return quests[:MAX_QUESTS_PER_DAY]


# ----- Completion detection --------------------------------------------------


def check_completion(
    quest: Quest,
    *,
    now: datetime,
    all_memories: Iterable[Memory],
    captured_counts: dict[str, int],
    current_health: Optional[int] = None,
) -> bool:
    """Return True iff the quest is complete right now.

    Idempotent — safe to call on already-completed quests. Auto-completes
    when targets disappear (sync removed them), so a deleted source task
    can't block a quest forever.
    """
    if quest.is_complete:
        return True

    mem_by_id = {m.id: m for m in all_memories}

    if quest.kind == "hit-95-health":
        return current_health is not None and current_health >= HIT_95_TARGET

    if not quest.target_memory_ids:
        return False

    if quest.kind == "capture-yesterday-closures":
        for mid in quest.target_memory_ids:
            if mid not in mem_by_id:
                continue  # gone => count as done for this target
            if captured_counts.get(mid, 0) <= 0:
                return False
        return True

    if quest.kind == "triage-inbox":
        # Done when target left the "memory" lane OR was tended today
        # (edit counts even if it stayed put).
        for mid in quest.target_memory_ids:
            mem = mem_by_id.get(mid)
            if mem is None:
                continue
            if (mem.column or "memory") == "memory" and not _was_tended_today(mem, now):
                return False
        return True

    # bury-ghost and tend-stale: ALL targets must be tended today
    # (or have disappeared from the store).
    for mid in quest.target_memory_ids:
        mem = mem_by_id.get(mid)
        if mem is None:
            continue
        if not _was_tended_today(mem, now):
            return False
    return True


def evaluate_pending(
    quests: list[Quest],
    *,
    now: datetime,
    all_memories: Iterable[Memory],
    captured_counts: dict[str, int],
    current_health: Optional[int] = None,
) -> list[Quest]:
    """Mark any pending quest complete if check_completion returns True.

    Mutates and returns the input list. ``completed_at`` is set to ``now``
    (UTC-aware) only on the transition pending → complete.
    """
    now_u = garden._as_aware_utc(now)
    assert now_u is not None
    mems = list(all_memories)
    for q in quests:
        if q.is_complete:
            continue
        if check_completion(
            q,
            now=now_u,
            all_memories=mems,
            captured_counts=captured_counts,
            current_health=current_health,
        ):
            q.completed_at = now_u
    return quests


def all_complete(quests: list[Quest]) -> bool:
    return bool(quests) and all(q.is_complete for q in quests)


def quest_bonus_for(quests: list[Quest]) -> int:
    """The +5 transient board-health bonus when all today's quests are done."""
    return 5 if all_complete(quests) else 0


def is_board_clean(
    memories: Iterable[Memory],
    now: Optional[datetime] = None,
    *,
    captured_counts: Optional[dict[str, int]] = None,
) -> bool:
    """A board is "clean" iff zero stale, zero ghost, zero overdue OPEN cards.

    Used by quest_state to decide whether to bump ``clean_streak_d``.
    """
    now_u = garden._now_utc(now)
    captured_counts = captured_counts or {}
    for m in memories:
        if (m.column or "memory") == "closed":
            continue
        f = garden.derive_freshness(m, now_u, has_captured_vial=False)
        if f in ("stale", "ghost"):
            return False
        if garden.is_overdue(m, now_u):
            return False
    return True
