"""In-memory sync job tracker for the API server.

Lets the dashboard kick off a sync via POST /api/sync and then poll
GET /api/sync/status until it finishes. Single-job: only one sync runs
at a time (Chroma is a single-writer store).
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SyncJobState:
    status: str = "idle"  # idle | running | done | error
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    source: Optional[str] = None
    lists: list[str] = field(default_factory=list)
    message: str = ""
    error: Optional[str] = None
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class SyncJobTracker:
    """Thread-safe single-job tracker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = SyncJobState()
        self._thread: Optional[threading.Thread] = None

    def snapshot(self) -> dict:
        with self._lock:
            return self._state.to_dict()

    def is_running(self) -> bool:
        with self._lock:
            return self._state.status == "running"

    def begin(self, *, source: str, lists: list[str], message: str = "Starting sync") -> dict:
        """Backward-compatible wrapper around try_begin that ignores the
        transition flag. New callers should prefer ``try_begin``.
        """
        _ok, snapshot = self.try_begin(source=source, lists=lists, message=message)
        return snapshot

    def try_begin(
        self, *, source: str, lists: list[str], message: str = "Starting sync"
    ) -> tuple[bool, dict]:
        """Atomic 'mark running if currently idle'. Returns (transitioned, snapshot).

        ``transitioned=True`` means this caller now owns the running job and
        must arrange for finish_ok/finish_error to be called. ``False`` means
        another sync was already in flight and the caller MUST NOT start a
        second one (Chroma is single-writer). Either way, ``snapshot`` is the
        current state — callers can inspect ``status`` to discriminate.
        """
        with self._lock:
            if self._state.status == "running":
                return False, self._state.to_dict()
            self._state = SyncJobState(
                status="running",
                started_at=datetime.now(timezone.utc).isoformat(),
                source=source,
                lists=list(lists or []),
                message=message,
            )
            return True, self._state.to_dict()

    def update(self, message: str) -> None:
        with self._lock:
            if self._state.status == "running":
                self._state.message = message

    def finish_ok(self, stats: dict, message: str = "Sync complete") -> None:
        with self._lock:
            self._state.status = "done"
            self._state.finished_at = datetime.now(timezone.utc).isoformat()
            self._state.stats = dict(stats)
            self._state.message = message
            self._state.error = None

    def finish_error(self, err: str) -> None:
        with self._lock:
            self._state.status = "error"
            self._state.finished_at = datetime.now(timezone.utc).isoformat()
            self._state.error = err
            self._state.message = f"Sync failed: {err}"

    def attach_thread(self, t: threading.Thread) -> None:
        with self._lock:
            self._thread = t


_TRACKER: Optional[SyncJobTracker] = None


def get_tracker() -> SyncJobTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = SyncJobTracker()
    return _TRACKER
