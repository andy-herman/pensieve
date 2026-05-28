"""FastAPI app — read-only HTTP layer over ChromaMemoryStore."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pensieve.config import REPO_ROOT, get_settings
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.store import ChromaMemoryStore


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

    # Serve the dashboard from /, if frontend-proto exists.
    frontend_dir: Path = REPO_ROOT / "frontend-proto"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="dashboard")

    return app


# Module-level app for uvicorn `pensieve.api.server:app`
app = create_app()
