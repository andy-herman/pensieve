"""Load the Connect goals data from data/connect-goals.json."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pensieve.config import get_settings


@lru_cache(maxsize=1)
def load_connect_goals() -> list[dict[str, Any]]:
    s = get_settings()
    path = s.connect_goals_path
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return list(payload.get("goals", []))


@lru_cache(maxsize=1)
def goals_index() -> dict[str, dict[str, Any]]:
    return {g["id"]: g for g in load_connect_goals() if "id" in g}
