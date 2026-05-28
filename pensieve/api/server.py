"""FastAPI app — HTTP layer over ChromaMemoryStore + sync trigger."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pensieve.config import REPO_ROOT, get_settings
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.store import ChromaMemoryStore
from pensieve.sync_state import get_tracker


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Pensieve API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_origin_regex=r"file://.*|null",
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    store = ChromaMemoryStore(settings)

    @app.get("/api/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "memories": store.count(),
            "chroma_dir": str(settings.chroma_dir),
            "default_source": settings.default_source,
        }

    @app.get("/api/memories")
    def list_memories() -> dict[str, Any]:
        mems = store.list_memories()
        return {
            "count": len(mems),
            "memories": [m.to_dashboard_dict() for m in mems],
        }

    @app.get("/api/memories/{memory_id}")
    def get_memory(memory_id: str) -> dict[str, Any]:
        mem = store.get_memory(memory_id)
        if mem is None:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        return mem.to_dashboard_dict()

    @app.patch("/api/memories/{memory_id}/column")
    def patch_column(memory_id: str, body: dict[str, str]) -> dict[str, Any]:
        col = (body or {}).get("column", "").strip()
        if col not in ("memory", "dive", "reverie", "reflection", "vial"):
            raise HTTPException(status_code=400, detail=f"Invalid column: {col}")
        ok = store.update_column(memory_id, col)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        return {"ok": True, "id": memory_id, "column": col}

    @app.patch("/api/memories/{memory_id}")
    def patch_memory(memory_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Edit a Memory in place from the dashboard.

        Accepts any of: title, why, impact, suggested_strand, strand_kind,
        connect_goal_ids (list), connect_alignment_note, notes_for_user,
        column, needs_human_strand_review.
        """
        mem = store.get_memory(memory_id)
        if mem is None:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        editable_str = {
            "title",
            "why",
            "impact",
            "suggested_strand",
            "strand_kind",
            "connect_alignment_note",
            "notes_for_user",
            "column",
        }
        for key in editable_str:
            if key in body and body[key] is not None:
                setattr(mem, key, str(body[key]))
        if "connect_goal_ids" in body and isinstance(body["connect_goal_ids"], list):
            mem.connect_goal_ids = [str(g) for g in body["connect_goal_ids"] if g]
        if "needs_human_strand_review" in body:
            mem.needs_human_strand_review = bool(body["needs_human_strand_review"])
        if mem.column not in ("memory", "dive", "reverie", "reflection", "vial"):
            raise HTTPException(status_code=400, detail=f"Invalid column: {mem.column}")
        store.upsert_memory(mem)
        return {"ok": True, "memory": mem.to_dashboard_dict()}

    @app.get("/api/search")
    def search(q: str = Query(..., min_length=1), top_k: int = 12) -> dict[str, Any]:
        results = store.search(q, top_k=top_k)
        return {
            "query": q,
            "count": len(results),
            "memories": [m.to_dashboard_dict() for m in results],
        }

    @app.get("/api/goals")
    def goals() -> dict[str, Any]:
        return {"goals": load_connect_goals()}

    @app.get("/api/sync/status")
    def sync_status() -> dict[str, Any]:
        return get_tracker().snapshot()

    @app.post("/api/sync")
    def trigger_sync(body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Kick off a background sync from the configured source (default outlook_com).

        Body (all optional):
          source: "outlook_com" | "sample_file" (default: settings.default_source)
          lists:  list[str] (Outlook task folder names to restrict to; default = all)
          force:  bool (re-enrich every task, even unchanged ones)
        """
        body = body or {}
        tracker = get_tracker()
        if tracker.is_running():
            snap = tracker.snapshot()
            return {"ok": False, "already_running": True, "state": snap}

        src_name = (body.get("source") or settings.default_source or "outlook_com").strip()
        lists_raw = body.get("lists") or []
        if isinstance(lists_raw, str):
            lists_raw = [lists_raw]
        list_names: list[str] = [str(x).strip() for x in lists_raw if str(x).strip()]
        force = bool(body.get("force", False))

        tracker.begin(
            source=src_name,
            lists=list_names,
            message="Connecting to source...",
        )

        def _runner() -> None:
            # COM apartments must be initialized per-thread on Windows.
            _com_inited = False
            try:
                try:
                    import pythoncom  # type: ignore[import-not-found]

                    pythoncom.CoInitialize()
                    _com_inited = True
                except Exception:
                    pass

                from pensieve.cli import _build_recent_context_from_chroma, _build_source
                from pensieve.sync import run_sync

                src = _build_source(src_name, list_names=list_names or None)
                strand_catalog = None
                recent_context = None
                if src_name == "outlook_com":
                    if settings.samples_path.exists():
                        import json as _json

                        with settings.samples_path.open("r", encoding="utf-8") as f:
                            blob = _json.load(f)
                        strand_catalog = blob.get("strand_catalog")
                    recent_context = _build_recent_context_from_chroma()
                tracker.update("Enriching new and changed tasks...")
                stats = run_sync(
                    src,
                    strand_catalog=strand_catalog,
                    recent_context=recent_context,
                    dry_run=False,
                    force=force,
                )
                tracker.finish_ok(
                    {
                        "total_tasks": stats.total_tasks,
                        "new_enriched": stats.new_enriched,
                        "updated_enriched": stats.updated_enriched,
                        "skipped_unchanged": stats.skipped_unchanged,
                        "failed": stats.failed,
                        "review_queue": stats.review_queue,
                        "tokens_used": stats.tokens_used,
                    },
                    message=(
                        f"Sync complete: {stats.new_enriched} new, "
                        f"{stats.updated_enriched} updated, "
                        f"{stats.skipped_unchanged} unchanged."
                    ),
                )
            except Exception as e:
                tracker.finish_error(str(e))
            finally:
                if _com_inited:
                    try:
                        import pythoncom  # type: ignore[import-not-found]

                        pythoncom.CoUninitialize()
                    except Exception:
                        pass

        t = threading.Thread(target=_runner, daemon=True, name="pensieve-sync")
        tracker.attach_thread(t)
        t.start()
        return {"ok": True, "started": True, "state": tracker.snapshot()}

    @app.get("/api/lists")
    def lists() -> dict[str, Any]:
        """Enumerate Outlook task folders / Microsoft To-Do lists."""
        from pensieve.sources.outlook_com import OutlookCOMSource, OutlookCOMUnavailable

        try:
            src = OutlookCOMSource()
            folders = src.discover_lists()
        except OutlookCOMUnavailable as e:
            raise HTTPException(status_code=503, detail=f"Outlook COM unavailable: {e}") from e
        return {"count": len(folders), "lists": folders}

    @app.post("/api/memories/{memory_id}/regenerate")
    def regenerate_memory(memory_id: str) -> dict[str, Any]:
        """Re-run AI enrichment on a single Memory.

        Regenerates: title (kept from source), why, impact, suggested_strand,
        strand_kind, confidences, connect_goal_ids, connect_alignment_note,
        needs_human_strand_review.

        Preserves the user's manual: column (lifecycle placement) and
        notes_for_user (private note).
        """
        from datetime import datetime, timezone

        from pensieve.cli import _build_recent_context_from_chroma
        from pensieve.enrichment import AzureOpenAIChatClient, enrich_task, load_connect_goals
        from pensieve.sources.base import RawTask

        existing = store.get_memory(memory_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

        # Reconstruct a RawTask from the persisted Memory.
        task = RawTask(
            id=existing.source_task_id or existing.id,
            title=existing.title,
            notes=existing.original_notes,
            list_name=existing.list_name or "",
            created_at=existing.source_created_at,
            last_modification_time=existing.source_last_modified,
            completed=existing.completed,
            completed_at=existing.completed_at,
            categories=list(existing.categories or []),
            due_date=existing.due_date,
            source=existing.source or "unknown",
        )

        # Strand catalog from samples.json; recent context from current Chroma state.
        strand_catalog = None
        if settings.samples_path.exists():
            import json as _json

            with settings.samples_path.open("r", encoding="utf-8") as f:
                blob = _json.load(f)
            strand_catalog = blob.get("strand_catalog")
        if strand_catalog is None:
            raise HTTPException(status_code=500, detail="strand_catalog missing (samples.json)")

        recent_context = _build_recent_context_from_chroma()
        connect_goals = load_connect_goals()

        try:
            client = AzureOpenAIChatClient(settings)
            result = enrich_task(
                task,
                strand_catalog=strand_catalog,
                recent_context=recent_context,
                client=client,
                connect_goals=connect_goals,
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Enrichment failed: {e}") from e

        # Overlay regenerated fields onto the existing Memory; preserve user-only fields.
        existing.suggested_strand = result.suggested_strand
        existing.strand_kind = result.strand_kind
        existing.needs_human_strand_review = result.needs_human_strand_review
        existing.why = result.why
        existing.impact = result.impact
        existing.confidence_strand = result.confidence_strand
        existing.confidence_impact = result.confidence_impact
        existing.connect_goal_ids = list(result.connect_goal_ids or [])
        existing.connect_alignment_confidence = result.connect_alignment_confidence
        existing.connect_alignment_note = result.connect_alignment_note
        # Preserve user-only fields: column, notes_for_user
        existing.tokens_used = (existing.tokens_used or 0) + (result.tokens_used or 0)
        existing.enriched_at = datetime.now(timezone.utc)
        store.upsert_memory(existing)
        return {
            "ok": True,
            "tokens_used": result.tokens_used,
            "memory": existing.to_dashboard_dict(),
        }

    # Serve the dashboard from /, if frontend-proto exists.
    frontend_dir: Path = REPO_ROOT / "frontend-proto"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="dashboard")

    return app


# Module-level app for uvicorn `pensieve.api.server:app`
app = create_app()
