"""Sync reads the store in bulk (no per-task get), and recent context tolerates naive timestamps."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from pensieve.config import get_settings
from pensieve.sources.sample_file import SampleFileSource
from pensieve.store import ChromaMemoryStore, Memory
from pensieve.sync import run_sync

UTC = timezone.utc


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


def _write_sample(path, tasks: list[dict]) -> None:
    payload = {
        "strand_catalog": [{"id": "x", "label": "x", "kind": "tactical", "context": ""}],
        "recent_context": {"user_recent_strands": [], "recent_titles_in_same_list": []},
        "tasks": tasks,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_unchanged_sync_does_no_per_task_reads(tmp_path, monkeypatch):
    created = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    tasks = [
        {"id": f"t{i}", "title": f"Task {i}", "notes": "n", "list_name": "L", "created_at": created}
        for i in range(5)
    ]
    samples = tmp_path / "samples.json"
    _write_sample(samples, tasks)
    source = SampleFileSource(samples)

    store = ChromaMemoryStore()
    for raw in source.list_tasks():
        store.upsert_memory(
            Memory(
                id=raw.id,
                source=raw.source,
                source_task_id=raw.id,
                list_name=raw.list_name,
                title=raw.title,
                original_notes=raw.notes,
                source_last_modified=raw.last_modification_time,
            )
        )

    calls: list[str] = []
    real_get_memory = ChromaMemoryStore.get_memory

    def counting_get_memory(self, memory_id):
        calls.append(memory_id)
        return real_get_memory(self, memory_id)

    monkeypatch.setattr(ChromaMemoryStore, "get_memory", counting_get_memory)
    stats = run_sync(source, dry_run=True)
    assert stats.total_tasks == 5
    assert stats.skipped_unchanged == 5
    assert calls == []


def test_recent_context_tolerates_naive_enriched_at():
    from pensieve.cli import _build_recent_context_from_chroma

    store = ChromaMemoryStore()
    store.upsert_memory(
        Memory(
            id="aware",
            source="sample_file",
            source_task_id="aware",
            title="aware task",
            suggested_strand="Strand A",
            enriched_at=datetime.now(UTC),
        )
    )
    store.upsert_memory(
        Memory(
            id="naive",
            source="sample_file",
            source_task_id="naive",
            title="naive task",
            suggested_strand="Strand B",
            enriched_at=datetime(2026, 1, 1, 12, 0, 0),  # no tzinfo, as older rows may have
        )
    )
    ctx = _build_recent_context_from_chroma()
    assert ctx["recent_titles_in_same_list"] == ["aware task", "naive task"]
    assert ctx["user_recent_strands"] == ["Strand A", "Strand B"]
