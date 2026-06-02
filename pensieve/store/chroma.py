"""ChromaDB-backed memory store (embedded, persistent)."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from pensieve.config import Settings, get_settings
from pensieve.store.schema import Memory


def _parse_iso(value: object) -> Optional[datetime]:
    """Parse an ISO datetime string from Chroma metadata; None if blank/invalid."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _build_document(m: Memory) -> str:
    """Text chunk that drives the embedding. Combines title + why + impact + notes."""
    parts = [
        m.title,
        m.why,
        m.impact,
        m.connect_alignment_note,
        m.original_notes,
    ]
    return "\n\n".join(p for p in parts if p)


class ChromaMemoryStore:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self._client = chromadb.PersistentClient(
            path=str(self.settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )
        self._memories = self._client.get_or_create_collection(
            name=self.settings.chroma_collection_memories,
            metadata={"hnsw:space": "cosine"},
        )

    # ----- writes -----

    def upsert_memory(self, memory: Memory) -> None:
        doc = _build_document(memory)
        if not doc:
            doc = memory.title or memory.id
        memory.embedding_text = doc
        self._memories.upsert(
            ids=[memory.id],
            documents=[doc],
            metadatas=[memory.to_chroma_metadata()],
        )

    def delete_memory(self, memory_id: str) -> None:
        self._memories.delete(ids=[memory_id])

    def update_column(self, memory_id: str, column: str) -> bool:
        existing = self._memories.get(ids=[memory_id], include=["metadatas"])
        if not existing or not existing.get("ids"):
            return False
        meta = (existing.get("metadatas") or [{}])[0] or {}
        meta["column"] = column
        self._memories.update(ids=[memory_id], metadatas=[meta])
        return True

    # ----- reads -----

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        res = self._memories.get(ids=[memory_id], include=["metadatas", "documents"])
        if not res or not res.get("ids"):
            return None
        return self._reconstruct(
            res["ids"][0], (res.get("metadatas") or [{}])[0], (res.get("documents") or [""])[0]
        )

    def list_memories(self) -> list[Memory]:
        res = self._memories.get(include=["metadatas", "documents"])
        out: list[Memory] = []
        for i, mid in enumerate(res.get("ids", []) or []):
            meta = (res.get("metadatas") or [{}])[i] or {}
            doc = (res.get("documents") or [""])[i] or ""
            out.append(self._reconstruct(mid, meta, doc))
        return out

    def search(self, query: str, top_k: int = 12) -> list[Memory]:
        if not query.strip():
            return []
        res = self._memories.query(query_texts=[query], n_results=top_k)
        ids = (res.get("ids") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        out: list[Memory] = []
        for i, mid in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            doc = docs[i] if i < len(docs) else ""
            out.append(self._reconstruct(mid, meta or {}, doc or ""))
        return out

    def count(self) -> int:
        return int(self._memories.count())

    def known_ids(self) -> set[str]:
        res = self._memories.get(include=[])
        return set(res.get("ids") or [])

    def find_orphan_ids(
        self,
        source: str,
        live_ids: set[str],
        covered_lists: Optional[set[str]] = None,
    ) -> list[tuple[str, str, str]]:
        """Find memories that no longer exist at the source.

        Scoped to ``source`` so a sync of Outlook never deletes sample-data
        memories (or vice versa). When ``covered_lists`` is provided (a set of
        list_name strings the current sync was responsible for), the scan is
        further narrowed to those lists — so syncing only "Agentic AI work"
        cannot orphan tasks in "CISO GRC" lists we didn't pull from.

        Returns a list of ``(memory_id, title, list_name)`` tuples for
        deletion + audit logging by the caller.
        """
        try:
            res = self._memories.get(where={"source": source}, include=["metadatas"])
        except Exception:
            # Fallback for chroma versions that dislike the where clause.
            res = self._memories.get(include=["metadatas"])
        ids = res.get("ids") or []
        metas = res.get("metadatas") or []
        out: list[tuple[str, str, str]] = []
        for mid, meta in zip(ids, metas, strict=False):
            meta = meta or {}
            if meta.get("source") != source:
                continue
            list_name = meta.get("list_name", "") or ""
            if covered_lists is not None and list_name not in covered_lists:
                continue
            if mid in live_ids:
                continue
            out.append((mid, meta.get("title", "") or "", list_name))
        return out

    # ----- internal -----

    def _reconstruct(self, mid: str, meta: dict, doc: str) -> Memory:
        goal_ids_csv = (meta.get("connect_goal_ids_csv") or "").strip()
        goal_ids = [g for g in goal_ids_csv.split(",") if g]
        cats_csv = (meta.get("categories_csv") or "").strip()
        cats = [c for c in cats_csv.split(",") if c]
        # One-time migrations for columns that were renamed in 2026-05-28's
        # lifecycle simplification (memory/dive/review/closed). Any persisted
        # memory in the old columns rehydrates into its closest successor; the
        # next upsert writes the migrated column back to Chroma.
        _COL_MIGRATE = {
            "reverie": "memory",  # Phase 2.5 concept; deferred
            "reflection": "closed",  # closure-debrief collapsed into closed
            "vial": "review",  # vial-as-column became user-driven review
        }
        column = meta.get("column", "memory")
        column = _COL_MIGRATE.get(column, column)
        kwargs: dict = dict(
            id=mid,
            source=meta.get("source", "unknown"),
            source_task_id=meta.get("source_task_id", mid),
            list_name=meta.get("list_name", ""),
            title=meta.get("title", ""),
            display_title=(meta.get("display_title") or None),
            original_notes=meta.get("original_notes", ""),
            suggested_strand=(meta.get("suggested_strand") or None),
            strand_kind=(meta.get("strand_kind") or None),
            needs_human_strand_review=bool(meta.get("needs_human_strand_review", False)),
            why=meta.get("why", ""),
            impact=meta.get("impact", ""),
            confidence_strand=float(meta.get("confidence_strand", 0.0) or 0.0),
            confidence_impact=float(meta.get("confidence_impact", 0.0) or 0.0),
            connect_goal_ids=goal_ids,
            connect_alignment_confidence=float(meta.get("connect_alignment_confidence", 0.0) or 0.0),
            connect_alignment_note=meta.get("connect_alignment_note", ""),
            notes_for_user=meta.get("notes_for_user", ""),
            categories=cats,
            column=column,
            source_created_at=_parse_iso(meta.get("source_created_at")),
            source_last_modified=_parse_iso(meta.get("source_last_modified")),
            due_date=_parse_iso(meta.get("due_date")),
            completed=bool(meta.get("completed", False)),
            completed_at=_parse_iso(meta.get("completed_at")),
            enrichment_version=meta.get("enrichment_version", "v2"),
            tokens_used=int(meta.get("tokens_used", 0) or 0),
            embedding_text=doc,
        )
        # Only override the default-factory enriched_at if Chroma actually has
        # the persisted value. Pre-fix memories upserted before this field was
        # round-tripped will fall back to the schema default (now()).
        enriched = _parse_iso(meta.get("enriched_at"))
        if enriched is not None:
            kwargs["enriched_at"] = enriched
        return Memory(**kwargs)

    def upsert_many(self, memories: Iterable[Memory]) -> int:
        n = 0
        for m in memories:
            self.upsert_memory(m)
            n += 1
        return n
