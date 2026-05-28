"""Tests for the sync overlay/preserve semantics on re-enrichment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pensieve.enrichment.enricher import EnrichmentResult
from pensieve.sources.base import RawTask
from pensieve.store.schema import Memory
from pensieve.sync import overlay_regeneration


def _existing_memory() -> Memory:
    return Memory(
        id="task-123",
        source="outlook_com",
        source_task_id="task-123",
        list_name="Tasks",
        title="OLD TITLE",
        original_notes="old notes",
        suggested_strand="ops-chores",
        strand_kind="tactical",
        needs_human_strand_review=False,
        why="old why",
        impact="old impact",
        confidence_strand=0.6,
        confidence_impact=0.5,
        connect_goal_ids=["goal-old"],
        connect_alignment_confidence=0.7,
        connect_alignment_note="old alignment",
        notes_for_user="ANDY'S PRIVATE NOTE",
        column="dive",  # user dragged it
        source_created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        source_last_modified=datetime(2025, 1, 1, tzinfo=timezone.utc),
        completed=False,
        categories=["foo"],
        tokens_used=1000,
    )


def _refreshed_task(*, completed: bool = False) -> RawTask:
    return RawTask(
        id="task-123",
        title="NEW TITLE (edited in To-Do)",
        notes="new notes",
        list_name="Tasks",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        last_modification_time=datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=10),
        completed=completed,
        categories=["bar"],
        source="outlook_com",
    )


def _fresh_result() -> EnrichmentResult:
    return EnrichmentResult(
        suggested_strand="ai-program-launch",
        strand_kind="deep",
        needs_human_strand_review=True,
        why="new why from LLM",
        impact="new impact from LLM",
        confidence_strand=0.91,
        confidence_impact=0.83,
        connect_goal_ids=["goal-4-ai-transformation"],
        connect_alignment_confidence=0.95,
        connect_alignment_note="new alignment from LLM",
        notes_for_user="enrichment system note (ignored on overlay)",
        tokens_used=2000,
    )


def test_overlay_preserves_user_column_and_private_note():
    existing = _existing_memory()
    merged = overlay_regeneration(existing, _refreshed_task(), _fresh_result())
    # USER-ONLY FIELDS — must survive a re-enrich
    assert merged.column == "dive", "user-dragged column was clobbered on re-enrich"
    assert merged.notes_for_user == "ANDY'S PRIVATE NOTE", "private note was clobbered on re-enrich"


def test_overlay_refreshes_source_and_enrichment_fields():
    existing = _existing_memory()
    merged = overlay_regeneration(existing, _refreshed_task(), _fresh_result())
    # Source-side fields refresh
    assert merged.title == "NEW TITLE (edited in To-Do)"
    assert merged.original_notes == "new notes"
    assert merged.categories == ["bar"]
    # Enrichment fields regenerate
    assert merged.suggested_strand == "ai-program-launch"
    assert merged.strand_kind == "deep"
    assert merged.why == "new why from LLM"
    assert merged.impact == "new impact from LLM"
    assert merged.confidence_strand == 0.91
    assert merged.connect_goal_ids == ["goal-4-ai-transformation"]
    assert merged.connect_alignment_note == "new alignment from LLM"
    assert merged.needs_human_strand_review is True


def test_overlay_accumulates_tokens_and_bumps_enriched_at():
    existing = _existing_memory()
    old_enriched_at = existing.enriched_at
    merged = overlay_regeneration(existing, _refreshed_task(), _fresh_result())
    assert merged.tokens_used == 3000  # 1000 + 2000
    assert merged.enriched_at >= old_enriched_at


def test_overlay_auto_promotes_completed_task_to_closed_column():
    """When the source marks the task complete, the kanban auto-moves it to Closed."""
    existing = _existing_memory()  # currently in "dive"
    merged = overlay_regeneration(existing, _refreshed_task(completed=True), _fresh_result())
    assert merged.column == "closed", "completed task should auto-promote to Closed"
    assert merged.completed is True


def test_overlay_does_not_overwrite_closed_when_already_closed():
    """If the memory is already in Closed, leave it there (idempotent)."""
    existing = _existing_memory()
    existing.column = "closed"
    merged = overlay_regeneration(existing, _refreshed_task(completed=True), _fresh_result())
    assert merged.column == "closed"


def test_overlay_does_not_force_closed_when_task_is_not_completed():
    """Re-enriching an open task must not move it to Closed."""
    existing = _existing_memory()  # column="dive", not completed
    merged = overlay_regeneration(existing, _refreshed_task(completed=False), _fresh_result())
    assert merged.column == "dive", "open task should preserve user-placed column"
    assert merged.completed is False
