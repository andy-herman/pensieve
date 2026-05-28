"""Outlook desktop COM TaskSource. READ-ONLY against the running Outlook client.

This source intentionally has NO write methods. Pensieve's pull-only contract
is enforced by the source surface, not just by convention.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from pensieve.sources.base import RawTask, TaskSource


class OutlookCOMUnavailable(RuntimeError):
    pass


def _to_aware(dt) -> Optional[datetime]:
    if dt is None:
        return None
    try:
        if isinstance(dt, str):
            return datetime.fromisoformat(dt)
        if hasattr(dt, "year"):
            return datetime(
                dt.year,
                dt.month,
                dt.day,
                getattr(dt, "hour", 0),
                getattr(dt, "minute", 0),
                getattr(dt, "second", 0),
                tzinfo=timezone.utc,
            )
    except Exception:
        return None
    return None


class OutlookCOMSource(TaskSource):
    """Reads the default Tasks folder from a running Outlook desktop client.

    Requirements:
      - Windows
      - Outlook desktop installed and the user signed in
      - pywin32 installed (`pip install pywin32`)

    The class never calls Save() on a task item.
    """

    name = "outlook_com"

    OL_FOLDER_TASKS = 13  # Outlook.OlDefaultFolders.olFolderTasks

    def __init__(
        self,
        list_name: Optional[str] = None,
        skip_completed_older_than_days: int = 30,
        include_subfolders: bool = False,
    ):
        self.list_name = list_name
        self.skip_completed_older_than_days = skip_completed_older_than_days
        self.include_subfolders = include_subfolders
        self._app = None
        self._ns = None

    def _connect(self):
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

    def _tasks_folder(self):
        self._connect()
        root = self._ns.GetDefaultFolder(self.OL_FOLDER_TASKS)
        if self.list_name and self.list_name.lower() != "tasks":
            for folder in root.Folders:
                if folder.Name.lower() == self.list_name.lower():
                    return folder
        return root

    def _iter_items(self, folder):
        items = folder.Items
        try:
            items.Sort("[LastModificationTime]", True)
        except Exception:
            pass
        for item in items:
            yield item
        if self.include_subfolders:
            for sub in folder.Folders:
                yield from self._iter_items(sub)

    def _should_skip(self, item) -> bool:
        try:
            if bool(getattr(item, "Complete", False)):
                completed_at = _to_aware(getattr(item, "DateCompleted", None))
                if completed_at is None:
                    return False
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.skip_completed_older_than_days)
                if completed_at < cutoff:
                    return True
        except Exception:
            return False
        return False

    def _to_raw(self, item) -> Optional[RawTask]:
        try:
            entry_id = getattr(item, "EntryID", None)
            if not entry_id:
                return None
            title = (getattr(item, "Subject", "") or "").strip()
            if not title:
                return None
            body = getattr(item, "Body", "") or ""
            categories = [c.strip() for c in (getattr(item, "Categories", "") or "").split(",") if c.strip()]
            created = _to_aware(getattr(item, "CreationTime", None))
            modified = _to_aware(getattr(item, "LastModificationTime", None))
            due = _to_aware(getattr(item, "DueDate", None))
            completed = bool(getattr(item, "Complete", False))
            completed_at = _to_aware(getattr(item, "DateCompleted", None)) if completed else None
            return RawTask(
                id=entry_id,
                title=title,
                notes=body,
                list_name=self.list_name or "Tasks",
                created_at=created,
                last_modification_time=modified,
                completed=completed,
                completed_at=completed_at,
                categories=categories,
                due_date=due,
                source=self.name,
            )
        except Exception:
            return None

    def list_tasks(self) -> Iterator[RawTask]:
        folder = self._tasks_folder()
        for item in self._iter_items(folder):
            if self._should_skip(item):
                continue
            raw = self._to_raw(item)
            if raw is not None:
                yield raw

    def get_task(self, task_id: str) -> Optional[RawTask]:
        self._connect()
        try:
            item = self._ns.GetItemFromID(task_id)
        except Exception:
            return None
        return self._to_raw(item)
