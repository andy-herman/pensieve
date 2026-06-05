"""FastAPI app — HTTP layer over ChromaMemoryStore + sync trigger."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pensieve import achievement_state as achievement_state_mod
from pensieve import achievements as achievements_mod
from pensieve import garden
from pensieve import quest_state as quest_state_mod
from pensieve import quests as quests_mod
from pensieve.config import REPO_ROOT, get_settings
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.scheduler import AutoSyncScheduler, start_sync_job
from pensieve.sources.outlook_com_sink import get_sink_for_source
from pensieve.sources.sink import TaskSink
from pensieve.store import ChromaMemoryStore, ChromaVialStore
from pensieve.store.schema import Vial
from pensieve.sync_state import get_tracker


def create_app() -> FastAPI:
    settings = get_settings()
    scheduler_holder: dict[str, AutoSyncScheduler] = {}

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        scheduler = AutoSyncScheduler(settings, get_tracker())
        scheduler.start()
        scheduler_holder["scheduler"] = scheduler
        try:
            yield
        finally:
            scheduler.stop(timeout=5.0)
            scheduler_holder.pop("scheduler", None)

    app = FastAPI(title="Pensieve API", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_origin_regex=r"file://.*|null",
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    store = ChromaMemoryStore(settings)
    vial_store = ChromaVialStore(settings)

    def _enrich_with_vials(mem_dict: dict[str, Any], memory_id: str,
                           captured_counts: dict[str, int],
                           any_vial_ids: set[str]) -> dict[str, Any]:
        """Add vials_count + pending_closure_capture to a Memory dashboard dict.

        Pending = column is closed AND no Vial (captured or skipped) exists
        for this memory. A Skip clears the chevron without adding to
        vials_count (which only counts captured Vials).
        """
        is_closed = mem_dict.get("column") == "closed"
        mem_dict["vials_count"] = captured_counts.get(memory_id, 0)
        mem_dict["pending_closure_capture"] = bool(is_closed and memory_id not in any_vial_ids)
        return mem_dict

    def _enrich_with_freshness(mem_dict: dict[str, Any], memory: Any,
                               now: datetime,
                               captured_counts: dict[str, int]) -> dict[str, Any]:
        """Add Garden v1 derived fields: freshness + is_overdue.

        Pure-function enrichment at the API boundary (same pattern as
        ``pending_closure_capture``). Memory model stays clean of Garden
        concepts. ``captured_counts`` is used to decide ``closed_vialed``
        — skipped Vials must NOT promote a closed card to that state.
        """
        has_captured = captured_counts.get(memory.id, 0) > 0
        mem_dict["freshness"] = garden.derive_freshness(
            memory, now, has_captured_vial=has_captured
        )
        mem_dict["is_overdue"] = garden.is_overdue(memory, now)
        return mem_dict

    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    # ----- Garden v2 quest helpers ------------------------------------------

    def _get_or_init_quest_state(now: datetime) -> quest_state_mod.QuestState:
        """Load quest state and roll the day if needed.

        On day rollover (first request of a new calendar day, UTC):
        1. Snapshot whether the board is clean RIGHT NOW into the
           previous day's history slot (best-available approximation of
           "yesterday end-of-day"). Recomputes ``clean_streak_d``.
        2. Generate today's quests based on the current board + the
           freshly-computed clean_streak_d.
        3. Persist atomically.

        Same-day calls are read-only.
        """
        state = quest_state_mod.load_state(settings.garden_quests_path)
        if quest_state_mod.is_today_row(state.today, now):
            return state

        # Day rollover — generate today.
        mems = store.list_memories()
        captured_counts = vial_store.captured_count_by_memory()
        was_clean = quests_mod.is_board_clean(
            mems, now, captured_counts=captured_counts
        )
        # Capture yesterday's intrinsic health snapshot for the level-summary
        # endpoint (Garden v3) — uses the streak we had BEFORE this rollover.
        snapshot = garden.compute_board_health(
            mems,
            now,
            captured_counts=captured_counts,
            clean_streak_d=state.clean_streak_d,
            quest_bonus=0,
        )
        quest_state_mod.record_yesterday_clean(
            state, was_clean=was_clean, now=now,
            health_score=int(snapshot["score"]),
        )
        # Pre-compute today's intrinsic health to drive the hit-95-health gate.
        prelim = garden.compute_board_health(
            mems,
            now,
            captured_counts=captured_counts,
            clean_streak_d=state.clean_streak_d,
            quest_bonus=0,
        )
        new_quests = quests_mod.generate_quests(
            mems,
            now,
            captured_counts=captured_counts,
            current_health=int(prelim["score"]),
        )
        state.today = quest_state_mod.TodayRow(
            date=now.astimezone(timezone.utc).strftime("%Y-%m-%d"),
            generated_at=now,
            quests=new_quests,
            all_done_bonus_grants=0,
        )
        quest_state_mod.save_state(state, settings.garden_quests_path)
        return state

    def _maybe_complete_quests(memory_id: Optional[str] = None) -> None:
        """Re-evaluate today's quests against current store state.

        Called from every tending endpoint AFTER the ``last_tended_at``
        bump succeeds. Idempotent — only persists when a quest actually
        transitions pending → complete.

        ``memory_id`` is unused today (we re-evaluate the full quest list
        because completion may depend on cross-memory state like "all
        targets tended"), but is kept as a hook for future per-quest
        targeting if needed.
        """
        now = _now_utc()
        state = quest_state_mod.load_state(settings.garden_quests_path)
        if not quest_state_mod.is_today_row(state.today, now):
            return  # today's row hasn't been generated yet
        assert state.today is not None
        if not state.today.quests:
            return
        prev_done = sum(1 for q in state.today.quests if q.is_complete)
        mems = store.list_memories()
        captured_counts = vial_store.captured_count_by_memory()
        # Compute current intrinsic health for hit-95-health detection
        # (without quest_bonus to avoid the bonus-completes-itself loop).
        live = garden.compute_board_health(
            mems,
            now,
            captured_counts=captured_counts,
            clean_streak_d=state.clean_streak_d,
            quest_bonus=0,
        )
        quests_mod.evaluate_pending(
            state.today.quests,
            now=now,
            all_memories=mems,
            captured_counts=captured_counts,
            current_health=int(live["score"]),
        )
        now_done = sum(1 for q in state.today.quests if q.is_complete)
        if now_done > prev_done:
            quest_state_mod.save_state(state, settings.garden_quests_path)

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

    def _mirror_completion_to_source(memory_id: str, column: str) -> dict[str, Any]:
        """Best-effort write of completion state to the upstream task.

        v1 is **close-only**: when the user drags a card to ``closed``, we
        call ``sink.set_completion(task_id, True)`` on the upstream system
        (e.g. Outlook ``MarkComplete()``). Dragging OUT of ``closed`` does
        NOT reopen the task — the user reopens in Outlook, and the next
        sync flips the card back to ``memory`` via the existing
        completion-drift handling in ``pensieve.sync``. This is a deliberate
        safety cut to avoid a stray drag silently un-completing a real task.

        Returns ``{"mirrored": bool, "reason": str}`` so the dashboard can
        surface what happened. All failures are non-fatal at the HTTP layer
        (the local column move is already persisted to Chroma).
        """
        if not settings.mirror_completion:
            return {"mirrored": False, "reason": "disabled"}
        if column != "closed":
            return {"mirrored": False, "reason": "not-closing"}
        mem = store.get_memory(memory_id)
        if mem is None:
            return {"mirrored": False, "reason": "memory-missing"}
        sink: Optional[TaskSink] = get_sink_for_source(mem.source)
        if sink is None:
            return {"mirrored": False, "reason": f"no-sink-for-{mem.source}"}
        try:
            ok = sink.set_completion(mem.source_task_id, True)
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
        captured_counts = vial_store.captured_count_by_memory()
        any_vial_ids = vial_store.has_any_vial_by_memory()
        now = _now_utc()
        out = []
        for m in mems:
            d = m.to_dashboard_dict()
            _enrich_with_vials(d, m.id, captured_counts, any_vial_ids)
            _enrich_with_freshness(d, m, now, captured_counts)
            out.append(d)
        return {"count": len(mems), "memories": out}

    @app.get("/api/memories/{memory_id}")
    def get_memory(memory_id: str) -> dict[str, Any]:
        mem = store.get_memory(memory_id)
        if mem is None:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        captured_counts = vial_store.captured_count_by_memory()
        any_vial_ids = vial_store.has_any_vial_by_memory()
        d = mem.to_dashboard_dict()
        _enrich_with_vials(d, mem.id, captured_counts, any_vial_ids)
        _enrich_with_freshness(d, mem, _now_utc(), captured_counts)
        return d

    @app.get("/api/board/health")
    def board_health() -> dict[str, Any]:
        """Garden v1: single board-health score + per-term breakdown.

        Used by the masthead pill and the click-to-filter offenders view.
        Computed live from current memories + captured-vial counts.
        Garden v2 wires in ``clean_streak_d`` (from quest history) and
        ``quest_bonus`` (+5 when today's quests are all complete).
        """
        now = _now_utc()
        mems = store.list_memories()
        captured_counts = vial_store.captured_count_by_memory()
        state = _get_or_init_quest_state(now)
        # Auto-evaluate pending quests so the bonus reflects current state
        # even if a tend happened outside an /api/* tending endpoint.
        prev_done = (
            sum(1 for q in state.today.quests if q.is_complete) if state.today else 0
        )
        if state.today is not None and state.today.quests:
            prelim = garden.compute_board_health(
                mems,
                now,
                captured_counts=captured_counts,
                clean_streak_d=state.clean_streak_d,
                quest_bonus=0,
            )
            quests_mod.evaluate_pending(
                state.today.quests,
                now=now,
                all_memories=mems,
                captured_counts=captured_counts,
                current_health=int(prelim["score"]),
            )
            now_done = sum(1 for q in state.today.quests if q.is_complete)
            if now_done > prev_done:
                quest_state_mod.save_state(state, settings.garden_quests_path)
        bonus = quest_state_mod.quest_bonus_today(state)
        result = garden.compute_board_health(
            mems,
            now,
            captured_counts=captured_counts,
            clean_streak_d=state.clean_streak_d,
            quest_bonus=bonus,
        )
        result["tier"] = garden.board_health_tier(result["score"])
        return result

    @app.get("/api/quests")
    def list_quests() -> dict[str, Any]:
        """Garden v2: today's daily quests + clean-streak counter.

        Generates today's quests on first call of a new calendar day (UTC).
        Auto-evaluates pending completions on every call, so the response
        always reflects current store state. Returns an empty list when
        the board is in a state with no actionable quests (e.g. perfectly
        clean board with no recent closures).
        """
        now = _now_utc()
        state = _get_or_init_quest_state(now)
        # Re-evaluate pending quests against current store state.
        if state.today is not None and state.today.quests:
            mems = store.list_memories()
            captured_counts = vial_store.captured_count_by_memory()
            prev_done = sum(1 for q in state.today.quests if q.is_complete)
            prelim = garden.compute_board_health(
                mems,
                now,
                captured_counts=captured_counts,
                clean_streak_d=state.clean_streak_d,
                quest_bonus=0,
            )
            quests_mod.evaluate_pending(
                state.today.quests,
                now=now,
                all_memories=mems,
                captured_counts=captured_counts,
                current_health=int(prelim["score"]),
            )
            now_done = sum(1 for q in state.today.quests if q.is_complete)
            if now_done > prev_done:
                quest_state_mod.save_state(state, settings.garden_quests_path)

        today_dict: dict[str, Any] = {
            "date": state.today.date if state.today else None,
            "generated_at": (
                state.today.generated_at.astimezone(timezone.utc).isoformat()
                if state.today
                else None
            ),
            "quests": [q.to_dict() for q in (state.today.quests if state.today else [])],
        }
        return {
            "today": today_dict,
            "clean_streak_d": state.clean_streak_d,
            "all_done": (
                quests_mod.all_complete(state.today.quests)
                if state.today and state.today.quests
                else False
            ),
            "quest_bonus": quest_state_mod.quest_bonus_today(state),
        }

    # ----- Garden v3 helpers ------------------------------------------------

    def _evaluate_and_merge_achievements(
        now: datetime,
    ) -> tuple[achievement_state_mod.AchievementState, set[str]]:
        """Load achievement state, evaluate predicates, persist new unlocks.

        Returns ``(state, new_ids)`` so the API surface can render confetti
        triggers when ``new_ids`` is non-empty. Idempotent — repeated calls
        without any predicate flipping return ``(state, set())``.
        """
        mems = store.list_memories()
        vials = vial_store.list_vials()
        # Use the post-rollover quest_state so the clean-day history is current.
        q_state = _get_or_init_quest_state(now)
        # Use INTRINSIC health (no quest_bonus) to gate Sharpshooter — earning
        # a +5 quest bonus shouldn't shortcut the 95 threshold.
        captured_counts = vial_store.captured_count_by_memory()
        live = garden.compute_board_health(
            mems,
            now,
            captured_counts=captured_counts,
            clean_streak_d=q_state.clean_streak_d,
            quest_bonus=0,
        )
        should = achievements_mod.evaluate(
            mems, vials,
            current_health=int(live["score"]),
            history=q_state.history,
        )
        state = achievement_state_mod.load_state(settings.achievements_path)
        state, new_ids = achievement_state_mod.merge_unlocked(state, should, now)
        if new_ids:
            achievement_state_mod.save_state(state, settings.achievements_path)
        return state, new_ids

    @app.get("/api/achievements")
    def list_achievements() -> dict[str, Any]:
        """Garden v3: list all badges with locked / unlocked status.

        Auto-evaluates on every call (idempotent). When new unlocks land,
        the response includes ``new_unlocks`` so the frontend can fire its
        confetti micro-burst once. Subsequent calls return an empty
        ``new_unlocks`` list (the badges stay in ``unlocked``).
        """
        now = _now_utc()
        state, new_ids = _evaluate_and_merge_achievements(now)
        unlocked_by_id = {u.id: u for u in state.unlocked}
        out_defs = []
        for d in achievements_mod.definitions():
            entry = dict(d)
            u = unlocked_by_id.get(d["id"])
            entry["unlocked"] = u is not None
            entry["unlocked_at"] = (
                u.unlocked_at.astimezone(timezone.utc).isoformat() if u else None
            )
            out_defs.append(entry)
        unlocked_count = sum(1 for d in out_defs if d["unlocked"])
        return {
            "achievements": out_defs,
            "total": len(out_defs),
            "unlocked_count": unlocked_count,
            "new_unlocks": sorted(new_ids),
        }

    @app.get("/api/garden/level-summary")
    def level_summary() -> dict[str, Any]:
        """Garden v3: trailing-7-days roll-up.

        Designed for the Friday digest (Issue #3) to consume — exposed
        standalone here so the dashboard can also show a "this week"
        block. Returns counts + capture rate + week-over-week health
        delta + streak data. Reads day-snapshot history from
        :mod:`pensieve.quest_state`.
        """
        now = _now_utc()
        state = _get_or_init_quest_state(now)
        mems = store.list_memories()
        vials = vial_store.list_vials()
        return achievements_mod.build_level_summary(
            mems, vials, now=now, history=state.history
        )

    @app.patch("/api/memories/{memory_id}/column")
    def patch_column(memory_id: str, body: dict[str, str]) -> dict[str, Any]:
        col = (body or {}).get("column", "").strip()
        if col not in ("memory", "dive", "review", "closed"):
            raise HTTPException(status_code=400, detail=f"Invalid column: {col}")
        # Garden v1: combine column update + tended bump into ONE atomic-ish
        # metadata write so concurrent partials can't clobber each other.
        ok = store.update_meta(
            memory_id,
            {"column": col, "last_tended_at": _now_utc()},
        )
        if not ok:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        mirror_result = _mirror_column_to_source(memory_id, col)
        completion_mirror = _mirror_completion_to_source(memory_id, col)
        _maybe_complete_quests(memory_id)
        # Return the enriched memory so the frontend can update in place
        # (freshness dot must refresh, not just the board-health pill).
        mem = store.get_memory(memory_id)
        memory_dict = None
        if mem is not None:
            captured_counts = vial_store.captured_count_by_memory()
            any_vial_ids = vial_store.has_any_vial_by_memory()
            memory_dict = mem.to_dashboard_dict()
            _enrich_with_vials(memory_dict, mem.id, captured_counts, any_vial_ids)
            _enrich_with_freshness(memory_dict, mem, _now_utc(), captured_counts)
        return {
            "ok": True,
            "id": memory_id,
            "column": col,
            "mirror": mirror_result,
            "completion_mirror": completion_mirror,
            "memory": memory_dict,
        }

    @app.patch("/api/memories/{memory_id}")
    def patch_memory(memory_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Edit a Memory in place from the dashboard.

        Accepts any of: title, why, impact, suggested_strand, strand_kind,
        connect_goal_ids (list), connect_alignment_note, notes_for_user,
        column, needs_human_strand_review, due_date (date "YYYY-MM-DD",
        full ISO datetime, or null to clear).
        """
        mem = store.get_memory(memory_id)
        if mem is None:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        editable_str = {
            "title",
            "display_title",
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
        if "due_date" in body:
            raw_due = body["due_date"]
            if raw_due:
                from datetime import datetime as _dt
                from datetime import timezone as _tz

                try:
                    parsed = _dt.fromisoformat(str(raw_due).strip())
                except ValueError as e:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid due_date: {raw_due}"
                    ) from e
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=_tz.utc)
                mem.due_date = parsed
            else:
                mem.due_date = None
        if mem.column not in ("memory", "dive", "review", "closed"):
            raise HTTPException(status_code=400, detail=f"Invalid column: {mem.column}")
        # Garden v1: set tended timestamp BEFORE upsert (full upsert writes
        # the whole metadata blob, so a post-upsert bump would race with
        # the rewrite).
        mem.last_tended_at = _now_utc()
        store.upsert_memory(mem)
        _maybe_complete_quests(memory_id)
        mirror_result = None
        completion_mirror = None
        if "column" in body and body["column"] is not None:
            mirror_result = _mirror_column_to_source(memory_id, mem.column)
            completion_mirror = _mirror_completion_to_source(memory_id, mem.column)
        captured_counts = vial_store.captured_count_by_memory()
        any_vial_ids = vial_store.has_any_vial_by_memory()
        d = mem.to_dashboard_dict()
        _enrich_with_vials(d, mem.id, captured_counts, any_vial_ids)
        _enrich_with_freshness(d, mem, _now_utc(), captured_counts)
        return {
            "ok": True,
            "memory": d,
            "mirror": mirror_result,
            "completion_mirror": completion_mirror,
        }

    # ----- Vials (closure-capture records) -----

    @app.get("/api/vials")
    def list_all_vials() -> dict[str, Any]:
        vials = vial_store.list_vials()
        return {
            "count": len(vials),
            "vials": [v.to_dashboard_dict() for v in vials],
        }

    @app.get("/api/memories/{memory_id}/vials")
    def list_memory_vials(memory_id: str) -> dict[str, Any]:
        if store.get_memory(memory_id) is None:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        vials = vial_store.list_vials_for_memory(memory_id)
        return {
            "memory_id": memory_id,
            "count": len(vials),
            "vials": [v.to_dashboard_dict() for v in vials],
        }

    @app.post("/api/memories/{memory_id}/vials")
    def create_vial(memory_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Create a closure-capture Vial for a closed Memory.

        Body: {captured_text: str, capture_kind?: "captured" | "skipped"}
        Defaults capture_kind to "captured". Rejects with 409 unless the
        Memory is in the closed column. Rejects empty captured_text when
        capture_kind == "captured"; allows empty when "skipped".
        """
        mem = store.get_memory(memory_id)
        if mem is None:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        if mem.column != "closed":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Memory {memory_id} is in column '{mem.column}'; "
                    "closure capture is only allowed for closed memories"
                ),
            )
        body = body or {}
        kind = (body.get("capture_kind") or "captured").strip()
        if kind not in ("captured", "skipped"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid capture_kind: {kind!r} (allowed: 'captured', 'skipped')",
            )
        text = str(body.get("captured_text") or "").strip()
        if len(text) > 2000:
            raise HTTPException(
                status_code=400, detail="captured_text exceeds 2000 character limit"
            )
        if kind == "captured" and not text:
            raise HTTPException(
                status_code=400,
                detail=(
                    "captured_text is required when capture_kind == 'captured'; "
                    "use capture_kind == 'skipped' to dismiss the chevron without text"
                ),
            )
        vial = Vial.snapshot_from(mem, captured_text=text, capture_kind=kind)
        vial_store.upsert_vial(vial)
        # Garden v1: posting (or skipping) a Vial counts as deliberate
        # user care of the card. Bump independent of vial_store write so
        # we don't couple the two domains.
        store.bump_tended_at(memory_id, _now_utc())
        _maybe_complete_quests(memory_id)
        return {"ok": True, "vial": vial.to_dashboard_dict()}

    @app.delete("/api/vials/{vial_id}")
    def delete_vial(vial_id: str) -> dict[str, Any]:
        existing = vial_store.get_vial(vial_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Vial {vial_id} not found")
        vial_store.delete_vial(vial_id)
        return {"ok": True, "id": vial_id}

    @app.get("/api/search")
    def search(q: str = Query(..., min_length=1), top_k: int = 12) -> dict[str, Any]:
        results = store.search(q, top_k=top_k)
        captured_counts = vial_store.captured_count_by_memory()
        any_vial_ids = vial_store.has_any_vial_by_memory()
        now = _now_utc()
        out = []
        for m in results:
            d = m.to_dashboard_dict()
            _enrich_with_vials(d, m.id, captured_counts, any_vial_ids)
            _enrich_with_freshness(d, m, now, captured_counts)
            out.append(d)
        return {"query": q, "count": len(results), "memories": out}

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

        # Atomic write: tmp file + replace, so a crash mid-write can never
        # leave an empty or half-JSON goals catalog (which would silently
        # zero Connect alignment on every future enrichment).
        path = settings.connect_goals_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)

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

        src_name = (body.get("source") or settings.default_source or "outlook_com").strip()
        lists_raw = body.get("lists") or []
        if isinstance(lists_raw, str):
            lists_raw = [lists_raw]
        list_names: list[str] = [str(x).strip() for x in lists_raw if str(x).strip()]
        force = bool(body.get("force", False))

        t = start_sync_job(
            settings=settings,
            tracker=tracker,
            src_name=src_name,
            list_names=list_names,
            force=force,
        )
        if t is None:
            return {
                "ok": False,
                "already_running": True,
                "state": tracker.snapshot(),
            }
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
        # Garden v1: regenerate is a deliberate user-initiated tend.
        # Set BEFORE upsert (full-blob write would race with a post-bump).
        merged.last_tended_at = _now_utc()
        store.upsert_memory(merged)
        _maybe_complete_quests(memory_id)
        captured_counts = vial_store.captured_count_by_memory()
        any_vial_ids = vial_store.has_any_vial_by_memory()
        d = merged.to_dashboard_dict()
        _enrich_with_vials(d, merged.id, captured_counts, any_vial_ids)
        _enrich_with_freshness(d, merged, _now_utc(), captured_counts)
        return {
            "ok": True,
            "tokens_used": result.tokens_used,
            "memory": d,
        }

    @app.post("/api/recap")
    def generate_recap_route(body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Draft a Microsoft Connect-format recap from enriched memories.

        Body (all optional):
          scope:        "all" | "completed" | "review" (default "all")
          goal_ids:     list[str] to restrict to specific Connect goals
          list_names:   list[str] to restrict to specific source list names
                        (e.g. ["CISO GRC"]). Omit to use the configured
                        default (PENSIEVE_RECAP_LIST_NAMES, default
                        "CISO GRC"). Pass [] to disable the list filter.
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
        list_names_raw = body.get("list_names", None)
        list_names = (
            [str(n) for n in list_names_raw if str(n).strip()]
            if isinstance(list_names_raw, list)
            else None
        )
        period_label = str(body.get("period_label") or "").strip()

        memories = store.list_memories()
        try:
            recap = generate_recap(
                memories,
                scope=scope,
                goal_ids=goal_ids,
                list_names=list_names,
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
        list_names_raw = body.get("list_names", None)
        list_names = (
            [str(n) for n in list_names_raw if str(n).strip()]
            if isinstance(list_names_raw, list)
            else None
        )
        if not goal_id:
            raise HTTPException(status_code=400, detail="goal_id is required")
        if not feedback:
            raise HTTPException(status_code=400, detail="feedback is required")
        memories = store.list_memories()
        try:
            section = revise_recap_section(
                memories,
                goal_id,
                feedback,
                scope=scope,
                list_names=list_names,
                settings=settings,
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
