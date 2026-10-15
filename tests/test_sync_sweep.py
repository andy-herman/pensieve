"""The sync's deletion sweep must not mistake an unreadable task for a deleted one."""

from __future__ import annotations

import pytest

from pensieve.config import get_settings
from pensieve.sources.base import TaskSource
from pensieve.store import ChromaMemoryStore
from pensieve.sync import run_sync


class _EmptySource(TaskSource):
    name = "outlook_com"

    def __init__(self, read_errors: int) -> None:
        self._errors = read_errors

    def list_tasks(self):
        self.read_errors = self._errors
        return iter(())

    def get_task(self, task_id):
        return None


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def _run(source: TaskSource, monkeypatch) -> list[str]:
    calls: list[str] = []
    orig = ChromaMemoryStore.find_orphan_ids

    def spy(self, *a, **kw):
        calls.append("swept")
        return orig(self, *a, **kw)

    monkeypatch.setattr(ChromaMemoryStore, "find_orphan_ids", spy)
    run_sync(source, strand_catalog=[], dry_run=True)
    return calls


def test_sweep_skipped_when_tasks_failed_to_read(settings, monkeypatch):
    assert _run(_EmptySource(read_errors=2), monkeypatch) == []


def test_sweep_runs_on_a_clean_read(settings, monkeypatch):
    assert _run(_EmptySource(read_errors=0), monkeypatch) == ["swept"]
