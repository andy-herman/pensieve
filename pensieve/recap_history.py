"""Persist and retrieve past recap runs.

Each generated recap is written to data/recaps/<id>.json so the dashboard can
show a running history and re-open any prior run. Storage is plain JSON files;
no database needed.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pensieve.config import Settings, get_settings

_ID_SAFE = re.compile(r"[^a-zA-Z0-9_-]")


def _recaps_dir(settings: Settings) -> Path:
    d = settings.data_dir / "recaps"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    """The light-weight view used by the history list (no full sections)."""
    return {
        "id": record.get("id"),
        "created_at": record.get("created_at"),
        "scope": record.get("scope"),
        "period_label": record.get("period_label"),
        "section_count": record.get("section_count"),
        "memories_considered": record.get("memories_considered"),
        "tokens_used": record.get("tokens_used"),
    }


def save_recap(
    recap: dict[str, Any],
    *,
    settings: Optional[Settings] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Persist a recap run; returns its summary (including the new id)."""
    settings = settings or get_settings()
    ts = now or datetime.now(timezone.utc)
    rid = "recap-" + ts.strftime("%Y%m%d-%H%M%S")
    rid = _ID_SAFE.sub("", rid)
    record = {
        "id": rid,
        "created_at": ts.isoformat(),
        "scope": recap.get("scope"),
        "period_label": recap.get("period_label"),
        "section_count": recap.get("section_count"),
        "memories_considered": recap.get("memories_considered"),
        "tokens_used": recap.get("tokens_used"),
        "recap": recap,
    }
    path = _recaps_dir(settings) / f"{rid}.json"
    # Avoid clobbering if two runs land in the same second.
    n = 1
    while path.exists():
        rid_n = f"{rid}-{n}"
        path = _recaps_dir(settings) / f"{rid_n}.json"
        record["id"] = rid_n
        n += 1
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return _summary(record)


def list_history(settings: Optional[Settings] = None) -> list[dict[str, Any]]:
    """Return run summaries, newest first."""
    settings = settings or get_settings()
    out: list[dict[str, Any]] = []
    for path in _recaps_dir(settings).glob("recap-*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                record = json.load(f)
            out.append(_summary(record))
        except Exception:
            continue
    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return out


def load_recap(rid: str, settings: Optional[Settings] = None) -> Optional[dict[str, Any]]:
    """Return the full stored record for an id, or None."""
    settings = settings or get_settings()
    safe = _ID_SAFE.sub("", rid)
    path = _recaps_dir(settings) / f"{safe}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
