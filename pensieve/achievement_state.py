"""Garden v3: persist the unlocked-set of achievements with timestamps.

File: ``data/achievements.json``. Atomic tmp+replace write pattern
matching ``data/connect-goals.json`` and ``data/garden-quests.json``.
Schema::

    {
      "version": 1,
      "unlocked": [
        {"id": "sprout", "unlocked_at": "...iso..."},
        ...
      ]
    }

Once unlocked, an achievement is never re-locked. ``merge_unlocked``
appends new IDs (with the current timestamp) but never removes
previously-unlocked entries — this protects against transient state
that briefly flips a predicate off (e.g. a sync drop dipping health
back below 95 after Sharpshooter was earned).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class UnlockedEntry:
    id: str
    unlocked_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "unlocked_at": self.unlocked_at.astimezone(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UnlockedEntry":
        ts_raw = str(d.get("unlocked_at") or "")
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.now(timezone.utc)
        return cls(id=str(d.get("id") or ""), unlocked_at=ts)


@dataclass
class AchievementState:
    unlocked: list[UnlockedEntry] = field(default_factory=list)

    def unlocked_ids(self) -> set[str]:
        return {u.id for u in self.unlocked}

    def to_dict(self) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "unlocked": [u.to_dict() for u in self.unlocked],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AchievementState":
        items = d.get("unlocked") or []
        out: list[UnlockedEntry] = []
        seen: set[str] = set()
        for x in items:
            if not isinstance(x, dict):
                continue
            entry = UnlockedEntry.from_dict(x)
            if not entry.id or entry.id in seen:
                continue
            seen.add(entry.id)
            out.append(entry)
        return cls(unlocked=out)


def load_state(path: Path) -> AchievementState:
    """Load state. Corrupt or missing file → empty default (no badges yet)."""
    if not path.exists():
        return AchievementState()
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return AchievementState()
        return AchievementState.from_dict(raw)
    except (json.JSONDecodeError, OSError, ValueError):
        return AchievementState()


def save_state(state: AchievementState, path: Path) -> None:
    """Atomic tmp+fsync+replace persistence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = state.to_dict()
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(path)


def merge_unlocked(
    state: AchievementState, should_be_unlocked: set[str], now: datetime
) -> tuple[AchievementState, set[str]]:
    """Add any new IDs in ``should_be_unlocked`` to ``state`` with ``now``.

    Returns ``(updated_state, new_ids)``. ``new_ids`` is the set of IDs
    that just transitioned from locked → unlocked on this call (empty
    when nothing changed). Never removes existing entries.
    """
    existing = state.unlocked_ids()
    new_ids = should_be_unlocked - existing
    for nid in new_ids:
        state.unlocked.append(UnlockedEntry(id=nid, unlocked_at=now))
    return state, new_ids
