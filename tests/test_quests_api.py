"""Garden v2 TestClient tests: /api/quests + completion via tend + bonus wiring."""

from __future__ import annotations

import json
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
        completed_at: datetime | None = None,
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
            completed_at=completed_at,
        )
        store.upsert_memory(m)
        return m

    return _seed


# --- /api/quests ------------------------------------------------------------


def test_quests_endpoint_returns_shape_for_empty_board(client):
    res = client.get("/api/quests")
    assert res.status_code == 200
    body = res.json()
    assert "today" in body
    assert "clean_streak_d" in body
    assert "all_done" in body
    assert "quest_bonus" in body
    assert body["today"]["quests"] == []
    assert body["all_done"] is False
    assert body["quest_bonus"] == 0


def test_quests_endpoint_generates_ghost_quest(seed, client):
    seed("g1", last_tended_at=datetime.now(UTC) - timedelta(days=45))
    body = client.get("/api/quests").json()
    quests_list = body["today"]["quests"]
    assert len(quests_list) >= 1
    assert any(q["kind"] == "bury-ghost" for q in quests_list)


def test_quests_persisted_across_requests_same_day(seed, client):
    seed("g1", last_tended_at=datetime.now(UTC) - timedelta(days=45))
    a = client.get("/api/quests").json()
    b = client.get("/api/quests").json()
    # IDs are deterministic per day → both requests return the same quest IDs.
    assert [q["id"] for q in a["today"]["quests"]] == [
        q["id"] for q in b["today"]["quests"]
    ]


def test_quests_state_file_written(seed, client, tmp_path):
    seed("g1", last_tended_at=datetime.now(UTC) - timedelta(days=45))
    client.get("/api/quests")
    state_file = tmp_path / "garden-quests.json"
    assert state_file.exists()
    raw = json.loads(state_file.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["today"] is not None
    assert len(raw["today"]["quests"]) >= 1


# --- completion via tending action -----------------------------------------


def test_bury_ghost_completes_when_user_moves_to_closed(seed, client):
    seed("g1", last_tended_at=datetime.now(UTC) - timedelta(days=45))
    initial = client.get("/api/quests").json()
    ghost_quest = next(q for q in initial["today"]["quests"] if q["kind"] == "bury-ghost")
    assert ghost_quest["completed_at"] is None

    # User moves the ghost to closed → tend bump + completion check fires.
    res = client.patch("/api/memories/g1/column", json={"column": "closed"})
    assert res.status_code == 200

    after = client.get("/api/quests").json()
    ghost_after = next(q for q in after["today"]["quests"] if q["kind"] == "bury-ghost")
    assert ghost_after["completed_at"] is not None


def test_quest_bonus_appears_when_all_quests_done(seed, client):
    seed("g1", last_tended_at=datetime.now(UTC) - timedelta(days=45))
    initial = client.get("/api/quests").json()
    # A single ghost in the memory lane CAN spawn up to 3 quests (bury-ghost,
    # hit-95-health when score sits in 90-94, triage-inbox is now excluded
    # because the ghost already owns the target). Just assert non-empty +
    # all-pending up front.
    assert len(initial["today"]["quests"]) >= 1
    assert all(q["completed_at"] is None for q in initial["today"]["quests"])
    assert initial["quest_bonus"] == 0

    # Closing the ghost completes bury-ghost AND removes the -10 penalty,
    # which lifts intrinsic health back to 100 and completes hit-95-health.
    client.patch("/api/memories/g1/column", json={"column": "closed"})

    after = client.get("/api/quests").json()
    assert after["all_done"] is True
    assert after["quest_bonus"] == 5


def test_quest_bonus_applied_to_board_health(seed, client):
    seed("g1", last_tended_at=datetime.now(UTC) - timedelta(days=45))
    before = client.get("/api/board/health").json()
    client.patch("/api/memories/g1/column", json={"column": "closed"})
    after = client.get("/api/board/health").json()
    # Closing the ghost removes the -10 ghost penalty AND grants +5 quest bonus.
    assert after["score"] > before["score"]
    assert after["terms"]["quest_bonus"] == 5


def test_capture_yesterday_closure_completes_via_vial_post(seed, client):
    yesterday = datetime.now(UTC) - timedelta(days=1)
    seed(
        "c1", column="closed", completed_at=yesterday, last_tended_at=yesterday,
    )
    initial = client.get("/api/quests").json()
    yclose = next(
        (q for q in initial["today"]["quests"] if q["kind"] == "capture-yesterday-closures"),
        None,
    )
    assert yclose is not None
    assert yclose["completed_at"] is None

    res = client.post(
        "/api/memories/c1/vials",
        json={"captured_text": "Shipped Garden v2.", "capture_kind": "captured"},
    )
    assert res.status_code == 200

    after = client.get("/api/quests").json()
    yclose_after = next(
        q for q in after["today"]["quests"] if q["kind"] == "capture-yesterday-closures"
    )
    assert yclose_after["completed_at"] is not None


def test_skipped_vial_does_not_complete_capture_quest(seed, client):
    """Skipping a Vial bumps tended (administrative), but a skip is NOT a capture
    — so the capture-yesterday-closures quest must remain pending."""
    yesterday = datetime.now(UTC) - timedelta(days=1)
    seed(
        "c1", column="closed", completed_at=yesterday, last_tended_at=yesterday,
    )
    initial = client.get("/api/quests").json()
    yclose = next(
        (q for q in initial["today"]["quests"] if q["kind"] == "capture-yesterday-closures"),
        None,
    )
    assert yclose is not None

    res = client.post(
        "/api/memories/c1/vials",
        json={"captured_text": "", "capture_kind": "skipped"},
    )
    assert res.status_code == 200

    after = client.get("/api/quests").json()
    yclose_after = next(
        q for q in after["today"]["quests"] if q["kind"] == "capture-yesterday-closures"
    )
    assert yclose_after["completed_at"] is None


def test_triage_inbox_completes_when_card_moved_out(seed, client):
    seed("old", column="memory", last_tended_at=datetime.now(UTC) - timedelta(days=5))
    initial = client.get("/api/quests").json()
    triage = next(
        (q for q in initial["today"]["quests"] if q["kind"] == "triage-inbox"),
        None,
    )
    assert triage is not None
    assert triage["target_memory_ids"] == ["old"]

    client.patch("/api/memories/old/column", json={"column": "dive"})

    after = client.get("/api/quests").json()
    triage_after = next(q for q in after["today"]["quests"] if q["kind"] == "triage-inbox")
    assert triage_after["completed_at"] is not None


def test_tend_stale_requires_all_three_targets(seed, client):
    seed("s1", column="dive", last_tended_at=datetime.now(UTC) - timedelta(days=10))
    seed("s2", column="dive", last_tended_at=datetime.now(UTC) - timedelta(days=15))
    seed("s3", column="dive", last_tended_at=datetime.now(UTC) - timedelta(days=20))
    initial = client.get("/api/quests").json()
    stale = next(q for q in initial["today"]["quests"] if q["kind"] == "tend-stale")
    assert len(stale["target_memory_ids"]) == 3

    # Tend only 2 of 3.
    client.patch("/api/memories/s1/column", json={"column": "review"})
    client.patch("/api/memories/s2/column", json={"column": "review"})
    mid = client.get("/api/quests").json()
    stale_mid = next(q for q in mid["today"]["quests"] if q["kind"] == "tend-stale")
    assert stale_mid["completed_at"] is None

    # Tend the third.
    client.patch("/api/memories/s3/column", json={"column": "review"})
    end = client.get("/api/quests").json()
    stale_end = next(q for q in end["today"]["quests"] if q["kind"] == "tend-stale")
    assert stale_end["completed_at"] is not None


# --- clean_streak_d --------------------------------------------------------


def test_clean_streak_starts_at_one_on_first_call_with_clean_board(client):
    """First /api/quests call records yesterday's clean status into history.
    An empty board IS clean (no stale/ghost/overdue), so the streak starts at 1.
    """
    body = client.get("/api/quests").json()
    assert body["clean_streak_d"] == 1
    health = client.get("/api/board/health").json()
    assert health["terms"]["clean_streak_d"] == 1


def test_board_health_reads_clean_streak_from_state(client, tmp_path):
    # Pre-seed the quest state file with a 4-day streak.
    state_file = tmp_path / "garden-quests.json"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
    state_file.write_text(
        json.dumps({
            "version": 1,
            "today": {
                "date": today,
                "generated_at": datetime.now(UTC).isoformat(),
                "quests": [],
                "all_done_bonus_grants": 0,
            },
            "clean_streak_d": 4,
            "history": [
                {"date": yesterday, "clean": True},
            ],
        }),
        encoding="utf-8",
    )
    body = client.get("/api/board/health").json()
    assert body["terms"]["clean_streak_d"] == 4
    # Empty board → 100 + 4 streak bonus, but clamped at 100.
    assert body["score"] == 100
