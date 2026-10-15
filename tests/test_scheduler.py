"""Tests for the background auto-sync scheduler.

Covers:
- ``start_sync_job`` honors the atomic try_begin gate (no double-start)
- ``start_sync_job`` returns a Thread on first call, None when busy
- ``AutoSyncScheduler`` fires the worker periodically based on
  ``settings.auto_sync_interval_seconds``
- The scheduler silently skips ticks when the resolved source is
  ``sample_file`` (so accidental sample_file auto-sync isn't a footgun)
- ``stop()`` cleanly joins the loop thread
- The atomic gate prevents two concurrent kick_off_sync calls from
  spawning two worker threads (the rubber-duck "race window" finding)
"""

from __future__ import annotations

import threading
import time

from pensieve.config import Settings
from pensieve.scheduler import AutoSyncScheduler, start_sync_job
from pensieve.sync_state import SyncJobTracker


def _settings(**overrides) -> Settings:
    base = Settings()
    return base.model_copy(update=overrides)


def _fake_worker_factory(barrier: threading.Event, started: list[str]):
    """Worker that simulates a slow sync (blocks on barrier, then finishes_ok)."""

    def _worker(settings, tracker, src_name, list_names, force):
        started.append(src_name)
        barrier.wait(timeout=2.0)
        tracker.finish_ok({}, message="ok")

    return _worker


# ---------- start_sync_job atomic gate ----------


def test_start_sync_job_returns_thread_when_idle():
    tracker = SyncJobTracker()
    settings = _settings(default_source="outlook_com")
    finished = threading.Event()

    def _quick_worker(s, tr, name, lists, force):
        tr.finish_ok({}, message="ok")
        finished.set()

    t = start_sync_job(
        settings=settings,
        tracker=tracker,
        src_name="outlook_com",
        list_names=[],
        force=False,
        worker=_quick_worker,
    )
    assert t is not None
    assert finished.wait(timeout=2.0), "worker never finished"
    t.join(timeout=2.0)
    assert tracker.snapshot()["status"] == "done"


def test_start_sync_job_returns_none_when_already_running():
    """The second caller must NOT spawn a second worker thread — Chroma is
    single-writer and a concurrent run would corrupt the store + double-pay
    Outlook + LLM costs."""
    tracker = SyncJobTracker()
    settings = _settings(default_source="outlook_com")
    started: list[str] = []
    barrier = threading.Event()

    t1 = start_sync_job(
        settings=settings,
        tracker=tracker,
        src_name="outlook_com",
        list_names=[],
        force=False,
        worker=_fake_worker_factory(barrier, started),
    )
    assert t1 is not None

    # Second call while the first is in flight must be rejected.
    t2 = start_sync_job(
        settings=settings,
        tracker=tracker,
        src_name="outlook_com",
        list_names=[],
        force=False,
        worker=_fake_worker_factory(barrier, started),
    )
    assert t2 is None

    # Let the first worker finish so the test doesn't leave a hanging thread.
    barrier.set()
    t1.join(timeout=2.0)
    assert started == ["outlook_com"], "expected exactly one worker spawn"


def test_concurrent_starts_only_one_wins():
    """Race test — fire 10 threads at start_sync_job simultaneously and
    assert that exactly one transitions the tracker."""
    tracker = SyncJobTracker()
    settings = _settings(default_source="outlook_com")
    started: list[str] = []
    barrier = threading.Event()
    threads_returned: list[threading.Thread | None] = []
    gate = threading.Event()
    lock = threading.Lock()

    def _attempt():
        gate.wait(timeout=2.0)
        t = start_sync_job(
            settings=settings,
            tracker=tracker,
            src_name="outlook_com",
            list_names=[],
            force=False,
            worker=_fake_worker_factory(barrier, started),
        )
        with lock:
            threads_returned.append(t)

    contenders = [threading.Thread(target=_attempt) for _ in range(10)]
    for c in contenders:
        c.start()
    gate.set()
    for c in contenders:
        c.join(timeout=2.0)

    spawned = [t for t in threads_returned if t is not None]
    assert len(spawned) == 1, f"expected exactly one winner, got {len(spawned)}"

    barrier.set()
    spawned[0].join(timeout=2.0)
    assert started == ["outlook_com"]


# ---------- AutoSyncScheduler periodic firing ----------


def test_scheduler_calls_starter_periodically():
    """With a 0.1s interval the scheduler should call the starter at least
    twice within ~0.4s."""
    tracker = SyncJobTracker()
    settings = _settings(
        default_source="outlook_com",
        auto_sync_interval_seconds=0,  # we override at the scheduler level
    )
    # bypass the disable-check in start() by patching the int directly
    settings = settings.model_copy(update={"auto_sync_interval_seconds": 1})

    calls = []

    def _fake_starter(*, settings, tracker, src_name, list_names, force, thread_name=""):
        calls.append(src_name)
        return None  # simulate "skip: busy" but still count the attempt

    scheduler = AutoSyncScheduler(settings, tracker, starter=_fake_starter)
    # Manually shorten the interval used by _loop. _loop reads
    # `self._settings.auto_sync_interval_seconds` once at start, so we
    # mutate the resolved value via model_copy before start().
    scheduler._settings = settings.model_copy(
        update={"auto_sync_interval_seconds": 1}
    )
    # Override to a much shorter interval for the test by monkey-patching
    # the loop method's wait time via a tighter settings clone:
    scheduler._settings = scheduler._settings.model_copy(
        update={"auto_sync_interval_seconds": 1}
    )
    # Replace the loop with a short-interval variant so the test runs fast.
    def _short_loop():
        while not scheduler._stop.wait(0.1):
            scheduler._tick_once()

    scheduler._loop = _short_loop  # type: ignore[assignment]

    assert scheduler.start() is True
    try:
        time.sleep(0.4)
    finally:
        scheduler.stop(timeout=2.0)

    # Should have ticked at least twice in ~0.4s of 0.1s waits.
    assert len(calls) >= 2, f"expected >=2 ticks, got {len(calls)}"
    assert all(c == "outlook_com" for c in calls)


def test_scheduler_disabled_when_interval_is_zero():
    tracker = SyncJobTracker()
    settings = _settings(auto_sync_interval_seconds=0)
    calls: list[str] = []

    def _starter(**kwargs):
        calls.append("called")
        return None

    scheduler = AutoSyncScheduler(settings, tracker, starter=_starter)
    assert scheduler.start() is False
    time.sleep(0.2)
    scheduler.stop(timeout=1.0)
    assert calls == []


def test_scheduler_skips_sample_file_source():
    """sample_file ticks must be silent no-ops — re-syncing a static JSON
    fixture every N minutes is pointless and would spam the logs."""
    tracker = SyncJobTracker()
    settings = _settings(
        default_source="sample_file",
        auto_sync_source="",  # falls through to default_source
        auto_sync_interval_seconds=1,
    )
    calls: list[str] = []

    def _starter(**kwargs):
        calls.append(kwargs["src_name"])
        return None

    scheduler = AutoSyncScheduler(settings, tracker, starter=_starter)
    # Skip the wait window and call _tick_once directly.
    scheduler._tick_once()
    scheduler._tick_once()
    assert calls == [], "sample_file ticks must be silent no-ops"


def test_scheduler_uses_auto_sync_source_override():
    """When auto_sync_source is set, scheduler ticks use it instead of
    default_source. This lets a user keep default_source=sample_file (for
    cheap CLI work) while having auto-sync hit outlook_com."""
    tracker = SyncJobTracker()
    settings = _settings(
        default_source="sample_file",
        auto_sync_source="outlook_com",
        auto_sync_interval_seconds=1,
    )
    calls: list[str] = []

    def _starter(**kwargs):
        calls.append(kwargs["src_name"])
        return None

    scheduler = AutoSyncScheduler(settings, tracker, starter=_starter)
    scheduler._tick_once()
    assert calls == ["outlook_com"]


def test_scheduler_stop_joins_loop_thread():
    tracker = SyncJobTracker()
    settings = _settings(
        default_source="outlook_com", auto_sync_interval_seconds=60
    )

    def _starter(**kwargs):
        return None

    scheduler = AutoSyncScheduler(settings, tracker, starter=_starter)
    scheduler.start()
    assert scheduler._thread is not None
    scheduler.stop(timeout=2.0)
    assert scheduler._thread is not None
    assert not scheduler._thread.is_alive()


# ---------- _sync_worker: COM teardown order + failure logging ----------


class _FakePythoncom:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def CoInitialize(self) -> None:
        self.events.append("init")

    def CoUninitialize(self) -> None:
        self.events.append("uninit")


class _ComHoldingSource:
    """Stands in for OutlookCOMSource: records when its last reference goes away."""

    name = "outlook_com"

    def __init__(self, events: list[str]) -> None:
        self._events = events

    def __del__(self) -> None:
        self._events.append("source-released")


def test_sync_worker_releases_source_before_couninitialize(monkeypatch, tmp_path):
    import sys

    import pensieve.cli as cli
    import pensieve.sync as sync_mod
    from pensieve.scheduler import _sync_worker
    from pensieve.sync import SyncStats

    events: list[str] = []
    monkeypatch.setitem(sys.modules, "pythoncom", _FakePythoncom(events))
    monkeypatch.setattr(cli, "_build_source", lambda name, list_names=None: _ComHoldingSource(events))
    monkeypatch.setattr(cli, "_build_recent_context_from_chroma", lambda: {})
    monkeypatch.setattr(sync_mod, "run_sync", lambda src, **kw: SyncStats(total_tasks=1))

    tracker = SyncJobTracker()
    tracker.try_begin(source="outlook_com", lists=[])
    _sync_worker(_settings(data_dir=tmp_path), tracker, "outlook_com", [], False)
    assert tracker.snapshot()["status"] == "done"
    assert events == ["init", "source-released", "uninit"]


def test_sync_worker_logs_each_distinct_failure_once(monkeypatch, tmp_path, caplog):
    import logging
    import sys

    import pensieve.cli as cli
    import pensieve.scheduler as sched

    events: list[str] = []
    monkeypatch.setitem(sys.modules, "pythoncom", _FakePythoncom(events))
    monkeypatch.setattr(sched, "_last_logged_failure", None)
    errors = iter(
        [RuntimeError("Outlook closed"), RuntimeError("Outlook closed"), ValueError("bad list")]
    )

    def failing_build(name, list_names=None):
        src = _ComHoldingSource(events)  # noqa: F841 - held by the failing frame
        raise next(errors)

    monkeypatch.setattr(cli, "_build_source", failing_build)
    tracker = SyncJobTracker()
    with caplog.at_level(logging.ERROR, logger="pensieve.scheduler"):
        for _ in range(3):
            tracker.try_begin(source="outlook_com", lists=[])
            sched._sync_worker(_settings(data_dir=tmp_path), tracker, "outlook_com", [], False)
            assert tracker.snapshot()["status"] == "error"

    logged = [r for r in caplog.records if r.name == "pensieve.scheduler"]
    assert [r.getMessage() for r in logged] == [
        "Sync failed: RuntimeError: Outlook closed",
        "Sync failed: ValueError: bad list",
    ]
    assert all(r.exc_info for r in logged)
    # Even on failure, the source is released before the apartment is torn down.
    assert events[:3] == ["init", "source-released", "uninit"]
