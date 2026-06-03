"""Outlook desktop COM TaskSink for Pensieve's writeback features.

This is the ONLY module in `pensieve.sources` that calls `Save()` on an
Outlook item. It exists as a sibling to `outlook_com.py` so the
read-only invariant on `OutlookCOMSource` stays unchanged (the
`test_sources_are_read_only_no_write_methods` test continues to pass).

Two writeback channels, both opt-in via their own env flag:

- ``set_column_tag`` / ``clear_column_tag`` — touches only ``.Categories``
  entries whose string starts with the configured prefix (default
  ``pensieve/col:``). User-authored categories are preserved byte for byte.
- ``set_completion`` — calls ``TaskItem.MarkComplete()`` (preferred) or
  flips ``item.Complete`` as a fallback, then ``Save()``. Used only when
  ``PENSIEVE_MIRROR_COMPLETION`` is enabled.

All three public methods wrap their COM work in a per-thread
``CoInitialize`` / ``CoUninitialize`` bracket. FastAPI dispatches sync
routes onto worker threads from a pool, and pywin32 requires each thread
that touches COM to own its own apartment — without this bracket the
first writeback from a fresh worker thread fails with
``CoInitialize has not been called.``
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from pensieve.sources.outlook_com import OutlookCOMUnavailable
from pensieve.sources.sink import TaskSink, merge_pensieve_tag


@contextmanager
def _ensured_com_apartment() -> Iterator[None]:
    """Initialize an STA on the current thread if one isn't already, and
    uninitialize ONLY if we were the ones that initialized it.

    Repeated CoInitialize() on a thread that already owns the same apartment
    returns S_FALSE (no raise); we still call CoUninitialize() to balance
    the refcount. The try/except around the import is for the test rig where
    pywin32 may not be installed.
    """
    owned = False
    try:
        try:
            import pythoncom  # type: ignore[import-not-found]
        except ImportError:
            yield
            return
        try:
            pythoncom.CoInitialize()
            owned = True
        except Exception:
            owned = False  # apartment already set up by an outer caller
        yield
    finally:
        if owned:
            try:
                import pythoncom  # type: ignore[import-not-found]

                pythoncom.CoUninitialize()
            except Exception:
                pass


class OutlookCOMSink(TaskSink):
    """Writes Pensieve column tags and completion state to the running Outlook desktop client."""

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
        with _ensured_com_apartment():
            return self._set_column_tag_unguarded(task_id, column, prefix=prefix)

    def _set_column_tag_unguarded(self, task_id: str, column: str, *, prefix: str) -> bool:
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
        with _ensured_com_apartment():
            return self._clear_column_tag_unguarded(task_id, prefix=prefix)

    def _clear_column_tag_unguarded(self, task_id: str, *, prefix: str) -> bool:
        item = self._get_item(task_id)
        if item is None:
            return False
        existing = self._read_categories(item)
        new_cats = merge_pensieve_tag(existing, None, prefix=prefix)
        if new_cats == existing:
            return True
        self._write_categories(item, new_cats)
        return True

    def set_completion(self, task_id: str, completed: bool) -> bool:
        with _ensured_com_apartment():
            return self._set_completion_unguarded(task_id, completed)

    def _set_completion_unguarded(self, task_id: str, completed: bool) -> bool:
        """Flip the source task's completed flag.

        Prefers ``TaskItem.MarkComplete()`` (the canonical Outlook call —
        sets ``Complete``, ``PercentComplete=100``, ``DateCompleted=now``,
        and ``Status=olTaskComplete`` atomically). Falls back to
        ``item.Complete = bool(completed)`` for MailItems-flagged-as-tasks
        and other non-Task surfaces that don't expose ``MarkComplete``. For
        ``completed=False`` we always use the property assignment because
        Outlook has no inverse ``MarkIncomplete()`` method.
        """
        item = self._get_item(task_id)
        if item is None:
            return False
        current = bool(getattr(item, "Complete", False))
        if current == bool(completed):
            return True
        if completed and hasattr(item, "MarkComplete"):
            try:
                item.MarkComplete()
            except Exception:
                item.Complete = True
        else:
            item.Complete = bool(completed)
        item.Save()
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
