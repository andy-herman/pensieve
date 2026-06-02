"""Write-back interface for keeping Pensieve's kanban column mirrored on the source.

Per AGENTS.md "Sources are read-only" contract, every `TaskSource` is pull-only.
This module introduces a strictly opt-in `TaskSink` that handles the only
writeback Pensieve supports: tagging a source task with the user's chosen
kanban column so the same view appears on a second PC after sync.

The tag format is `<prefix><column>` where prefix defaults to
``pensieve/col:`` (configurable via `PENSIEVE_MIRROR_TAG_PREFIX`). Pensieve
never touches categories that do not start with the prefix.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


def merge_pensieve_tag(
    existing_categories: list[str],
    column: Optional[str],
    *,
    prefix: str,
) -> list[str]:
    """Pure helper: rewrite a categories list so it has exactly one Pensieve tag.

    - Drops every category that starts with `prefix` (case-insensitive on the
      prefix; the column suffix is preserved as-given on write).
    - If `column` is non-empty, appends `f"{prefix}{column}"` at the end.
    - Preserves order and casing of every other category.
    - De-duplicates only the Pensieve tags; user tags are untouched even if
      duplicated upstream (we don't reformat the user's data).
    """
    prefix_lower = prefix.lower()
    kept = [c for c in existing_categories if not c.lower().startswith(prefix_lower)]
    if column:
        kept.append(f"{prefix}{column}")
    return kept


def extract_pensieve_column(
    categories: list[str],
    *,
    prefix: str,
) -> Optional[str]:
    """Return the column embedded in the first Pensieve tag, or None.

    Multiple Pensieve tags on one task is a bug (Pensieve always writes one),
    but if it happens we honor the first hit. The column is whatever follows
    `prefix` literally, stripped of surrounding whitespace.
    """
    prefix_lower = prefix.lower()
    for cat in categories:
        if cat.lower().startswith(prefix_lower):
            return cat[len(prefix) :].strip() or None
    return None


class TaskSink(ABC):
    """Strictly opt-in write surface for the column-mirror feature.

    Implementations MUST limit themselves to the single tag namespace passed
    via `prefix`. They MUST NOT modify task titles, bodies, due dates,
    completion state, or any other field. Any change to a task MUST be
    reversible (remove the tag returns the task to its pre-Pensieve state).
    """

    name: str = "unknown"

    @abstractmethod
    def set_column_tag(self, task_id: str, column: str, *, prefix: str) -> bool:
        """Replace any existing Pensieve column tag with `prefix + column`.

        Returns True on a write, False if the task could not be found.
        Raises on transport failures so callers can decide whether to retry
        or roll back the local change.
        """

    @abstractmethod
    def clear_column_tag(self, task_id: str, *, prefix: str) -> bool:
        """Strip every Pensieve column tag from the task. Returns True on write."""
