"""TestClient tests for the Vial closure-capture API endpoints.

These are the first TestClient tests in the codebase; they double as
contract tests for the existing /api/memories route (which now exposes
vials_count + pending_closure_capture).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from pensieve.api.server import create_app
from pensieve.config import get_settings
from pensieve.store import ChromaMemoryStore, Memory


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
def seed_memory(tmp_path, monkeypatch):
    """Drop a single closed Memory into the store so the API has something
    to attach a Vial to. Must be defined before the client fixture is
    consumed in the test (i.e. listed first in the test signature)."""
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    store = ChromaMemoryStore()

    def _seed(memory_id: str = "m1", column: str = "closed") -> Memory:
        m = Memory(
            id=memory_id,
            source="sample_file",
            source_task_id=memory_id,
            list_name="CISO GRC",
            title="Shipped DORA RFI",
            display_title="Shipped DORA RFI",
            suggested_strand="dora-rfi",
            strand_kind="deep",
            why="Because.",
            impact="It mattered.",
            connect_goal_ids=["goal-1-dora-deep-dive"],
            connect_alignment_note="Direct DORA work.",
            column=column,
            completed=(column == "closed"),
            completed_at=datetime.now(timezone.utc) if column == "closed" else None,
        )
        store.upsert_memory(m)
        return m

    return _seed


# ----- list/get enrichment with vials_count + pending_closure_capture -----


def test_list_memories_marks_closed_memory_as_pending(seed_memory, client):
    seed_memory("m1", column="closed")
    res = client.get("/api/memories")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    mem = body["memories"][0]
    assert mem["column"] == "closed"
    assert mem["vials_count"] == 0
    assert mem["pending_closure_capture"] is True


def test_list_memories_non_closed_never_pending(seed_memory, client):
    seed_memory("m1", column="memory")
    body = client.get("/api/memories").json()
    mem = body["memories"][0]
    assert mem["column"] == "memory"
    assert mem["pending_closure_capture"] is False
    assert mem["vials_count"] == 0


def test_get_single_memory_enriched(seed_memory, client):
    seed_memory("m1", column="closed")
    res = client.get("/api/memories/m1")
    assert res.status_code == 200
    body = res.json()
    assert body["vials_count"] == 0
    assert body["pending_closure_capture"] is True


# ----- POST /api/memories/{id}/vials -----


def test_post_vial_captures_text_and_snapshot(seed_memory, client):
    seed_memory("m1", column="closed")
    res = client.post(
        "/api/memories/m1/vials",
        json={"captured_text": "Shifted policy from X to Y"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    v = body["vial"]
    assert v["memory_id"] == "m1"
    assert v["capture_kind"] == "captured"
    assert v["captured_text"] == "Shifted policy from X to Y"
    assert v["title_snapshot"] == "Shipped DORA RFI"
    assert v["suggested_strand_snapshot"] == "dora-rfi"
    assert v["list_name_snapshot"] == "CISO GRC"
    assert v["connect_goal_ids_snapshot"] == ["goal-1-dora-deep-dive"]
    assert v["id"].startswith("vial_")


def test_post_vial_409_when_memory_not_closed(seed_memory, client):
    seed_memory("m1", column="memory")
    res = client.post(
        "/api/memories/m1/vials",
        json={"captured_text": "should not work"},
    )
    assert res.status_code == 409
    assert "closed" in res.json()["detail"]


def test_post_vial_404_when_memory_missing(client):
    res = client.post(
        "/api/memories/nonexistent/vials",
        json={"captured_text": "nope"},
    )
    assert res.status_code == 404


def test_post_vial_rejects_empty_captured_text(seed_memory, client):
    seed_memory("m1", column="closed")
    res = client.post(
        "/api/memories/m1/vials",
        json={"captured_text": "   "},
    )
    assert res.status_code == 400
    assert "captured_text" in res.json()["detail"]


def test_post_vial_allows_skipped_with_no_text(seed_memory, client):
    seed_memory("m1", column="closed")
    res = client.post(
        "/api/memories/m1/vials",
        json={"capture_kind": "skipped", "captured_text": ""},
    )
    assert res.status_code == 200, res.text
    assert res.json()["vial"]["capture_kind"] == "skipped"


def test_post_vial_rejects_bad_capture_kind(seed_memory, client):
    seed_memory("m1", column="closed")
    res = client.post(
        "/api/memories/m1/vials",
        json={"capture_kind": "weird", "captured_text": "x"},
    )
    assert res.status_code == 400


def test_post_vial_rejects_text_over_2000_chars(seed_memory, client):
    seed_memory("m1", column="closed")
    res = client.post(
        "/api/memories/m1/vials",
        json={"captured_text": "x" * 2001},
    )
    assert res.status_code == 400


# ----- pending/badge interaction post-Save and post-Skip -----


def test_captured_vial_clears_pending_and_increments_badge(seed_memory, client):
    seed_memory("m1", column="closed")
    client.post("/api/memories/m1/vials", json={"captured_text": "yes"})
    mem = client.get("/api/memories/m1").json()
    assert mem["pending_closure_capture"] is False
    assert mem["vials_count"] == 1


def test_skipped_vial_clears_pending_without_incrementing_badge(seed_memory, client):
    """Skip is for dismissing the chevron; it must not pretend a closure
    was actually captured (badge stays at 0)."""
    seed_memory("m1", column="closed")
    client.post(
        "/api/memories/m1/vials",
        json={"capture_kind": "skipped", "captured_text": ""},
    )
    mem = client.get("/api/memories/m1").json()
    assert mem["pending_closure_capture"] is False
    assert mem["vials_count"] == 0


# ----- GET /api/memories/{id}/vials + /api/vials -----


def test_get_memory_vials_lists_oldest_first(seed_memory, client):
    seed_memory("m1", column="closed")
    client.post("/api/memories/m1/vials", json={"captured_text": "first"})
    client.post("/api/memories/m1/vials", json={"captured_text": "second"})
    res = client.get("/api/memories/m1/vials")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 2
    assert [v["captured_text"] for v in body["vials"]] == ["first", "second"]


def test_get_memory_vials_404_when_memory_missing(client):
    res = client.get("/api/memories/nonexistent/vials")
    assert res.status_code == 404


def test_list_all_vials_returns_all_memories(seed_memory, client):
    seed_memory("m1", column="closed")
    seed_memory("m2", column="closed")
    client.post("/api/memories/m1/vials", json={"captured_text": "a"})
    client.post("/api/memories/m2/vials", json={"captured_text": "b"})
    body = client.get("/api/vials").json()
    assert body["count"] == 2


# ----- DELETE /api/vials/{id} -----


def test_delete_vial_removes_it(seed_memory, client):
    seed_memory("m1", column="closed")
    created = client.post("/api/memories/m1/vials", json={"captured_text": "z"}).json()
    vid = created["vial"]["id"]
    res = client.delete(f"/api/vials/{vid}")
    assert res.status_code == 200
    body = client.get("/api/memories/m1/vials").json()
    assert body["count"] == 0


def test_delete_missing_vial_404(client):
    res = client.delete("/api/vials/vial_doesnotexist")
    assert res.status_code == 404
