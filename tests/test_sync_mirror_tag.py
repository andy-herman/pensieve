"""Tests for Phase 2 mirror-tag: cross-PC kanban column sync via Categories.

Covers both the initial-build path (`_build_memory`) and the re-enrich
overlay (`overlay_regeneration`) with the source-wins-on-newer policy
Andy confirmed on 2026-06-02.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pensieve.enrichment.enricher import EnrichmentResult
from pensieve.sources.base import RawTask
from pensieve.store.schema import Memory
from pensieve.sync import _build_memory, _column_from_task, overlay_regeneration

PREFIX = "pensieve/col:"


def _result() -> EnrichmentResult:
    return EnrichmentResult(
        suggested_strand="ops-chores",
        strand_kind="tactical",
        needs_human_strand_review=False,
        why="why",
        impact="impact",
        confidence_strand=0.8,
        confidence_impact=0.7,
        connect_goal_ids=[],
        connect_alignment_confidence=0.6,
        connect_alignment_note="note",
        notes_for_user="",
        tokens_used=100,
    )


def _raw(*, categories=None, completed=False, modified=None) -> RawTask:
    return RawTask(
        id="task-9",
        title="ship the thing",
        notes="",
        list_name="Tasks",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        last_modification_time=modified or datetime(2026, 5, 2, tzinfo=timezone.utc),
        completed=completed,
        categories=categories or [],
        source="outlook_com",
    )


# ---------- _column_from_task pure helper ----------


def test_column_from_task_reads_known_column():
    task = _raw(categories=["Work", "pensieve/col:dive"])
    assert _column_from_task(task, PREFIX) == "dive"


def test_column_from_task_ignores_unknown_column_value():
    task = _raw(categories=["pensieve/col:bogus"])
    assert _column_from_task(task, PREFIX) is None


def test_column_from_task_returns_none_without_tag():
    task = _raw(categories=["Work", "Personal"])
    assert _column_from_task(task, PREFIX) is None


def test_column_from_task_accepts_all_valid_columns():
    for col in ("memory", "dive", "review", "closed"):
        task = _raw(categories=[f"pensieve/col:{col}"])
        assert _column_from_task(task, PREFIX) == col


# ---------- _build_memory honors the mirror tag ----------


def test_build_memory_first_boot_picks_up_mirrored_column():
    """A fresh sync on a new PC should land cards directly in their column."""
    task = _raw(categories=["Work", "pensieve/col:dive"])
    mem = _build_memory(task, _result())
    assert mem.column == "dive"


def test_build_memory_falls_back_to_completed_then_memory():
    completed = _raw(completed=True)
    assert _build_memory(completed, _result()).column == "closed"
    open_task = _raw()
    assert _build_memory(open_task, _result()).column == "memory"


def test_build_memory_mirror_tag_beats_completed_default():
    """Explicit mirror tag wins even if the task is marked complete upstream."""
    task = _raw(categories=["pensieve/col:review"], completed=True)
    assert _build_memory(task, _result()).column == "review"


# ---------- overlay_regeneration: source-wins-on-newer ----------


def _existing(column: str = "memory", enriched_at: datetime | None = None) -> Memory:
    return Memory(
        id="task-9",
        source="outlook_com",
        source_task_id="task-9",
        list_name="Tasks",
        title="ship the thing",
        original_notes="",
        suggested_strand="ops-chores",
        strand_kind="tactical",
        needs_human_strand_review=False,
        why="why",
        impact="impact",
        confidence_strand=0.8,
        confidence_impact=0.7,
        connect_goal_ids=[],
        connect_alignment_confidence=0.6,
        connect_alignment_note="note",
        notes_for_user="ANDY PRIVATE",
        column=column,
        source_created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        source_last_modified=datetime(2026, 5, 2, tzinfo=timezone.utc),
        completed=False,
        categories=[],
        tokens_used=100,
        enriched_at=enriched_at or datetime(2026, 5, 3, tzinfo=timezone.utc),
    )


def test_overlay_source_wins_when_tag_newer_than_local():
    existing = _existing(column="memory", enriched_at=datetime(2026, 5, 3, tzinfo=timezone.utc))
    # Source modified AFTER we last enriched, and its tag says "dive".
    task = _raw(
        categories=["pensieve/col:dive"],
        modified=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    merged = overlay_regeneration(existing, task, _result())
    assert merged.column == "dive"
    # private note still preserved
    assert merged.notes_for_user == "ANDY PRIVATE"


def test_overlay_local_wins_when_local_newer_than_source():
    existing = _existing(column="dive", enriched_at=datetime(2026, 5, 20, tzinfo=timezone.utc))
    # Source last modified BEFORE our last enrich (we won the race locally).
    task = _raw(
        categories=["pensieve/col:memory"],
        modified=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    merged = overlay_regeneration(existing, task, _result())
    assert merged.column == "dive"


def test_overlay_completion_still_promotes_to_closed_even_with_mirror_tag():
    """Source-completed signal trumps the mirror tag (terminal state wins)."""
    existing = _existing(column="dive", enriched_at=datetime(2026, 5, 3, tzinfo=timezone.utc))
    task = _raw(
        categories=["pensieve/col:review"],
        completed=True,
        modified=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    merged = overlay_regeneration(existing, task, _result())
    assert merged.column == "closed"


def test_overlay_no_mirror_tag_preserves_user_column():
    """Backwards compatibility: tasks without the tag behave exactly as before."""
    existing = _existing(column="review", enriched_at=datetime(2026, 5, 3, tzinfo=timezone.utc))
    task = _raw(modified=datetime(2026, 5, 10, tzinfo=timezone.utc))
    merged = overlay_regeneration(existing, task, _result())
    assert merged.column == "review"


def test_overlay_skips_override_when_tag_matches_local():
    existing = _existing(column="dive", enriched_at=datetime(2026, 5, 3, tzinfo=timezone.utc))
    task = _raw(
        categories=["pensieve/col:dive"],
        modified=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    merged = overlay_regeneration(existing, task, _result())
    assert merged.column == "dive"
