"""API fixes: due-date round trip, PDF import off the event loop, graph embeddings,
Garden state file locking, lean startup."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from pensieve.api.server import create_app
from pensieve.config import get_settings
from pensieve.store import ChromaMemoryStore, Memory


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS", "0")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()  # type: ignore[attr-defined]


def _seed(mid: str, title: str, **kw) -> Memory:
    m = Memory(
        id=mid,
        source="sample_file",
        source_task_id=mid,
        title=title,
        why="why",
        impact="impact",
        enriched_at=datetime.now(timezone.utc) - timedelta(days=1),
        **kw,
    )
    ChromaMemoryStore().upsert_memory(m)
    return m


def _local_date(iso: str) -> str:
    """The calendar date the dashboard shows for an ISO timestamp (local zone)."""
    return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d")


def test_date_only_due_date_round_trips_through_edit_modal(client):
    _seed("m1", "Due date card")
    body = client.patch("/api/memories/m1", json={"due_date": "2026-03-20"}).json()
    due = body["memory"]["due_date"]
    assert _local_date(due) == "2026-03-20"
    # Saving the modal again sends the date it displayed; it must not drift.
    for _ in range(3):
        body = client.patch("/api/memories/m1", json={"due_date": _local_date(due)}).json()
        due = body["memory"]["due_date"]
    assert _local_date(due) == "2026-03-20"


def test_full_iso_due_date_keeps_its_offset(client):
    _seed("m1", "Due date card")
    body = client.patch("/api/memories/m1", json={"due_date": "2026-03-20T15:30:00+02:00"}).json()
    assert datetime.fromisoformat(body["memory"]["due_date"]) == datetime(
        2026, 3, 20, 13, 30, tzinfo=timezone.utc
    )
    body = client.patch("/api/memories/m1", json={"due_date": "2026-03-20T15:30:00"}).json()
    assert datetime.fromisoformat(body["memory"]["due_date"]) == datetime(
        2026, 3, 20, 15, 30, tzinfo=timezone.utc
    )


def test_invalid_due_date_is_400(client):
    _seed("m1", "Due date card")
    assert client.patch("/api/memories/m1", json={"due_date": "not-a-date"}).status_code == 400


def test_goals_pdf_import_runs_off_the_event_loop(client, monkeypatch):
    from pensieve.enrichment import goals_importer

    seen: dict[str, bool] = {}

    def fake_import(pdf_bytes: bytes, source_label: str = "") -> dict:
        try:
            asyncio.get_running_loop()
            seen["on_event_loop"] = True
        except RuntimeError:
            seen["on_event_loop"] = False
        return {"_meta": {"source": source_label}, "goals": []}

    monkeypatch.setattr(goals_importer, "import_pdf_to_goals", fake_import)
    res = client.post(
        "/api/goals/import",
        files={"file": ("goals.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert res.status_code == 200
    assert res.json()["proposal"]["_meta"]["source"] == "Imported from goals.pdf"
    assert seen == {"on_event_loop": False}


def test_graph_links_similar_tasks(client):
    _seed("a", "Quarterly vendor risk assessment review")
    _seed("b", "Vendor risk assessment for the quarter")
    body = client.get("/api/graph", params={"threshold": 0.0}).json()
    assert body["ok"] is True
    semantic = [e for e in body["graph"]["edges"] if e["kind"] == "semantic"]
    assert semantic and {semantic[0]["source"], semantic[0]["target"]} == {"a", "b"}
    assert 0.0 < semantic[0]["weight"] <= 1.0


def test_server_import_does_not_load_azure_identity():
    """azure.identity costs ~0.5 s at startup and is only needed for keyless auth."""
    code = (
        "import sys, pensieve.cli, pensieve.api.server; "
        "print('azure.identity' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True
    )
    assert out.stdout.strip().splitlines()[-1] == "False"


def test_parallel_garden_requests_serialize_state_files(client, monkeypatch):
    """The dashboard fetches board health, quests and achievements in parallel.

    Their quest / achievement JSON reads and writes must never overlap: on
    Windows a replace fails while another thread has the file open, and a
    failed read looks like "no state", which would wipe the streak history.
    """
    from pensieve import achievement_state, quest_state

    state_path = get_settings().garden_quests_path
    old_days = ["2026-01-01", "2026-01-02", "2026-01-03"]
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "today": {"date": "2026-01-03", "generated_at": "2026-01-03T08:00:00+00:00", "quests": []},
                "clean_streak_d": 3,
                "history": [{"date": d, "clean": True} for d in old_days],
            }
        ),
        encoding="utf-8",
    )
    _seed("m1", "Card")

    active = 0
    peak = 0
    guard = threading.Lock()

    def tracked(fn):
        def wrapper(*args, **kwargs):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.02)
                return fn(*args, **kwargs)
            finally:
                with guard:
                    active -= 1

        return wrapper

    for mod in (quest_state, achievement_state):
        monkeypatch.setattr(mod, "load_state", tracked(mod.load_state))
        monkeypatch.setattr(mod, "save_state", tracked(mod.save_state))

    codes: list[int] = []

    def hit(path: str) -> None:
        codes.append(client.get(path).status_code)

    paths = ["/api/board/health", "/api/quests", "/api/achievements"] * 3
    threads = [threading.Thread(target=hit, args=(p,)) for p in paths]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert codes == [200] * len(paths)
    assert peak == 1
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert [h["date"] for h in saved["history"]][: len(old_days)] == old_days
    assert saved["today"]["date"] == datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_patch_marks_only_fields_that_changed_as_hand_edited(client):
    _seed("ue1", "Plan the quarter")
    body = {"display_title": "Plan the quarter", "why": "why", "impact": "My impact", "column": "dive"}
    r = client.patch("/api/memories/ue1", json=body)
    assert r.status_code == 200
    assert ChromaMemoryStore().get_memory("ue1").user_edited == ["impact"]
