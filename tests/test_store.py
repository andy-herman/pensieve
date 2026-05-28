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


def test_find_orphan_ids_scoped_to_source(tmp_store):
    """Sync of source A must never orphan memories of source B."""
    m_sample = _mk_memory(id_="sample-1")  # source=sample_file
    m_outlook = _mk_memory(id_="ol-1")
    m_outlook.source = "outlook_com"
    m_outlook.source_task_id = "ol-1"
    tmp_store.upsert_memory(m_sample)
    tmp_store.upsert_memory(m_outlook)

    # A sync of outlook_com that returns NO live ids should orphan ol-1 only.
    orphans = tmp_store.find_orphan_ids(source="outlook_com", live_ids=set())
    orphan_ids = {mid for mid, _, _ in orphans}
    assert orphan_ids == {"ol-1"}, "sample_file memory must NOT be orphaned by an outlook sync"


def test_find_orphan_ids_respects_covered_lists(tmp_store):
    """Sync that only covers list X must not orphan memories in list Y."""
    m_in_scope = _mk_memory(id_="a")
    m_in_scope.list_name = "Agentic AI work"
    m_in_scope.source = "outlook_com"
    m_out_of_scope = _mk_memory(id_="b")
    m_out_of_scope.list_name = "CISO GRC"
    m_out_of_scope.source = "outlook_com"
    tmp_store.upsert_memory(m_in_scope)
    tmp_store.upsert_memory(m_out_of_scope)

    # Sync covered only "Agentic AI work" and returned no live ids.
    orphans = tmp_store.find_orphan_ids(
        source="outlook_com",
        live_ids=set(),
        covered_lists={"Agentic AI work"},
    )
    orphan_ids = {mid for mid, _, _ in orphans}
    assert orphan_ids == {"a"}, "memory in uncovered list must NOT be considered orphan"


def test_find_orphan_ids_skips_live_tasks(tmp_store):
    """Memories still present in the source pull are never orphaned."""
    m1 = _mk_memory(id_="a")
    m1.source = "outlook_com"
    m2 = _mk_memory(id_="b")
    m2.source = "outlook_com"
    tmp_store.upsert_memory(m1)
    tmp_store.upsert_memory(m2)
    orphans = tmp_store.find_orphan_ids(source="outlook_com", live_ids={"a", "b"})
    assert orphans == []


def test_dashboard_dict_shape(tmp_store):
    tmp_store.upsert_memory(_mk_memory())
    m = tmp_store.get_memory("t1")
    d = m.to_dashboard_dict()
    assert d["id"] == "mem_t1"
    assert d["title"] == "Hello world"
    assert d["connect_goal_ids"] == ["goal-1-dora-deep-dive"]
