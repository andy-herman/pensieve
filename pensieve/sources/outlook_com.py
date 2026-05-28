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
    """Reads task folders from a running Outlook desktop client.

    By default, enumerates the default Tasks folder PLUS every Microsoft
    To-Do list (which Outlook surfaces as child folders of the default
    Tasks folder). Use ``list_names`` to filter to specific lists by name.

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
        list_names: Optional[list[str]] = None,
        skip_completed_older_than_days: int = 30,
        include_subfolders: bool = True,
    ):
        """
        :param list_names: If provided, restrict to these list names (case-insensitive
            match against folder Name). If None or empty, pull from ALL lists
            (default Tasks folder + every To-Do list folder under it).
        :param skip_completed_older_than_days: Drop completed tasks finished
            before this cutoff.
        :param include_subfolders: When True (default), walk subfolders of each
            matched folder. Set False to restrict to the matched folder only.
        """
        self.list_names = [n.strip() for n in (list_names or []) if n and n.strip()]
        self.skip_completed_older_than_days = skip_completed_older_than_days
        self.include_subfolders = include_subfolders
        self._app = None
        self._ns = None
        # Populated during list_tasks() so the sync orchestrator's deletion
        # sweep knows which lists we covered (and therefore which previously
        # ingested memories are safe to consider orphans).
        self._last_covered_lists: Optional[set[str]] = None

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

    def _root_tasks_folder(self):
        self._connect()
        return self._ns.GetDefaultFolder(self.OL_FOLDER_TASKS)

    def _iter_candidate_folders(self):
        """Yield (display_name, folder) for every task folder we should read.

        Microsoft To-Do lists land as child folders of the default Tasks
        folder. We yield the default folder itself first, then each child
        (and grandchildren if include_subfolders is True).
        """
        root = self._root_tasks_folder()
        yield (root.Name or "Tasks", root)
        if self.include_subfolders:
            yield from self._walk_subfolders(root)

    @classmethod
    def _walk_subfolders(cls, folder):
        try:
            children = folder.Folders
        except Exception:
            return
        for sub in children:
            yield (sub.Name or "", sub)
            yield from cls._walk_subfolders(sub)

    def _selected_folders(self):
        """Apply list_names filter (if any) over the candidate folders."""
        wanted = {n.lower() for n in self.list_names} if self.list_names else None
        for name, folder in self._iter_candidate_folders():
            if wanted is None or name.lower() in wanted:
                yield (name, folder)

    def _iter_items(self, folder):
        items = folder.Items
        try:
            items.Sort("[LastModificationTime]", True)
        except Exception:
            pass
        for item in items:
            yield item

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

    def _to_raw(self, item, list_name: str) -> Optional[RawTask]:
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
                list_name=list_name,
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
        # Reset coverage tracking for this run. We accumulate folder names
        # below so covered_lists() can report exactly what we scanned (even
        # for folders that turned out to be empty).
        covered: set[str] = set()
        for folder_name, folder in self._selected_folders():
            covered.add(folder_name)
            for item in self._iter_items(folder):
                if self._should_skip(item):
                    continue
                raw = self._to_raw(item, folder_name)
                if raw is not None:
                    yield raw
        self._last_covered_lists = covered

    def covered_lists(self) -> Optional[set[str]]:
        return None if self._last_covered_lists is None else set(self._last_covered_lists)

    def get_task(self, task_id: str) -> Optional[RawTask]:
        self._connect()
        try:
            item = self._ns.GetItemFromID(task_id)
        except Exception:
            return None
        list_name = "Tasks"
        try:
            parent = item.Parent
            if parent is not None and getattr(parent, "Name", None):
                list_name = parent.Name
        except Exception:
            pass
        return self._to_raw(item, list_name)

    def discover_lists(self) -> list[dict]:
        """Enumerate available task folders (Microsoft To-Do lists) with a count.

        Returns a list of dicts with keys: ``name``, ``item_count``, ``entry_id``.
        Read-only; used by the ``pensieve lists`` command.
        """
        out = []
        for name, folder in self._iter_candidate_folders():
            try:
                count = folder.Items.Count
            except Exception:
                count = -1
            try:
                entry_id = folder.EntryID
            except Exception:
                entry_id = ""
            out.append({"name": name, "item_count": count, "entry_id": entry_id})
        return out
