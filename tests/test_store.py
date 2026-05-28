"""Tests for the Chroma store (no LLM, in-process)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pensieve.config import get_settings
from pensieve.store import ChromaMemoryStore, Memory


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    """Isolate Chroma to a tmp dir per test."""
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()
    yield store
    get_settings.cache_clear()  # type: ignore[attr-defined]


def _mk_memory(
    id_="t1", title="Hello world", strand="dora-rfi", why="Because.", impact="Things happen."
) -> Memory:
    return Memory(
        id=id_,
        source="sample_file",
        source_task_id=id_,
        title=title,
        suggested_strand=strand,
        strand_kind="deep",
        why=why,
        impact=impact,
        confidence_strand=0.9,
        confidence_impact=0.8,
        connect_goal_ids=["goal-1-dora-deep-dive"],
        connect_alignment_confidence=0.95,
        connect_alignment_note="Direct DORA work.",
        source_last_modified=datetime.now(timezone.utc),
    )


def test_upsert_and_get(tmp_store):
    m = _mk_memory()
    tmp_store.upsert_memory(m)
    fetched = tmp_store.get_memory("t1")
    assert fetched is not None
    assert fetched.title == "Hello world"
    assert fetched.suggested_strand == "dora-rfi"
    assert fetched.connect_goal_ids == ["goal-1-dora-deep-dive"]


def test_idempotent_upsert(tmp_store):
    m = _mk_memory()
    tmp_store.upsert_memory(m)
    tmp_store.upsert_memory(m)
    assert tmp_store.count() == 1


def test_update_column(tmp_store):
    tmp_store.upsert_memory(_mk_memory())
    ok = tmp_store.update_column("t1", "dive")
    assert ok
    assert tmp_store.get_memory("t1").column == "dive"


def test_search_finds_match(tmp_store):
    tmp_store.upsert_memory(
        _mk_memory(id_="t1", title="DORA RFI response draft", why="JET asked.", impact="Closes RFI.")
    )
    tmp_store.upsert_memory(
        _mk_memory(id_="t2", title="Buy groceries", strand="personal-admin", why="Hungry.", impact="Eat.")
    )
    results = tmp_store.search("regulator RFI")
    assert len(results) >= 1
    assert results[0].id == "t1"


def test_known_ids(tmp_store):
    tmp_store.upsert_memory(_mk_memory(id_="t1"))
    tmp_store.upsert_memory(_mk_memory(id_="t2"))
    assert tmp_store.known_ids() == {"t1", "t2"}


def test_dashboard_dict_shape(tmp_store):
    tmp_store.upsert_memory(_mk_memory())
    m = tmp_store.get_memory("t1")
    d = m.to_dashboard_dict()
    assert d["id"] == "mem_t1"
    assert d["title"] == "Hello world"
    assert d["connect_goal_ids"] == ["goal-1-dora-deep-dive"]
