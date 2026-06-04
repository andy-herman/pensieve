"""CRITICAL: end-to-end test that auto-sync does NOT bump last_tended_at.

If this regresses, the entire freshness signal evaporates: every 120-second
auto-sync would mark every card as freshly tended, and stale/ghost states
would be unreachable. The test runs ``run_sync`` against a SampleFileSource
(no Azure needed for the column-only auto-close path) and uses a stubbed
``enrich_task`` for the re-enrichment path.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from pensieve.config import get_settings
from pensieve.enrichment.enricher import EnrichmentResult
from pensieve.sources.sample_file import SampleFileSource
from pensieve.store import ChromaMemoryStore, Memory
from pensieve.sync import run_sync


UTC = timezone.utc


def _write_sample(path, tasks: list[dict]) -> None:
    payload = {
        "strand_catalog": [
            {"id": "x", "label": "x", "kind": "tactical", "context": ""},
        ],
        "recent_context": {"user_recent_strands": [], "recent_titles_in_same_list": []},
        "tasks": tasks,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_ENABLED", "false")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_sync_skip_unchanged_does_not_bump_tended(tmp_path):
    """When sync finds nothing to do, it must not touch any timestamps."""
    samples = tmp_path / "samples.json"
    _write_sample(samples, [])

    # Pre-seed a memory the user already tended.
    store = ChromaMemoryStore()
    user_tend_time = datetime.now(UTC) - timedelta(days=3)
    seeded = Memory(
        id="m1",
        source="sample_file",
        source_task_id="m1",
        title="already tended",
        column="dive",
        last_tended_at=user_tend_time,
    )
    store.upsert_memory(seeded)

    # Sync sees the source as empty + this memory in chroma; but since this
    # memory's id is not in live_ids and the covered_lists includes its
    # list_name (""), the orphan sweep would delete it. To avoid that, give
    # the source a covered_lists that EXCLUDES "" by listing a different
    # list_name. Easiest: include the memory's task in the source so it's
    # in live_ids, but mark it unchanged.
    _write_sample(samples, [{
        "id": "m1",
        "title": "already tended",
        "list_name": "",
    }])
    src = SampleFileSource(samples)
    run_sync(src)

    rebuilt = store.get_memory("m1")
    assert rebuilt is not None
    assert rebuilt.last_tended_at is not None
    # Allow microsecond-level ISO round-trip drift; must be unchanged
    assert abs((rebuilt.last_tended_at - user_tend_time).total_seconds()) < 1


def test_sync_auto_close_path_does_not_bump_tended(tmp_path):
    """Source marked task complete → sync auto-closes the kanban card.
    last_tended_at must SURVIVE the column flip."""
    samples = tmp_path / "samples.json"
    store = ChromaMemoryStore()

    # Seed an open memory with a known last_tended_at.
    user_tend_time = datetime.now(UTC) - timedelta(days=10)
    seeded = Memory(
        id="m1",
        source="sample_file",
        source_task_id="m1",
        title="will be auto-closed",
        column="memory",
        last_tended_at=user_tend_time,
    )
    store.upsert_memory(seeded)

    # Now the source says it's complete — sync should auto-close via the
    # column-only path (no LLM call).
    _write_sample(samples, [{
        "id": "m1",
        "title": "will be auto-closed",
        "list_name": "",
        "completed": True,
    }])
    src = SampleFileSource(samples)
    run_sync(src)

    rebuilt = store.get_memory("m1")
    assert rebuilt is not None
    assert rebuilt.column == "closed"  # auto-closed
    assert rebuilt.completed is True
    # Tended timestamp must survive the column flip:
    assert rebuilt.last_tended_at is not None
    assert abs((rebuilt.last_tended_at - user_tend_time).total_seconds()) < 1


def test_sync_reenrich_preserves_user_tend(tmp_path, monkeypatch):
    """Source title changes → sync re-enriches. The user-owned fields
    (column, notes_for_user, last_tended_at) must all survive the
    re-enrichment overlay write."""
    samples = tmp_path / "samples.json"
    store = ChromaMemoryStore()
    user_tend_time = datetime.now(UTC) - timedelta(days=4)
    seeded = Memory(
        id="m1",
        source="sample_file",
        source_task_id="m1",
        title="OLD TITLE",
        column="dive",
        notes_for_user="andy private note",
        last_tended_at=user_tend_time,
    )
    store.upsert_memory(seeded)

    # New source state with the title changed → triggers "title-changed" re-enrich.
    _write_sample(samples, [{
        "id": "m1",
        "title": "NEW TITLE (edited at source)",
        "list_name": "",
    }])

    # Stub enrich_task so we don't hit Azure.
    def _fake_enrich(task, *, strand_catalog, recent_context, client, connect_goals):
        return EnrichmentResult(
            suggested_strand="x",
            strand_kind="tactical",
            needs_human_strand_review=False,
            why="new why",
            impact="new impact",
            confidence_strand=0.9,
            confidence_impact=0.9,
            connect_goal_ids=[],
            connect_alignment_confidence=0.0,
            connect_alignment_note="",
            notes_for_user="",
            display_title="",
            tokens_used=0,
        )

    monkeypatch.setattr("pensieve.sync.enrich_task", _fake_enrich)
    # Don't actually construct an Azure client either — patch it to None.
    monkeypatch.setattr(
        "pensieve.sync.AzureOpenAIChatClient",
        lambda settings: None,
    )

    src = SampleFileSource(samples)
    run_sync(src)

    rebuilt = store.get_memory("m1")
    assert rebuilt is not None
    # Re-enrichment ran: title + why updated.
    assert rebuilt.title == "NEW TITLE (edited at source)"
    assert rebuilt.why == "new why"
    # User-owned fields ALL preserved:
    assert rebuilt.column == "dive"
    assert rebuilt.notes_for_user == "andy private note"
    assert rebuilt.last_tended_at is not None
    assert abs((rebuilt.last_tended_at - user_tend_time).total_seconds()) < 1
