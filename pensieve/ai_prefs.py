"""In-app model choices for Pensieve's AI calls.

The dashboard's "AI models" panel picks a model per purpose. Choices live in
``<data_dir>/ai-models.json`` and are read on every LLM call, so a change in
the app applies to the next call without restarting anything.

Resolution for a purpose: its own choice, else the panel's default, else
``COPILOT_MODEL`` from ``.env``. A blank or missing value means "inherit".
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from pensieve.config import Settings

FILENAME = "ai-models.json"

# Purpose keys, in panel order, with the labels the dashboard shows.
PURPOSES: dict[str, str] = {
    "enrichment": "Sync enrichment and Regenerate",
    "recap": "Connect recaps",
    "goals": "Goals PDF import",
}
_KEYS = ("default", *PURPOSES)

_lock = threading.Lock()


def _path(settings: Settings) -> Path:
    return Path(settings.data_dir) / FILENAME


def _clean(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    v = value.strip()
    return v or None


def load(settings: Settings) -> dict[str, Optional[str]]:
    """Saved choices, ``{"default": ..., "enrichment": ..., ...}`` (None = inherit)."""
    out: dict[str, Optional[str]] = {k: None for k in _KEYS}
    p = _path(settings)
    try:
        with _lock, p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return out
    if isinstance(raw, dict):
        for k in _KEYS:
            out[k] = _clean(raw.get(k))
    return out


def save(settings: Settings, choices: dict[str, Any]) -> dict[str, Optional[str]]:
    """Replace the saved choices (unknown keys ignored) and return the result."""
    data = {k: _clean(choices.get(k)) for k in _KEYS}
    p = _path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with _lock:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, p)
    return data


def model_for(settings: Settings, purpose: str) -> str:
    """The model id to use for ``purpose`` right now."""
    choices = load(settings)
    return choices.get(purpose) or choices.get("default") or settings.copilot_model


def describe(settings: Settings) -> dict[str, Any]:
    """Panel state: saved choices plus the effective model for each purpose."""
    choices = load(settings)
    env_default = settings.copilot_model
    default_effective = choices["default"] or env_default
    return {
        "env_default": env_default,
        "default": choices["default"],
        "default_effective": default_effective,
        "purposes": [
            {
                "key": key,
                "label": label,
                "model": choices[key],
                "effective": choices[key] or default_effective,
            }
            for key, label in PURPOSES.items()
        ],
    }
