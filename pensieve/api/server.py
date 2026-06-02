"""FastAPI app — HTTP layer over ChromaMemoryStore + sync trigger."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pensieve.config import REPO_ROOT, get_settings
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.sources.outlook_com_sink import get_sink_for_source
from pensieve.sources.sink import TaskSink
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

    def _mirror_column_to_source(memory_id: str, column: str) -> dict[str, Any]:
        """Best-effort writeback of `pensieve/col:<col>` to the upstream task.

        Returns a small status dict the API surfaces back to the dashboard so
        the user knows whether the mirror tag landed. Failure is non-fatal:
        the local column change has already been persisted to Chroma and the
        next successful sync will reconcile from the user's drag.
        """
        if not settings.mirror_to_source:
            return {"mirrored": False, "reason": "disabled"}
        mem = store.get_memory(memory_id)
        if mem is None:
            return {"mirrored": False, "reason": "memory-missing"}
        sink: Optional[TaskSink] = get_sink_for_source(mem.source)
        if sink is None:
            return {"mirrored": False, "reason": f"no-sink-for-{mem.source}"}
        try:
            ok = sink.set_column_tag(
                mem.source_task_id,
                column,
                prefix=settings.mirror_tag_prefix,
            )
            return {
                "mirrored": bool(ok),
                "reason": "ok" if ok else "task-not-found-at-source",
            }
        except Exception as e:
            return {"mirrored": False, "reason": f"sink-error: {e}"}

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
        if col not in ("memory", "dive", "review", "closed"):
            raise HTTPException(status_code=400, detail=f"Invalid column: {col}")
        ok = store.update_column(memory_id, col)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        mirror_result = _mirror_column_to_source(memory_id, col)
        return {"ok": True, "id": memory_id, "column": col, "mirror": mirror_result}

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
        if mem.column not in ("memory", "dive", "review", "closed"):
            raise HTTPException(status_code=400, detail=f"Invalid column: {mem.column}")
        store.upsert_memory(mem)
        mirror_result = None
        if "column" in body and body["column"] is not None:
            mirror_result = _mirror_column_to_source(memory_id, mem.column)
        return {"ok": True, "memory": mem.to_dashboard_dict(), "mirror": mirror_result}

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
        import json as _json

        meta: dict[str, Any] = {}
        path = settings.connect_goals_path
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    raw = _json.load(f)
                if isinstance(raw, dict):
                    meta = raw.get("_meta") or {}
            except Exception:
                meta = {}
        return {"goals": load_connect_goals(), "_meta": meta}

    @app.post("/api/goals/import")
    async def import_goals(file: "UploadFile" = File(...)) -> dict[str, Any]:  # noqa: F821, B008
        """Parse an uploaded Connect PDF and return a proposed goals payload.

        Does NOT persist. The frontend shows the proposal for review, then
        the user clicks Save -> POST /api/goals to commit.
        """
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a .pdf")
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty")
        if len(pdf_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF must be smaller than 5 MB")

        from pensieve.enrichment.goals_importer import import_pdf_to_goals

        try:
            payload = import_pdf_to_goals(pdf_bytes, source_label=f"Imported from {file.filename}")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF import failed: {e}") from e

        return {"ok": True, "proposal": payload}

    @app.post("/api/goals")
    def save_goals(body: dict[str, Any]) -> dict[str, Any]:
        """Persist a goals payload to data/connect-goals.json.

        Body shape (from the editor or from /api/goals/import's response):
          { "_meta": {...optional...}, "goals": [ {id, number, short_name, ...}, ... ] }

        Validates that each goal has at least id + short_name. Overwrites the
        file. Invalidates the in-process cache so the next enrichment sees the
        new goals immediately.
        """
        import json as _json

        from pensieve.enrichment import connect_goals as _cg_mod

        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object")
        goals_in = body.get("goals")
        if not isinstance(goals_in, list):
            raise HTTPException(status_code=400, detail="Body.goals must be a list")
        seen_ids: set[str] = set()
        for i, g in enumerate(goals_in):
            if not isinstance(g, dict):
                raise HTTPException(status_code=400, detail=f"goals[{i}] must be an object")
            gid = (g.get("id") or "").strip()
            short = (g.get("short_name") or "").strip()
            if not gid or not short:
                raise HTTPException(status_code=400, detail=f"goals[{i}] requires id and short_name")
            if gid in seen_ids:
                raise HTTPException(status_code=400, detail=f"Duplicate goal id: {gid}")
            seen_ids.add(gid)

        payload: dict[str, Any] = {
            "_meta": body.get("_meta") or {},
            "goals": goals_in,
        }
        if "behaviors" in body:
            payload["behaviors"] = body["behaviors"]

        path = settings.connect_goals_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=2)

        # Drop cached views so the next read picks up the new file.
        _cg_mod.load_connect_goals.cache_clear()  # type: ignore[attr-defined]
        _cg_mod.goals_index.cache_clear()  # type: ignore[attr-defined]

        return {"ok": True, "saved": len(goals_in), "path": str(path)}

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
                        "deleted": stats.deleted,
                        "failed": stats.failed,
                        "review_queue": stats.review_queue,
                        "tokens_used": stats.tokens_used,
                    },
                    message=(
                        f"Sync complete: {stats.new_enriched} new, "
                        f"{stats.updated_enriched} updated, "
                        f"{stats.deleted} deleted, "
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
        """Enumerate Outlook task folders / Microsoft To-Do lists.

        FastAPI dispatches sync routes onto worker threads from a pool, and
        COM apartments must be initialized per-thread on Windows. Without
        the explicit CoInitialize/CoUninitialize bracket below, win32com
        raises ``(-2147221008, 'CoInitialize has not been called.')`` on
        any worker thread that hasn't been used for a COM call before.
        """
        from pensieve.sources.outlook_com import OutlookCOMSource, OutlookCOMUnavailable

        _com_inited = False
        try:
            try:
                import pythoncom  # type: ignore[import-not-found]

                pythoncom.CoInitialize()
                _com_inited = True
            except Exception:
                pass

            try:
                src = OutlookCOMSource()
                folders = src.discover_lists()
            except OutlookCOMUnavailable as e:
                raise HTTPException(status_code=503, detail=f"Outlook COM unavailable: {e}") from e
            return {"count": len(folders), "lists": folders}
        finally:
            if _com_inited:
                try:
                    import pythoncom  # type: ignore[import-not-found]

                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    @app.post("/api/memories/{memory_id}/regenerate")
    def regenerate_memory(memory_id: str) -> dict[str, Any]:
        """Re-run AI enrichment on a single Memory.

        Regenerates: title (kept from source), why, impact, suggested_strand,
        strand_kind, confidences, connect_goal_ids, connect_alignment_note,
        needs_human_strand_review.

        Preserves the user's manual: column (lifecycle placement) and
        notes_for_user (private note).
        """
        from pensieve.cli import _build_recent_context_from_chroma
        from pensieve.enrichment import AzureOpenAIChatClient, enrich_task, load_connect_goals
        from pensieve.sources.base import RawTask
        from pensieve.sync import overlay_regeneration

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

        merged = overlay_regeneration(existing, task, result)
        store.upsert_memory(merged)
        return {
            "ok": True,
            "tokens_used": result.tokens_used,
            "memory": merged.to_dashboard_dict(),
        }

    @app.post("/api/recap")
    def generate_recap_route(body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Draft a Microsoft Connect-format recap from enriched memories.

        Body (all optional):
          scope:        "all" | "completed" | "review" (default "all")
          goal_ids:     list[str] to restrict to specific Connect goals
          period_label: free-text reflection period for the header
        """
        from pensieve.recap import generate_recap

        body = body or {}
        scope = (body.get("scope") or "all").strip()
        goal_ids_raw = body.get("goal_ids") or None
        goal_ids = (
            [str(g) for g in goal_ids_raw if str(g).strip()]
            if isinstance(goal_ids_raw, list)
            else None
        )
        period_label = str(body.get("period_label") or "").strip()

        memories = store.list_memories()
        try:
            recap = generate_recap(
                memories,
                scope=scope,
                goal_ids=goal_ids,
                period_label=period_label,
                settings=settings,
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Recap generation failed: {e}") from e

        from pensieve.recap_history import save_recap

        summary = None
        try:
            summary = save_recap(recap, settings=settings)
        except Exception:
            summary = None  # history is best-effort; never fail the recap on it
        return {"ok": True, "recap": recap, "history": summary}

    @app.post("/api/recap/export")
    def export_recap(body: dict[str, Any]) -> Response:
        """Render a recap payload to a downloadable .docx."""
        from pensieve.recap_export import build_recap_docx

        recap = (body or {}).get("recap")
        if not isinstance(recap, dict) or not recap.get("sections"):
            raise HTTPException(status_code=400, detail="Body.recap with sections is required")
        try:
            data = build_recap_docx(recap)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DOCX export failed: {e}") from e
        filename = "connect-recap.docx"
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/recap/history")
    def recap_history() -> dict[str, Any]:
        from pensieve.recap_history import list_history

        return {"ok": True, "runs": list_history(settings)}

    @app.get("/api/recap/history/{rid}")
    def recap_history_one(rid: str) -> dict[str, Any]:
        from pensieve.recap_history import load_recap

        record = load_recap(rid, settings)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Recap {rid} not found")
        return {"ok": True, "record": record}

    @app.post("/api/recap/revise")
    def revise_recap(body: dict[str, Any]) -> dict[str, Any]:
        """Re-draft one recap section using the user's correction (recap chat)."""
        from pensieve.recap import revise_recap_section

        body = body or {}
        goal_id = (body.get("goal_id") or "").strip()
        feedback = (body.get("feedback") or "").strip()
        scope = (body.get("scope") or "all").strip()
        if not goal_id:
            raise HTTPException(status_code=400, detail="goal_id is required")
        if not feedback:
            raise HTTPException(status_code=400, detail="feedback is required")
        memories = store.list_memories()
        try:
            section = revise_recap_section(
                memories, goal_id, feedback, scope=scope, settings=settings
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Revision failed: {e}") from e
        return {"ok": True, "section": section}

    @app.get("/api/graph")
    def graph(threshold: float = Query(0.6, ge=0.0, le=1.0), max_per_node: int = 3) -> dict[str, Any]:
        """Constellation graph: goal hubs + task nodes + alignment/semantic edges.

        Semantic edges are derived from the Chroma embeddings (the same vectors
        that power search), so related tasks link up even when the user never
        tagged them with the same goal.
        """
        from pensieve.graph import build_graph

        memories = store.list_memories()
        # Pull embeddings straight from the collection so we don't recompute them.
        # Chroma returns embeddings as a numpy ndarray, so avoid truthiness on it
        # (an `or []` fallback raises "truth value ambiguous") and convert per-row.
        embeddings: dict[str, Any] = {}
        try:
            raw = store._memories.get(include=["embeddings"])  # noqa: SLF001
            ids = raw.get("ids") or []
            vecs = raw.get("embeddings")
            if vecs is not None:
                for mid, vec in zip(ids, vecs, strict=False):
                    if vec is not None:
                        embeddings[mid] = [float(x) for x in vec]
        except Exception:
            embeddings = {}

        goals = load_connect_goals()
        g = build_graph(
            memories,
            goals,
            embeddings or None,
            semantic_threshold=threshold,
            max_semantic_per_node=max_per_node,
        )
        return {"ok": True, "graph": g}

    @app.get("/api/docs")
    def docs_list() -> dict[str, Any]:
        from pensieve.docs_store import list_docs

        return {"ok": True, "docs": list_docs(settings)}

    @app.post("/api/docs")
    def docs_create(body: dict[str, Any]) -> dict[str, Any]:
        from pensieve.docs_store import create_doc

        title = (body or {}).get("title", "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        return {"ok": True, "doc": create_doc(title, settings)}

    @app.get("/api/docs/{doc_id}")
    def docs_get(doc_id: str) -> dict[str, Any]:
        from pensieve.docs_store import read_doc

        doc = read_doc(doc_id, settings)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Doc {doc_id} not found")
        return {"ok": True, "doc": doc}

    @app.put("/api/docs/{doc_id}")
    def docs_save(doc_id: str, body: dict[str, Any]) -> dict[str, Any]:
        from pensieve.docs_store import save_doc

        content = (body or {}).get("content")
        if content is None:
            raise HTTPException(status_code=400, detail="content is required")
        return {"ok": True, "doc": save_doc(doc_id, content, settings)}

    @app.delete("/api/docs/{doc_id}")
    def docs_delete(doc_id: str) -> dict[str, Any]:
        from pensieve.docs_store import delete_doc

        ok = delete_doc(doc_id, settings)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Doc {doc_id} not found")
        return {"ok": True}

    # Serve the dashboard from /, if frontend-proto exists.
    frontend_dir: Path = REPO_ROOT / "frontend-proto"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="dashboard")

    return app


# Module-level app for uvicorn `pensieve.api.server:app`
app = create_app()
