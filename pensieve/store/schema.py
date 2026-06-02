"""Pydantic models for the persistent layer (Memory, Vial)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Memory(BaseModel):
    """A single enriched To-Do task. The id is the source task id (e.g. Outlook EntryID)."""

    id: str
    source: str
    source_task_id: str
    list_name: str = ""
    title: str
    original_notes: str = ""

    # Enrichment outputs
    suggested_strand: Optional[str] = None
    strand_kind: Optional[str] = None
    needs_human_strand_review: bool = False
    why: str = ""
    impact: str = ""
    confidence_strand: float = 0.0
    confidence_impact: float = 0.0
    connect_goal_ids: list[str] = Field(default_factory=list)
    connect_alignment_confidence: float = 0.0
    connect_alignment_note: str = ""
    notes_for_user: str = ""

    # Lifecycle (for the kanban; user can drag to update)
    column: str = "memory"

    # Source-side dates
    source_created_at: Optional[datetime] = None
    source_last_modified: Optional[datetime] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    categories: list[str] = Field(default_factory=list)

    # Pensieve-side bookkeeping
    enriched_at: datetime = Field(default_factory=_utcnow)
    enrichment_version: str = "v2"
    tokens_used: int = 0
    embedding_text: str = ""

    def to_chroma_metadata(self) -> dict[str, Any]:
        """Flatten to Chroma-friendly scalars (str/int/float/bool only)."""
        return {
            "source": self.source,
            "source_task_id": self.source_task_id,
            "list_name": self.list_name,
            "title": self.title,
            "original_notes": self.original_notes,
            "suggested_strand": self.suggested_strand or "",
            "strand_kind": self.strand_kind or "",
            "needs_human_strand_review": bool(self.needs_human_strand_review),
            "why": self.why,
            "impact": self.impact,
            "confidence_strand": float(self.confidence_strand),
            "confidence_impact": float(self.confidence_impact),
            "connect_goal_ids_csv": ",".join(self.connect_goal_ids),
            "connect_alignment_confidence": float(self.connect_alignment_confidence),
            "connect_alignment_note": self.connect_alignment_note,
            "notes_for_user": self.notes_for_user,
            "categories_csv": ",".join(self.categories),
            "column": self.column,
            "source_last_modified": (
                self.source_last_modified.isoformat() if self.source_last_modified else ""
            ),
            "due_date": self.due_date.isoformat() if self.due_date else "",
            "completed": bool(self.completed),
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
            "enrichment_version": self.enrichment_version,
            "enriched_at": self.enriched_at.isoformat(),
            "tokens_used": int(self.tokens_used),
        }

    def to_dashboard_dict(self) -> dict[str, Any]:
        """JSON shape expected by frontend-proto/pensieve.js."""
        return {
            "id": f"mem_{self.id}",
            "title": self.title,
            "suggested_strand": self.suggested_strand,
            "needs_human_strand_review": self.needs_human_strand_review,
            "why": self.why,
            "impact": self.impact,
            "strand_kind": self.strand_kind,
            "confidence_strand": self.confidence_strand,
            "confidence_impact": self.confidence_impact,
            "connect_goal_ids": self.connect_goal_ids,
            "connect_alignment_confidence": self.connect_alignment_confidence,
            "connect_alignment_note": self.connect_alignment_note,
            "column": self.column,
            "source": self.source,
            "source_task_id": self.source_task_id,
            "list_name": self.list_name,
            "notes_for_user": self.notes_for_user,
            "categories": self.categories,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "enriched_at": self.enriched_at.isoformat(),
        }


class Vial(BaseModel):
    """Closure record for a completed Memory. Phase 2; stub now."""

    id: str
    memory_id: str
    title: str
    impact_statement: str = ""
    captured_at: datetime = Field(default_factory=_utcnow)
    connect_goal_ids: list[str] = Field(default_factory=list)
    raw_memory_snapshot: dict[str, Any] = Field(default_factory=dict)
