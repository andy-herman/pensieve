"""ChromaDB-backed Vial store (closure-capture records)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from pensieve.config import Settings, get_settings
from pensieve.store.schema import Vial


def _parse_iso(value: object) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _build_document(v: Vial) -> str:
    """Embedding text for a Vial. Falls back to snapshot title if no captured text
    (skipped Vials still need a non-empty document or Chroma rejects them)."""
    parts = [v.captured_text, v.polished_text]
    body = "\n\n".join(p for p in parts if p)
    if body:
        return body
    # Fallback for skipped or empty Vials
    return f"[closure capture {v.capture_kind}] {v.title_snapshot or v.memory_id}"


class ChromaVialStore:
    """Wraps the ``vials`` Chroma collection.

    Vials are durable promo evidence. They deliberately do NOT cascade-delete
    when a parent Memory is removed — if the upstream To-Do task is later
    deleted (orphan sweep) the Vial remains as historical record. Snapshot
    fields on each Vial preserve closure-time context for promo/recap use
    even if the Memory is gone.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self._client = chromadb.PersistentClient(
            path=str(self.settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )
        self._vials = self._client.get_or_create_collection(
            name=self.settings.chroma_collection_vials,
            metadata={"hnsw:space": "cosine"},
        )

    # ----- writes -----

    def upsert_vial(self, vial: Vial) -> None:
        doc = _build_document(vial)
        self._vials.upsert(
            ids=[vial.id],
            documents=[doc],
            metadatas=[vial.to_chroma_metadata()],
        )

    def delete_vial(self, vial_id: str) -> None:
        self._vials.delete(ids=[vial_id])

    # ----- reads -----

    def get_vial(self, vial_id: str) -> Optional[Vial]:
        res = self._vials.get(ids=[vial_id], include=["metadatas"])
        if not res or not res.get("ids"):
            return None
        return self._reconstruct(res["ids"][0], (res.get("metadatas") or [{}])[0] or {})

    def list_vials(self) -> list[Vial]:
        res = self._vials.get(include=["metadatas"])
        out: list[Vial] = []
        for i, vid in enumerate(res.get("ids", []) or []):
            meta = (res.get("metadatas") or [{}])[i] or {}
            out.append(self._reconstruct(vid, meta))
        out.sort(key=lambda v: v.captured_at)
        return out

    def list_vials_for_memory(self, memory_id: str) -> list[Vial]:
        try:
            res = self._vials.get(where={"memory_id": memory_id}, include=["metadatas"])
        except Exception:
            # Fallback: full scan if Chroma rejects the where clause
            res = self._vials.get(include=["metadatas"])
        out: list[Vial] = []
        for i, vid in enumerate(res.get("ids", []) or []):
            meta = (res.get("metadatas") or [{}])[i] or {}
            if meta.get("memory_id") != memory_id:
                continue
            out.append(self._reconstruct(vid, meta))
        out.sort(key=lambda v: v.captured_at)
        return out

    def captured_count_by_memory(self) -> dict[str, int]:
        """One bulk query returning {memory_id: count_of_captured_vials}.

        Skipped Vials are excluded — they exist only to clear the
        ``pending_closure_capture`` chevron, not to count as evidence.
        """
        res = self._vials.get(include=["metadatas"])
        counts: dict[str, int] = {}
        for meta in res.get("metadatas", []) or []:
            meta = meta or {}
            if meta.get("capture_kind") != "captured":
                continue
            mid = meta.get("memory_id")
            if not mid:
                continue
            counts[mid] = counts.get(mid, 0) + 1
        return counts

    def has_any_vial_by_memory(self) -> set[str]:
        """One bulk query returning the set of memory_ids that have ANY Vial
        (captured or skipped). Used to compute pending_closure_capture so
        that a Skip also clears the chevron."""
        res = self._vials.get(include=["metadatas"])
        seen: set[str] = set()
        for meta in res.get("metadatas", []) or []:
            meta = meta or {}
            mid = meta.get("memory_id")
            if mid:
                seen.add(mid)
        return seen

    def count(self) -> int:
        return int(self._vials.count())

    # ----- internal -----

    def _reconstruct(self, vid: str, meta: dict) -> Vial:
        goal_ids_csv = (meta.get("connect_goal_ids_snapshot_csv") or "").strip()
        goal_ids = [g for g in goal_ids_csv.split(",") if g]
        captured = _parse_iso(meta.get("captured_at")) or datetime.fromtimestamp(0)
        return Vial(
            id=vid,
            memory_id=meta.get("memory_id", ""),
            captured_at=captured,
            capture_kind=meta.get("capture_kind", "captured"),
            captured_text=meta.get("captured_text", ""),
            polished_text=meta.get("polished_text", ""),
            title_snapshot=meta.get("title_snapshot", ""),
            display_title_snapshot=meta.get("display_title_snapshot", ""),
            why_snapshot=meta.get("why_snapshot", ""),
            impact_snapshot=meta.get("impact_snapshot", ""),
            connect_alignment_note_snapshot=meta.get("connect_alignment_note_snapshot", ""),
            connect_goal_ids_snapshot=goal_ids,
            suggested_strand_snapshot=(meta.get("suggested_strand_snapshot") or None),
            source_snapshot=meta.get("source_snapshot", ""),
            source_task_id_snapshot=meta.get("source_task_id_snapshot", ""),
            list_name_snapshot=meta.get("list_name_snapshot", ""),
            column_snapshot=meta.get("column_snapshot", "closed"),
            completed_at_snapshot=_parse_iso(meta.get("completed_at_snapshot")),
            due_date_snapshot=_parse_iso(meta.get("due_date_snapshot")),
            source=meta.get("source", "user"),
            tokens_used=int(meta.get("tokens_used", 0) or 0),
        )
