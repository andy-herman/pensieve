"""Tests for the Vial schema + ChromaVialStore (no LLM, in-process)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pensieve.config import get_settings
from pensieve.store import ChromaMemoryStore, ChromaVialStore, Memory, Vial


@pytest.fixture()
def tmp_stores(tmp_path, monkeypatch):
    """Isolate Chroma to a tmp dir; yield both stores fresh per test."""
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield ChromaMemoryStore(), ChromaVialStore()
    get_settings.cache_clear()  # type: ignore[attr-defined]


def _mk_closed_memory(id_="m1", title="Shipped DORA RFI") -> Memory:
    return Memory(
        id=id_,
        source="sample_file",
        source_task_id=id_,
        list_name="CISO GRC",
        title=title,
        display_title=title,
        suggested_strand="dora-rfi",
        strand_kind="deep",
        why="Because.",
        impact="Things happen.",
        connect_goal_ids=["goal-1-dora-deep-dive", "goal-2-ai-safety"],
        connect_alignment_note="Direct DORA work.",
        column="closed",
        completed=True,
        completed_at=datetime.now(timezone.utc),
        source_last_modified=datetime.now(timezone.utc),
    )


# ----- Schema -----


def test_vial_id_is_auto_generated_unique():
    v1 = Vial(memory_id="m1")
    v2 = Vial(memory_id="m1")
    assert v1.id.startswith("vial_")
    assert v2.id.startswith("vial_")
    assert v1.id != v2.id


def test_snapshot_from_freezes_memory_context():
    m = _mk_closed_memory()
    v = Vial.snapshot_from(m, captured_text="Shifted policy from X to Y")
    assert v.memory_id == "m1"
    assert v.capture_kind == "captured"
    assert v.captured_text == "Shifted policy from X to Y"
    assert v.title_snapshot == "Shipped DORA RFI"
    assert v.display_title_snapshot == "Shipped DORA RFI"
    assert v.why_snapshot == "Because."
    assert v.impact_snapshot == "Things happen."
    assert v.connect_goal_ids_snapshot == ["goal-1-dora-deep-dive", "goal-2-ai-safety"]
    assert v.suggested_strand_snapshot == "dora-rfi"
    assert v.source_snapshot == "sample_file"
    assert v.source_task_id_snapshot == "m1"
    assert v.list_name_snapshot == "CISO GRC"
    assert v.column_snapshot == "closed"
    assert v.completed_at_snapshot is not None


def test_snapshot_does_not_follow_memory_edits():
    """The Vial's snapshot must NOT change when the source Memory is later
    edited — that's the entire point of snapshotting at closure-time."""
    m = _mk_closed_memory()
    v = Vial.snapshot_from(m, captured_text="captured at v1")
    original_title_snapshot = v.title_snapshot
    m.title = "Title was edited later"
    m.why = "Edited why"
    assert v.title_snapshot == original_title_snapshot
    assert v.why_snapshot == "Because."


def test_skipped_vial_allows_empty_text():
    v = Vial(memory_id="m1", capture_kind="skipped", captured_text="")
    assert v.capture_kind == "skipped"
    assert v.captured_text == ""


# ----- Store -----


def test_upsert_and_get_vial(tmp_stores):
    _, vials = tmp_stores
    v = Vial(memory_id="m1", captured_text="Closed because reasons", title_snapshot="My task")
    vials.upsert_vial(v)
    got = vials.get_vial(v.id)
    assert got is not None
    assert got.memory_id == "m1"
    assert got.captured_text == "Closed because reasons"
    assert got.title_snapshot == "My task"


def test_round_trip_preserves_list_snapshot(tmp_stores):
    """connect_goal_ids_snapshot is stored CSV-flattened in Chroma; ensure
    the reconstruct path rebuilds the list correctly."""
    _, vials = tmp_stores
    v = Vial(
        memory_id="m1",
        captured_text="ok",
        connect_goal_ids_snapshot=["g1", "g2", "g3"],
    )
    vials.upsert_vial(v)
    got = vials.get_vial(v.id)
    assert got is not None
    assert got.connect_goal_ids_snapshot == ["g1", "g2", "g3"]


def test_round_trip_preserves_none_datetimes(tmp_stores):
    """Optional datetime fields must survive the empty-string round-trip."""
    _, vials = tmp_stores
    v = Vial(memory_id="m1", captured_text="ok")
    assert v.completed_at_snapshot is None
    assert v.due_date_snapshot is None
    vials.upsert_vial(v)
    got = vials.get_vial(v.id)
    assert got is not None
    assert got.completed_at_snapshot is None
    assert got.due_date_snapshot is None


def test_list_vials_for_memory_scopes_to_one_memory(tmp_stores):
    _, vials = tmp_stores
    v1 = Vial(memory_id="m1", captured_text="first")
    v2 = Vial(memory_id="m1", captured_text="second")
    v3 = Vial(memory_id="m2", captured_text="other memory")
    vials.upsert_vial(v1)
    vials.upsert_vial(v2)
    vials.upsert_vial(v3)
    got = vials.list_vials_for_memory("m1")
    assert len(got) == 2
    assert {v.captured_text for v in got} == {"first", "second"}


def test_captured_count_excludes_skipped(tmp_stores):
    """captured_count_by_memory must not count Skip markers — only real
    captured Vials count toward the badge."""
    _, vials = tmp_stores
    vials.upsert_vial(Vial(memory_id="m1", captured_text="real one"))
    vials.upsert_vial(Vial(memory_id="m1", capture_kind="skipped", captured_text=""))
    vials.upsert_vial(Vial(memory_id="m2", captured_text="another real one"))
    counts = vials.captured_count_by_memory()
    assert counts == {"m1": 1, "m2": 1}


def test_has_any_vial_includes_skipped(tmp_stores):
    """has_any_vial_by_memory must include skips — Skip clears the chevron."""
    _, vials = tmp_stores
    vials.upsert_vial(Vial(memory_id="m1", capture_kind="skipped", captured_text=""))
    vials.upsert_vial(Vial(memory_id="m2", captured_text="real"))
    seen = vials.has_any_vial_by_memory()
    assert seen == {"m1", "m2"}


def test_delete_vial(tmp_stores):
    _, vials = tmp_stores
    v = Vial(memory_id="m1", captured_text="ok")
    vials.upsert_vial(v)
    assert vials.get_vial(v.id) is not None
    vials.delete_vial(v.id)
    assert vials.get_vial(v.id) is None


def test_vials_survive_memory_deletion(tmp_stores):
    """Critical contract: Vials are durable evidence and must outlive their
    parent Memory. delete_memory must NOT cascade to Vials. If this test
    fails, promo evidence is at risk."""
    memories, vials = tmp_stores
    m = _mk_closed_memory()
    memories.upsert_memory(m)
    vials.upsert_vial(Vial.snapshot_from(m, captured_text="Shipped this!"))
    # Simulate orphan sweep removing the upstream Memory
    memories.delete_memory(m.id)
    assert memories.get_memory(m.id) is None
    # Vial must still be there with its snapshot context intact
    survivors = vials.list_vials_for_memory(m.id)
    assert len(survivors) == 1
    assert survivors[0].title_snapshot == "Shipped DORA RFI"
    assert survivors[0].captured_text == "Shipped this!"


def test_list_vials_sorted_oldest_first(tmp_stores):
    """Stable chronological order in API responses."""
    _, vials = tmp_stores
    early = Vial(memory_id="m1", captured_text="early",
                 captured_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    late = Vial(memory_id="m1", captured_text="late",
                captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    vials.upsert_vial(late)
    vials.upsert_vial(early)
    got = vials.list_vials_for_memory("m1")
    assert [v.captured_text for v in got] == ["early", "late"]
