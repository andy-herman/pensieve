"""Read cache for whole-collection Chroma scans: hits, and invalidation on every write path."""

from __future__ import annotations

import sqlite3

import pytest
from chromadb.api.models.Collection import Collection

from pensieve.config import get_settings
from pensieve.store import ChromaMemoryStore, ChromaVialStore, Memory, Vial, read_cache


@pytest.fixture()
def stores(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    read_cache.clear()
    yield ChromaMemoryStore(), ChromaVialStore()
    read_cache.clear()


@pytest.fixture()
def get_calls(monkeypatch):
    """Count full-collection Collection.get() calls (no ids / where filter)."""
    calls: list[str] = []
    real_get = Collection.get

    def counting_get(self, *args, **kwargs):
        if not args and kwargs.get("ids") is None and kwargs.get("where") is None:
            calls.append(self.name)
        return real_get(self, *args, **kwargs)

    monkeypatch.setattr(Collection, "get", counting_get)
    return calls


def _mem(mid: str, title: str = "t", column: str = "memory") -> Memory:
    return Memory(
        id=mid,
        source="sample_file",
        source_task_id=mid,
        title=title,
        why="why",
        impact="impact",
        column=column,
    )


def test_repeat_reads_hit_cache(stores, get_calls):
    store, vials = stores
    store.upsert_memory(_mem("m1"))
    get_calls.clear()
    for _ in range(3):
        assert [m.id for m in store.list_memories()] == ["m1"]
        assert store.known_ids() == {"m1"}
    assert get_calls == ["memories"]
    for _ in range(3):
        vials.captured_count_by_memory()
        vials.has_any_vial_by_memory()
        vials.list_vials()
    assert get_calls == ["memories", "vials"]


def test_invalidated_by_upsert_update_and_delete(stores):
    store, _ = stores
    store.upsert_memory(_mem("m1", title="first"))
    assert [m.title for m in store.list_memories()] == ["first"]
    store.upsert_memory(_mem("m1", title="renamed"))
    assert [m.title for m in store.list_memories()] == ["renamed"]
    store.update_meta("m1", {"column": "dive"})
    assert [m.column for m in store.list_memories()] == ["dive"]
    store.upsert_memory(_mem("m2"))
    assert store.known_ids() == {"m1", "m2"}
    store.delete_memory("m1")
    assert store.known_ids() == {"m2"}


def test_invalidated_by_another_store_instance(stores):
    """The sync worker writes through its own ChromaMemoryStore instance."""
    store, _ = stores
    store.upsert_memory(_mem("m1"))
    assert store.known_ids() == {"m1"}
    other = ChromaMemoryStore()
    other.upsert_memory(_mem("m2"))
    other.update_meta("m1", {"column": "closed"})
    by_id = {m.id: m for m in store.list_memories()}
    assert set(by_id) == {"m1", "m2"}
    assert by_id["m1"].column == "closed"


def test_invalidated_by_direct_collection_write(stores):
    store, _ = stores
    store.upsert_memory(_mem("m1"))
    assert store.known_ids() == {"m1"}
    meta = _mem("m2").to_chroma_metadata()
    store._memories.upsert(ids=["m2"], documents=["doc"], metadatas=[meta])
    assert store.known_ids() == {"m1", "m2"}


def test_invalidated_by_external_sqlite_commit(stores, get_calls):
    """Any other connection's commit (e.g. another process) forces a refetch."""
    store, _ = stores
    store.upsert_memory(_mem("m1"))
    store.list_memories()
    get_calls.clear()
    store.list_memories()
    assert get_calls == []
    db = store.settings.chroma_dir / read_cache.DB_FILENAME
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS pensieve_test_probe (x INTEGER)")
    conn.commit()
    conn.close()
    store.list_memories()
    assert get_calls == ["memories"]


def test_vial_reads_invalidated_by_vial_writes(stores):
    store, vials = stores
    m = _mem("m1", column="closed")
    store.upsert_memory(m)
    assert vials.captured_count_by_memory() == {}
    v = Vial.snapshot_from(m, captured_text="shipped it")
    vials.upsert_vial(v)
    assert vials.captured_count_by_memory() == {"m1": 1}
    assert vials.has_any_vial_by_memory() == {"m1"}
    assert [x.id for x in vials.list_vials()] == [v.id]
    vials.delete_vial(v.id)
    assert vials.captured_count_by_memory() == {}
    assert vials.list_vials() == []


def test_returned_memories_are_independent_copies(stores):
    store, _ = stores
    store.upsert_memory(_mem("m1", title="original"))
    first = store.list_memories()
    first[0].title = "mutated by a caller"
    first[0].connect_goal_ids.append("g1")
    again = store.list_memories()
    assert again[0].title == "original"
    assert again[0].connect_goal_ids == []


def test_falls_back_to_direct_reads_when_version_unknown(stores, get_calls, monkeypatch):
    store, _ = stores
    store.upsert_memory(_mem("m1"))
    monkeypatch.setattr(read_cache, "data_version", lambda key: None)
    get_calls.clear()
    store.list_memories()
    store.list_memories()
    assert get_calls == ["memories", "memories"]


def test_reopened_connection_never_matches_old_versions(stores, get_calls):
    """data_version numbering restarts per connection; versions carry a connection token."""
    store, _ = stores
    store.upsert_memory(_mem("m1"))
    store.list_memories()
    key = store._cache_key
    v1 = read_cache.data_version(key)
    with read_cache._lock:
        read_cache._close(key)
    v2 = read_cache.data_version(key)
    assert v1 is not None and v2 is not None
    assert v1[0] != v2[0]
    get_calls.clear()
    store.list_memories()
    assert get_calls == ["memories"]
