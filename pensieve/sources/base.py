"""Abstract task source interface. All implementations are READ-ONLY."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Optional

from pydantic import BaseModel, Field


class RawTask(BaseModel):
    """Source-agnostic representation of a To-Do task."""

    id: str = Field(..., description="Stable per-source identifier (Outlook EntryID, sample id, etc.)")
    title: str
    notes: str = ""
    list_name: str = ""
    created_at: Optional[datetime] = None
    last_modification_time: Optional[datetime] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    categories: list[str] = Field(default_factory=list)
    due_date: Optional[datetime] = None
    source: str = "unknown"


class TaskSource(ABC):
    """Read-only interface for any backing store of To-Do tasks.

    Implementations MUST NOT mutate the upstream store. The pull-only contract
    is what keeps Pensieve safe against the user's real To-Do data.
    """

    name: str = "unknown"

    @abstractmethod
    def list_tasks(self) -> Iterable[RawTask]:
        """Yield every task this source surfaces (filters applied)."""

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[RawTask]:
        """Fetch a single task by its source-specific id, or None if not present."""

    def covered_lists(self) -> Optional[set[str]]:
        """Return the set of list_name values this source is responsible for.

        Used by the sync orchestrator's deletion sweep: a task previously
        ingested from list X should only be considered "deleted at source" if
        we actually scanned list X this run. Returning ``None`` means the
        source covers EVERY list — any memory of this source not in the
        current pull is fair game for deletion.

        Implementations that filter (e.g. OutlookCOMSource with ``list_names``)
        SHOULD record the names of folders/lists they walked during
        ``list_tasks()`` and surface them here. Otherwise a user who narrows
        to one list would have memories from other lists silently deleted.
        """
        return None

    def health_check(self) -> tuple[bool, str]:
        """Return (ok, message). Default just tries to list one task."""
        try:
            for _ in self.list_tasks():
                return True, f"{self.name}: reachable"
            return True, f"{self.name}: reachable (no tasks)"
        except Exception as e:
            return False, f"{self.name}: {e}"
