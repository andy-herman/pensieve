"""Pydantic models for the persistent layer (Memory, Vial)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

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
    display_title: Optional[str] = None
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
            "display_title": self.display_title or "",
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
            "source_created_at": (
                self.source_created_at.isoformat() if self.source_created_at else ""
            ),
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
            "display_title": self.display_title,
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


def _new_vial_id() -> str:
    return f"vial_{uuid.uuid4().hex}"


class Vial(BaseModel):
    """A closure-capture record: what changed when a Memory was closed.

    Vials are durable promo evidence. They outlive their parent Memory —
    if the upstream To-Do task is later deleted (orphan sweep) or the
    Memory is re-edited / re-enriched, the Vial's snapshot fields preserve
    the closure-time context for future recap/promo use.
    """

    id: str = Field(default_factory=_new_vial_id)
    memory_id: str
    captured_at: datetime = Field(default_factory=_utcnow)

    # Either a meaningful captured note or an explicit skip marker
    capture_kind: Literal["captured", "skipped"] = "captured"
    captured_text: str = ""  # required (non-empty) iff capture_kind == "captured"

    # Reserved for v1.1 AI polish (empty in v1)
    polished_text: str = ""

    # Closure-time snapshots: frozen at create; don't follow Memory edits
    title_snapshot: str = ""
    display_title_snapshot: str = ""
    why_snapshot: str = ""
    impact_snapshot: str = ""
    connect_alignment_note_snapshot: str = ""
    connect_goal_ids_snapshot: list[str] = Field(default_factory=list)
    suggested_strand_snapshot: Optional[str] = None
    source_snapshot: str = ""
    source_task_id_snapshot: str = ""
    list_name_snapshot: str = ""
    column_snapshot: str = "closed"
    completed_at_snapshot: Optional[datetime] = None
    due_date_snapshot: Optional[datetime] = None

    # Provenance for future audit / UI hints
    source: str = "user"  # "user" | "ai_drafted" | "ai_edited" (v1: always "user")
    tokens_used: int = 0

    def to_chroma_metadata(self) -> dict[str, Any]:
        """Flatten to Chroma-friendly scalars (str/int/float/bool only)."""
        return {
            "memory_id": self.memory_id,
            "captured_at": self.captured_at.isoformat(),
            "capture_kind": self.capture_kind,
            "captured_text": self.captured_text,
            "polished_text": self.polished_text,
            "title_snapshot": self.title_snapshot,
            "display_title_snapshot": self.display_title_snapshot,
            "why_snapshot": self.why_snapshot,
            "impact_snapshot": self.impact_snapshot,
            "connect_alignment_note_snapshot": self.connect_alignment_note_snapshot,
            "connect_goal_ids_snapshot_csv": ",".join(self.connect_goal_ids_snapshot),
            "suggested_strand_snapshot": self.suggested_strand_snapshot or "",
            "source_snapshot": self.source_snapshot,
            "source_task_id_snapshot": self.source_task_id_snapshot,
            "list_name_snapshot": self.list_name_snapshot,
            "column_snapshot": self.column_snapshot,
            "completed_at_snapshot": (
                self.completed_at_snapshot.isoformat() if self.completed_at_snapshot else ""
            ),
            "due_date_snapshot": (
                self.due_date_snapshot.isoformat() if self.due_date_snapshot else ""
            ),
            "source": self.source,
            "tokens_used": int(self.tokens_used),
        }

    def to_dashboard_dict(self) -> dict[str, Any]:
        """JSON shape returned by Vial API endpoints."""
        return {
            "id": self.id,
            "memory_id": self.memory_id,
            "captured_at": self.captured_at.isoformat(),
            "capture_kind": self.capture_kind,
            "captured_text": self.captured_text,
            "polished_text": self.polished_text,
            "title_snapshot": self.title_snapshot,
            "display_title_snapshot": self.display_title_snapshot,
            "why_snapshot": self.why_snapshot,
            "impact_snapshot": self.impact_snapshot,
            "connect_alignment_note_snapshot": self.connect_alignment_note_snapshot,
            "connect_goal_ids_snapshot": list(self.connect_goal_ids_snapshot),
            "suggested_strand_snapshot": self.suggested_strand_snapshot,
            "source_snapshot": self.source_snapshot,
            "source_task_id_snapshot": self.source_task_id_snapshot,
            "list_name_snapshot": self.list_name_snapshot,
            "column_snapshot": self.column_snapshot,
            "completed_at_snapshot": (
                self.completed_at_snapshot.isoformat() if self.completed_at_snapshot else None
            ),
            "due_date_snapshot": (
                self.due_date_snapshot.isoformat() if self.due_date_snapshot else None
            ),
            "source": self.source,
            "tokens_used": self.tokens_used,
        }

    @classmethod
    def snapshot_from(
        cls,
        memory: "Memory",
        *,
        captured_text: str = "",
        capture_kind: str = "captured",
    ) -> "Vial":
        """Build a Vial that snapshots a Memory at closure-time.

        The Memory's promo-relevant context is frozen into the Vial so a
        later re-edit or re-enrich of the Memory doesn't rewrite history.
        """
        return cls(
            memory_id=memory.id,
            capture_kind=capture_kind,
            captured_text=captured_text,
            title_snapshot=memory.title,
            display_title_snapshot=memory.display_title or "",
            why_snapshot=memory.why,
            impact_snapshot=memory.impact,
            connect_alignment_note_snapshot=memory.connect_alignment_note,
            connect_goal_ids_snapshot=list(memory.connect_goal_ids),
            suggested_strand_snapshot=memory.suggested_strand,
            source_snapshot=memory.source,
            source_task_id_snapshot=memory.source_task_id,
            list_name_snapshot=memory.list_name,
            column_snapshot=memory.column,
            completed_at_snapshot=memory.completed_at,
            due_date_snapshot=memory.due_date,
        )
