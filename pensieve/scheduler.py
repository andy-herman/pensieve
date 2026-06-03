"""Background auto-sync scheduler for the Pensieve FastAPI server.

Periodically calls the same sync code path as ``POST /api/sync`` so the
kanban stays current without manual "Pull from To-Do" clicks. Both the
HTTP route and the scheduler funnel through :func:`start_sync_job`, which
in turn relies on :meth:`pensieve.sync_state.SyncJobTracker.try_begin`
for an atomic single-job gate — so manual and scheduled syncs never
collide on Chroma's single-writer constraint.

Design notes:

- One daemon thread per scheduler instance. Each scheduled tick spawns
  ITS OWN sync worker thread (so the scheduler is free to keep ticking
  while a long sync runs). The worker thread handles its own COM
  ``CoInitialize`` / ``CoUninitialize`` bracket, identical to the
  manual-route runner — pywin32 requires per-thread apartments.
- The ``sample_file`` source is silently skipped because re-syncing a
  static JSON fixture every N minutes is pointless. A clear log line
  fires on startup so the operator sees this (helps Andy whose default
  source is sample_file but who runs against outlook_com via the
  ``PENSIEVE_AUTO_SYNC_SOURCE`` override).
- Repeated identical errors (e.g. Outlook closed for an hour) are
  collapsed so the console isn't spammed.
- Shutdown sets a stop event AND ``thread.join``s with a bounded
  timeout so uvicorn can exit cleanly without leaving COM apartments
  half-torn-down.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from rich.console import Console

from pensieve.config import Settings
from pensieve.sync_state import SyncJobTracker

console = Console()


def _sync_worker(
    settings: Settings,
    tracker: SyncJobTracker,
    src_name: str,
    list_names: list[str],
    force: bool,
) -> None:
    """Body of the spawned sync thread.

    Mirrors the code in ``POST /api/sync``'s ``_runner`` closure: COM
    bracket, build source, optional strand catalog + recent context for
    outlook_com, run_sync, finish on the tracker. Kept as a free function
    so both the API route and the scheduler can call into it without a
    circular import on ``pensieve.api.server``.
    """
    _com_inited = False
    try:
        try:
            import pythoncom  # type: ignore[import-not-found]

            pythoncom.CoInitialize()
            _com_inited = True
        except Exception:
            pass

        from pensieve.cli import _build_recent_context_from_chroma, _build_source
        from pensieve.sync import run_sync

        src = _build_source(src_name, list_names=list_names or None)
        strand_catalog = None
        recent_context = None
        if src_name == "outlook_com":
            if settings.samples_path.exists():
                import json as _json

                with settings.samples_path.open("r", encoding="utf-8") as f:
                    blob = _json.load(f)
                strand_catalog = blob.get("strand_catalog")
            recent_context = _build_recent_context_from_chroma()
        tracker.update("Enriching new and changed tasks...")
        stats = run_sync(
            src,
            strand_catalog=strand_catalog,
            recent_context=recent_context,
            dry_run=False,
            force=force,
        )
        tracker.finish_ok(
            {
                "total_tasks": stats.total_tasks,
                "new_enriched": stats.new_enriched,
                "updated_enriched": stats.updated_enriched,
                "skipped_unchanged": stats.skipped_unchanged,
                "deleted": stats.deleted,
                "failed": stats.failed,
                "review_queue": stats.review_queue,
                "tokens_used": stats.tokens_used,
            },
            message=(
                f"Sync complete: {stats.new_enriched} new, "
                f"{stats.updated_enriched} updated, "
                f"{stats.deleted} deleted, "
                f"{stats.skipped_unchanged} unchanged."
            ),
        )
    except Exception as e:
        tracker.finish_error(str(e))
    finally:
        if _com_inited:
            try:
                import pythoncom  # type: ignore[import-not-found]

                pythoncom.CoUninitialize()
            except Exception:
                pass


def start_sync_job(
    *,
    settings: Settings,
    tracker: SyncJobTracker,
    src_name: str,
    list_names: list[str],
    force: bool,
    thread_name: str = "pensieve-sync",
    worker: Callable[[Settings, SyncJobTracker, str, list[str], bool], None] = _sync_worker,
) -> Optional[threading.Thread]:
    """Atomically start a sync worker thread, or return None if one's already running.

    The atomicity guarantee comes from :meth:`SyncJobTracker.try_begin` —
    if it returns ``transitioned=False``, ANOTHER caller has already won
    the race and this caller MUST NOT spawn a thread (Chroma is
    single-writer; the second sync would corrupt the store and double-pay
    Outlook + LLM costs).

    Both ``POST /api/sync`` and :class:`AutoSyncScheduler` go through this
    function so the gate is honored uniformly.
    """
    transitioned, _ = tracker.try_begin(
        source=src_name, lists=list_names, message="Connecting to source..."
    )
    if not transitioned:
        return None

    t = threading.Thread(
        target=worker,
        args=(settings, tracker, src_name, list_names, force),
        daemon=True,
        name=thread_name,
    )
    tracker.attach_thread(t)
    t.start()
    return t


class AutoSyncScheduler:
    """Periodic sync runner. One instance per FastAPI app lifecycle."""

    def __init__(
        self,
        settings: Settings,
        tracker: SyncJobTracker,
        *,
        starter: Callable[..., Optional[threading.Thread]] = start_sync_job,
    ) -> None:
        self._settings = settings
        self._tracker = tracker
        self._starter = starter
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Collapse repeated identical errors (Outlook closed for an hour
        # shouldn't write 30 lines to the log).
        self._last_status: Optional[str] = None

    def start(self) -> bool:
        """Start the scheduler thread. Returns True if started, False if disabled."""
        interval = self._settings.auto_sync_interval_seconds
        if interval <= 0:
            console.print(
                "[dim]Auto-sync scheduler disabled "
                "(PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS=0).[/dim]"
            )
            return False
        src = self._resolve_source()
        if src == "sample_file":
            console.print(
                f"[yellow]Auto-sync scheduler is enabled but the resolved source is "
                f"'sample_file', so ticks will be no-ops. Set "
                f"PENSIEVE_AUTO_SYNC_SOURCE=outlook_com (or change "
                f"PENSIEVE_DEFAULT_SOURCE) to actually pull from Outlook every "
                f"{interval}s.[/yellow]"
            )
        else:
            console.print(
                f"[green]Auto-sync scheduler started:[/green] every {interval}s "
                f"from source '{src}'."
            )
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="pensieve-autosync"
        )
        self._thread.start()
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the scheduler to exit and wait briefly for it to join."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _resolve_source(self) -> str:
        override = (self._settings.auto_sync_source or "").strip()
        if override:
            return override
        return (self._settings.default_source or "outlook_com").strip()

    def _loop(self) -> None:
        interval = self._settings.auto_sync_interval_seconds
        # Wait the full interval before the first tick to avoid double-syncing
        # right after startup (the user may have just hit Pull from To-Do).
        while not self._stop.wait(interval):
            self._tick_once()

    def _tick_once(self) -> None:
        src = self._resolve_source()
        if src == "sample_file":
            return  # silent skip per startup banner

        try:
            t = self._starter(
                settings=self._settings,
                tracker=self._tracker,
                src_name=src,
                list_names=[],
                force=False,
                thread_name="pensieve-autosync-worker",
            )
            if t is None:
                self._log_once("skip-busy", "[dim]Auto-sync: a manual sync is in flight; skipping tick.[/dim]")
            else:
                self._log_once("ok", None)  # reset the suppression on a healthy tick
        except Exception as e:
            self._log_once(f"err:{e}", f"[red]Auto-sync error:[/red] {e}")

    def _log_once(self, status_key: str, message: Optional[str]) -> None:
        if self._last_status == status_key:
            return
        self._last_status = status_key
        if message is not None:
            console.print(message)
