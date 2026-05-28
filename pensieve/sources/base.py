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

    def health_check(self) -> tuple[bool, str]:
        """Return (ok, message). Default just tries to list one task."""
        try:
            for _ in self.list_tasks():
                return True, f"{self.name}: reachable"
            return True, f"{self.name}: reachable (no tasks)"
        except Exception as e:
            return False, f"{self.name}: {e}"
