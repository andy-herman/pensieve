"""Outlook desktop COM TaskSink for the Pensieve column-mirror feature.

This is the ONLY module in `pensieve.sources` that calls `Save()` on an
Outlook item. It exists as a sibling to `outlook_com.py` so the
read-only invariant on `OutlookCOMSource` stays unchanged (the
`test_sources_are_read_only_no_write_methods` test continues to pass).

Mirror semantics:
- We only touch the `.Categories` field.
- We only add or remove tags whose category string starts with the
  configured prefix (default ``pensieve/col:``). User-authored categories
  are preserved byte for byte.
- One Save() per call. No retry loop. The caller decides what to do on
  failure (raise vs swallow).
"""

from __future__ import annotations

from typing import Optional

from pensieve.sources.outlook_com import OutlookCOMUnavailable
from pensieve.sources.sink import TaskSink, merge_pensieve_tag


class OutlookCOMSink(TaskSink):
    """Writes Pensieve column tags to the running Outlook desktop client."""

    name = "outlook_com"

    def __init__(self) -> None:
        self._app = None
        self._ns = None

    def _connect(self) -> None:
        if self._app is not None:
            return
        try:
            import win32com.client  # type: ignore[import-not-found]
        except ImportError as e:
            raise OutlookCOMUnavailable("pywin32 is not installed. Run: pip install pywin32") from e
        try:
            self._app = win32com.client.Dispatch("Outlook.Application")
            self._ns = self._app.GetNamespace("MAPI")
        except Exception as e:
            raise OutlookCOMUnavailable(
                f"Could not connect to Outlook via COM. Is Outlook desktop running? ({e})"
            ) from e

    def _get_item(self, task_id: str):
        self._connect()
        try:
            return self._ns.GetItemFromID(task_id)
        except Exception:
            return None

    def _read_categories(self, item) -> list[str]:
        raw = (getattr(item, "Categories", "") or "").strip()
        if not raw:
            return []
        return [c.strip() for c in raw.split(",") if c.strip()]

    def _write_categories(self, item, categories: list[str]) -> None:
        item.Categories = ", ".join(categories)
        item.Save()

    def set_column_tag(self, task_id: str, column: str, *, prefix: str) -> bool:
        item = self._get_item(task_id)
        if item is None:
            return False
        existing = self._read_categories(item)
        new_cats = merge_pensieve_tag(existing, column, prefix=prefix)
        if new_cats == existing:
            return True
        self._write_categories(item, new_cats)
        return True

    def clear_column_tag(self, task_id: str, *, prefix: str) -> bool:
        item = self._get_item(task_id)
        if item is None:
            return False
        existing = self._read_categories(item)
        new_cats = merge_pensieve_tag(existing, None, prefix=prefix)
        if new_cats == existing:
            return True
        self._write_categories(item, new_cats)
        return True


def get_sink_for_source(source_name: Optional[str]) -> Optional[TaskSink]:
    """Look up the writer matching a `Memory.source` value, or None.

    Used by the API layer to decide whether to fire a write-back call after
    a column change. Returning None means "no sink wired for this source",
    which the caller should treat as a silent no-op (sample_file, future
    sources without write surfaces, etc.).
    """
    if source_name == OutlookCOMSink.name:
        return OutlookCOMSink()
    return None
