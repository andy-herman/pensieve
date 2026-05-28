"""Load the v2 enrichment system prompt from prompts/enrich-memory-prompt.md."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pensieve.config import get_settings


@lru_cache(maxsize=4)
def load_system_prompt(name: str = "enrich-memory-prompt.md") -> str:
    s = get_settings()
    path: Path = s.prompts_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
