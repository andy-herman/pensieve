"""Garden v2: persist today's quests + clean-day history to a JSON file.

File: ``data/garden-quests.json`` (path resolved via :class:`Settings`).
Shape::

    {
      "version": 1,
      "today": {
        "date": "2026-06-05",
        "generated_at": "...iso...",
        "quests": [ {id, kind, title, description, target_memory_ids, completed_at}, ... ],
        "all_done_bonus_grants": 0
      },
      "clean_streak_d": 3,
      "history": [
        {"date": "2026-06-04", "clean": true},
        {"date": "2026-06-03", "clean": true},
        ...
      ]
    }

``history`` is capped to the most recent ~120 entries (a quarter+).
Writes are atomic (tmp+replace+fsync) so a crash mid-write never leaves
an empty or half-JSON state file. The atomic-write pattern matches
``data/connect-goals.json`` (see ``pensieve.api.server.save_goals``).

Concurrency note: this is a single-user single-process app. Two near-
simultaneous tend bumps may both read the file and both write
``completed_at`` for the same quest — the writes are idempotent
(``completed_at`` stays approximately the same), and the second write
wins. No locking required.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pensieve import garden
from pensieve.quests import Quest

MAX_HISTORY_ENTRIES = 120
SCHEMA_VERSION = 1


@dataclass
class TodayRow:
    date: str
    generated_at: datetime
    quests: list[Quest] = field(default_factory=list)
    all_done_bonus_grants: int = 0

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "generated_at": self.generated_at.astimezone(timezone.utc).isoformat(),
            "quests": [q.to_dict() for q in self.quests],
            "all_done_bonus_grants": int(self.all_done_bonus_grants),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TodayRow":
        gen_raw = d.get("generated_at") or ""
        try:
            gen = datetime.fromisoformat(str(gen_raw).replace("Z", "+00:00"))
        except ValueError:
            gen = datetime.now(timezone.utc)
        return cls(
            date=str(d.get("date") or ""),
            generated_at=gen,
            quests=[Quest.from_dict(x) for x in (d.get("quests") or [])],
            all_done_bonus_grants=int(d.get("all_done_bonus_grants") or 0),
        )


@dataclass
class QuestState:
    today: Optional[TodayRow] = None
    clean_streak_d: int = 0
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "today": self.today.to_dict() if self.today else None,
            "clean_streak_d": int(self.clean_streak_d),
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "QuestState":
        today_raw = d.get("today")
        today = TodayRow.from_dict(today_raw) if isinstance(today_raw, dict) else None
        history_raw = d.get("history") or []
        history = []
        for x in history_raw:
            if not isinstance(x, dict) or not x.get("date"):
                continue
            entry: dict = {"date": str(x["date"]), "clean": bool(x.get("clean"))}
            hs = x.get("health_score")
            if isinstance(hs, int):
                entry["health_score"] = hs
            history.append(entry)
        return cls(
            today=today,
            clean_streak_d=int(d.get("clean_streak_d") or 0),
            history=history[-MAX_HISTORY_ENTRIES:],
        )


# ----- persistence ----------------------------------------------------------


def _state_path_from(quest_state_path: Path) -> Path:
    return quest_state_path


def load_state(path: Path) -> QuestState:
    """Load state from disk. Returns an empty default if the file is missing
    or corrupted (so a one-off bad write can't permanently break quests).
    """
    if not path.exists():
        return QuestState()
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return QuestState()
        return QuestState.from_dict(raw)
    except (json.JSONDecodeError, OSError, ValueError):
        return QuestState()


def save_state(state: QuestState, path: Path) -> None:
    """Atomically persist state to ``path`` (tmp + fsync + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = state.to_dict()
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(path)


# ----- day rollover + streak math -------------------------------------------


def _yesterday_key(now: datetime) -> str:
    aware = garden._as_aware_utc(now)
    assert aware is not None
    return (aware - timedelta(days=1)).strftime("%Y-%m-%d")


def is_today_row(row: Optional[TodayRow], now: datetime) -> bool:
    """True iff ``row`` is for the calendar day ``now`` belongs to (UTC)."""
    if row is None:
        return False
    aware = garden._as_aware_utc(now)
    assert aware is not None
    return row.date == aware.strftime("%Y-%m-%d")


def record_yesterday_clean(
    state: QuestState,
    *,
    was_clean: bool,
    now: datetime,
    health_score: Optional[int] = None,
) -> QuestState:
    """Append yesterday's clean/dirty record and recompute ``clean_streak_d``.

    Idempotent: if yesterday's date already appears at the tail of history,
    overwrite that entry instead of duplicating. ``clean_streak_d`` becomes
    the count of consecutive clean days ending at yesterday (today is not
    yet decided).

    ``health_score`` is an optional integer snapshot of the board health
    score for the day being recorded. When provided it lands in the history
    entry so :func:`pensieve.achievements.build_level_summary` can compute
    week-over-week deltas. Older entries that predate this field stay valid
    (level-summary tolerates missing scores).
    """
    y_key = _yesterday_key(now)
    history = list(state.history or [])
    new_entry: dict = {"date": y_key, "clean": bool(was_clean)}
    if health_score is not None:
        new_entry["health_score"] = int(health_score)
    if history and history[-1].get("date") == y_key:
        # Preserve any pre-existing health_score if the caller didn't supply one.
        if health_score is None and isinstance(history[-1].get("health_score"), int):
            new_entry["health_score"] = int(history[-1]["health_score"])
        history[-1] = new_entry
    else:
        history.append(new_entry)
    history = history[-MAX_HISTORY_ENTRIES:]

    # Recompute streak: walk backwards from the tail counting consecutive cleans.
    streak = 0
    for entry in reversed(history):
        if entry.get("clean"):
            streak += 1
        else:
            break

    state.history = history
    state.clean_streak_d = streak
    return state


def quest_bonus_today(state: QuestState) -> int:
    """+5 iff today's quests are all complete AND we have a today row."""
    if state.today is None or not state.today.quests:
        return 0
    return 5 if all(q.is_complete for q in state.today.quests) else 0
