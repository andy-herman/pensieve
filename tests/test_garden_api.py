"""TestClient tests for Garden v1 API: board-health endpoint + tending bumps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from pensieve.api.server import create_app
from pensieve.config import get_settings
from pensieve.store import ChromaMemoryStore, Memory


UTC = timezone.utc


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_ENABLED", "false")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    app = create_app()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture()
def seed(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()

    def _seed(
        mid: str = "m1",
        *,
        column: str = "memory",
        last_tended_at: datetime | None = None,
        enriched_at: datetime | None = None,
        due_date: datetime | None = None,
    ) -> Memory:
        m = Memory(
            id=mid,
            source="sample_file",
            source_task_id=mid,
            list_name="CISO GRC",
            title=f"Memory {mid}",
            display_title=f"Memory {mid}",
            why="why",
            impact="impact",
            column=column,
            last_tended_at=last_tended_at,
            enriched_at=enriched_at or datetime.now(UTC) - timedelta(days=1),
            due_date=due_date,
            completed=(column == "closed"),
            completed_at=datetime.now(UTC) if column == "closed" else None,
        )
        store.upsert_memory(m)
        return m

    return _seed


# --- GET /api/board/health --------------------------------------------------


def test_board_health_empty_returns_100(client):
    res = client.get("/api/board/health")
    assert res.status_code == 200
    body = res.json()
    assert body["score"] == 100
    assert body["tier"] == "green"
    assert body["counts"] == {"open": 0, "closed": 0, "captured_closed": 0}
    assert body["terms"]["stale_count"] == 0


def test_board_health_with_stale_card(seed, client):
    seed("m1", last_tended_at=datetime.now(UTC) - timedelta(days=20))
    body = client.get("/api/board/health").json()
    assert body["terms"]["stale_count"] == 1
    assert body["score"] < 100


def test_board_health_skipped_vial_doesnt_inflate_capture(seed, client):
    """Skipping a Vial must NOT count as captured evidence."""
    seed("m1", column="closed")
    client.post(
        "/api/memories/m1/vials",
        json={"capture_kind": "skipped", "captured_text": ""},
    )
    body = client.get("/api/board/health").json()
    # 1 closed, 0 captured → capture_pct = 0
    assert body["terms"]["capture_pct"] == 0.0
    assert body["counts"]["captured_closed"] == 0


# --- freshness enrichment on /api/memories ----------------------------------


def test_list_memories_includes_freshness_and_overdue(seed, client):
    seed(
        "fresh1",
        column="memory",
        last_tended_at=datetime.now(UTC) - timedelta(hours=2),
    )
    seed(
        "stale1",
        column="memory",
        last_tended_at=datetime.now(UTC) - timedelta(days=15),
    )
    body = client.get("/api/memories").json()
    mems = {m["id"]: m for m in body["memories"]}
    assert mems["mem_fresh1"]["freshness"] == "fresh"
    assert mems["mem_stale1"]["freshness"] == "stale"
    assert mems["mem_fresh1"]["is_overdue"] is False


def test_get_memory_includes_freshness(seed, client):
    seed("m1", last_tended_at=datetime.now(UTC) - timedelta(days=2))
    body = client.get("/api/memories/m1").json()
    assert body["freshness"] == "fresh"
    assert "is_overdue" in body


def test_search_includes_freshness(seed, client):
    """Search results must carry the same enrichment as /api/memories.

    Regression: pre-Garden /api/search returned raw to_dashboard_dict()
    and missed vials_count / pending_closure_capture too.
    """
    seed("m1", column="closed", last_tended_at=datetime.now(UTC))
    body = client.get("/api/search", params={"q": "Memory"}).json()
    assert body["count"] >= 1
    mem = body["memories"][0]
    assert "freshness" in mem
    assert "is_overdue" in mem
    assert "vials_count" in mem
    assert "pending_closure_capture" in mem


# --- tending bumps last_tended_at -------------------------------------------


def _read_tended(client, memory_id: str) -> datetime | None:
    body = client.get(f"/api/memories/{memory_id}").json()
    raw = body.get("last_tended_at")
    if not raw:
        return None
    return datetime.fromisoformat(raw)


def test_patch_column_bumps_tended(seed, client):
    seed_time = datetime.now(UTC) - timedelta(days=10)
    seed("m1", column="memory", last_tended_at=seed_time)
    before = _read_tended(client, "m1")
    res = client.patch("/api/memories/m1/column", json={"column": "dive"})
    assert res.status_code == 200
    after = _read_tended(client, "m1")
    assert after is not None
    assert before is not None
    assert after > before
    # Endpoint also returns the enriched memory so frontend can refresh in place
    body = res.json()
    assert body["memory"]["freshness"] == "fresh"
    assert body["memory"]["column"] == "dive"


def test_patch_memory_edit_bumps_tended(seed, client):
    seed_time = datetime.now(UTC) - timedelta(days=10)
    seed("m1", last_tended_at=seed_time)
    res = client.patch("/api/memories/m1", json={"title": "Edited title"})
    assert res.status_code == 200
    after = _read_tended(client, "m1")
    assert after is not None
    assert after > seed_time
    assert res.json()["memory"]["title"] == "Edited title"
    assert res.json()["memory"]["freshness"] == "fresh"


def test_post_vial_captured_bumps_tended(seed, client):
    seed_time = datetime.now(UTC) - timedelta(days=20)
    seed("m1", column="closed", last_tended_at=seed_time)
    res = client.post("/api/memories/m1/vials", json={"captured_text": "ship"})
    assert res.status_code == 200
    after = _read_tended(client, "m1")
    assert after is not None and after > seed_time


def test_post_vial_skipped_bumps_tended(seed, client):
    """Skipping a Vial is still a deliberate user action → tending."""
    seed_time = datetime.now(UTC) - timedelta(days=20)
    seed("m1", column="closed", last_tended_at=seed_time)
    res = client.post(
        "/api/memories/m1/vials",
        json={"capture_kind": "skipped", "captured_text": ""},
    )
    assert res.status_code == 200
    after = _read_tended(client, "m1")
    assert after is not None and after > seed_time


def test_delete_vial_does_not_bump_tended(seed, client):
    """Vial deletion is administrative undo, not tending."""
    seed_time = datetime.now(UTC) - timedelta(days=30)
    seed("m1", column="closed", last_tended_at=seed_time)
    created = client.post("/api/memories/m1/vials", json={"captured_text": "x"}).json()
    # Vial post DID bump (covered by other test); reset the timestamp for
    # this isolated check.
    store = ChromaMemoryStore()
    store.update_meta("m1", {"last_tended_at": seed_time})
    before = _read_tended(client, "m1")
    res = client.delete(f"/api/vials/{created['vial']['id']}")
    assert res.status_code == 200
    after = _read_tended(client, "m1")
    assert after == before  # no change from delete


# --- store-level: backfill + bump_tended_at ---------------------------------


def test_reconstruct_backfills_tended_from_enriched_at(tmp_path, monkeypatch):
    """Pre-Garden memories (no last_tended_at in meta) should reconstruct
    with last_tended_at = enriched_at, so freshness has a sensible signal."""
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()
    seeded_enriched = datetime.now(UTC) - timedelta(days=5)
    m = Memory(
        id="legacy1",
        source="sample_file",
        source_task_id="legacy1",
        title="Legacy",
        enriched_at=seeded_enriched,
        last_tended_at=None,  # never tended → simulates pre-Garden row
    )
    store.upsert_memory(m)
    rebuilt = store.get_memory("legacy1")
    assert rebuilt is not None
    assert rebuilt.last_tended_at is not None
    # Backfilled from enriched_at (allowing microsecond-level ISO drift)
    assert abs((rebuilt.last_tended_at - seeded_enriched).total_seconds()) < 1


def test_bump_tended_at_updates_only_that_field(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()
    m = Memory(
        id="m1",
        source="sample_file",
        source_task_id="m1",
        title="Original Title",
        column="dive",
        notes_for_user="private note",
    )
    store.upsert_memory(m)
    when = datetime.now(UTC)
    assert store.bump_tended_at("m1", when) is True
    rebuilt = store.get_memory("m1")
    assert rebuilt is not None
    assert rebuilt.title == "Original Title"  # untouched
    assert rebuilt.column == "dive"  # untouched
    assert rebuilt.notes_for_user == "private note"  # untouched
    assert rebuilt.last_tended_at is not None
    assert abs((rebuilt.last_tended_at - when).total_seconds()) < 1


def test_bump_tended_at_missing_memory_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()
    assert store.bump_tended_at("doesnotexist") is False


def test_update_meta_atomic_multi_field(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()
    m = Memory(id="m1", source="sample_file", source_task_id="m1", title="t", column="memory")
    store.upsert_memory(m)
    when = datetime.now(UTC)
    assert store.update_meta("m1", {"column": "review", "last_tended_at": when}) is True
    rebuilt = store.get_memory("m1")
    assert rebuilt is not None
    assert rebuilt.column == "review"
    assert rebuilt.last_tended_at is not None


def test_upsert_preserving_user_fields_keeps_user_tend(tmp_path, monkeypatch):
    """The critical write-time merge: a stale read by sync must not
    clobber a user tend that landed AFTER sync read but BEFORE sync wrote."""
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()
    user_tend_time = datetime.now(UTC)
    seeded = Memory(
        id="m1",
        source="sample_file",
        source_task_id="m1",
        title="seeded",
        column="dive",
        notes_for_user="andy note",
        last_tended_at=user_tend_time,
    )
    store.upsert_memory(seeded)
    # Simulate sync holding a STALE in-memory copy that lacks the user tend
    stale_copy = Memory(
        id="m1",
        source="sample_file",
        source_task_id="m1",
        title="sync rewritten title",
        column="memory",  # sync had the old column
        notes_for_user="",  # sync had no private note
        last_tended_at=None,  # sync didn't know about user's tend
    )
    store.upsert_memory_preserving_user_fields(stale_copy)
    rebuilt = store.get_memory("m1")
    assert rebuilt is not None
    # Title CHANGES (sync rewrote it — that's fine, it's enrichment output)
    assert rebuilt.title == "sync rewritten title"
    # But user-owned fields are preserved from the latest persisted row:
    assert rebuilt.column == "dive"
    assert rebuilt.notes_for_user == "andy note"
    assert rebuilt.last_tended_at is not None
    assert abs((rebuilt.last_tended_at - user_tend_time).total_seconds()) < 1
