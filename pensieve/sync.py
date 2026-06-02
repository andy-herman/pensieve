"""End-to-end sync orchestrator: read tasks → enrich new/changed → upsert to Chroma."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console

from pensieve.config import get_settings
from pensieve.enrichment import (
    AzureOpenAIChatClient,
    enrich_task,
    load_connect_goals,
)
from pensieve.sources.base import RawTask, TaskSource
from pensieve.sources.sample_file import SampleFileSource
from pensieve.sources.sink import extract_pensieve_column
from pensieve.store import ChromaMemoryStore, Memory

_VALID_COLUMNS = frozenset({"memory", "dive", "review", "closed"})


def _column_from_task(task: RawTask, prefix: str) -> Optional[str]:
    """Return the kanban column encoded on the source task, or None.

    Reads the Pensieve column tag the writer placed on the upstream task
    so a second PC syncing for the first time picks up the mirrored view.
    Unknown column values are ignored so a corrupted tag does not stamp
    junk into the kanban.
    """
    col = extract_pensieve_column(task.categories or [], prefix=prefix)
    if col and col in _VALID_COLUMNS:
        return col
    return None


@dataclass
class SyncStats:
    total_tasks: int = 0
    new_enriched: int = 0
    updated_enriched: int = 0
    skipped_unchanged: int = 0
    skipped_dry_run: int = 0
    failed: int = 0
    review_queue: int = 0
    tokens_used: int = 0
    deleted: int = 0


def _audit_write(entry: dict) -> None:
    s = get_settings()
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with s.audit_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _build_memory(task: RawTask, result) -> Memory:
    # New tasks that arrive already-completed land directly in the Closed column.
    settings = get_settings()
    mirrored = _column_from_task(task, settings.mirror_tag_prefix)
    if mirrored is not None:
        initial_column = mirrored
    elif task.completed:
        initial_column = "closed"
    else:
        initial_column = "memory"
    return Memory(
        id=task.id,
        source=task.source,
        source_task_id=task.id,
        list_name=task.list_name,
        title=task.title,
        display_title=(result.display_title or None),
        original_notes=task.notes,
        suggested_strand=result.suggested_strand,
        strand_kind=result.strand_kind,
        needs_human_strand_review=result.needs_human_strand_review,
        why=result.why,
        impact=result.impact,
        confidence_strand=result.confidence_strand,
        confidence_impact=result.confidence_impact,
        connect_goal_ids=result.connect_goal_ids,
        connect_alignment_confidence=result.connect_alignment_confidence,
        connect_alignment_note=result.connect_alignment_note,
        notes_for_user=result.notes_for_user,
        column=initial_column,
        source_created_at=task.created_at,
        source_last_modified=task.last_modification_time,
        completed=task.completed,
        completed_at=task.completed_at,
        due_date=task.due_date,
        categories=task.categories,
        tokens_used=result.tokens_used,
        enriched_at=datetime.now(timezone.utc),
    )


def overlay_regeneration(existing: Memory, task: RawTask, result) -> Memory:
    """Merge a fresh enrichment + source snapshot onto an existing Memory.

    Regenerates: title, original_notes, list_name, source dates, completion,
    due, categories, plus all enrichment outputs (why/impact/strand/connect/etc.).
    PRESERVES user-only fields: column (lifecycle placement) and notes_for_user
    (private note). This is what makes 'edit title in To-Do then refresh' safe:
    your dragged column and private notes survive re-enrichment.

    EXCEPTION: when the source task is completed and the user has not already
    moved it to a terminal column (vial / closed), auto-promote to "closed"
    so the kanban reflects the source's completion state.
    """
    existing.title = task.title
    if result.display_title:
        existing.display_title = result.display_title
    existing.original_notes = task.notes
    if task.list_name:
        existing.list_name = task.list_name
    existing.source_created_at = task.created_at or existing.source_created_at
    existing.source_last_modified = task.last_modification_time or existing.source_last_modified
    existing.completed = task.completed
    existing.completed_at = task.completed_at
    existing.due_date = task.due_date
    existing.categories = list(task.categories or [])
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
    # PRESERVED on purpose: existing.column, existing.notes_for_user
    # Mirror tag override (Phase 2 TaskSink writeback). When the source carries
    # a `pensieve/col:<col>` tag whose value differs from the local column AND
    # the source was modified after we last enriched this memory, the other PC
    # is the newer writer; honor its view. This is the "source-wins-on-newer"
    # conflict policy Andy confirmed on 2026-06-02. Runs BEFORE the completion
    # promotion below so a hard "task completed at source" signal still wins.
    settings = get_settings()
    mirrored = _column_from_task(task, settings.mirror_tag_prefix)
    if (
        mirrored is not None
        and mirrored != existing.column
        and task.last_modification_time is not None
        and existing.enriched_at is not None
        and task.last_modification_time > existing.enriched_at
    ):
        existing.column = mirrored
    # Completion is terminal: if the source completed the task, force closed
    # regardless of where the user (local or remote) wanted the card to live.
    # Closed is the only terminal column now; Review = needs attention, Closed
    # = done. The user can manually drag back if they really want.
    if task.completed and existing.column != "closed":
        existing.column = "closed"
    existing.tokens_used = (existing.tokens_used or 0) + (result.tokens_used or 0)
    existing.enriched_at = datetime.now(timezone.utc)
    return existing


def run_sync(
    source: TaskSource,
    *,
    strand_catalog: Optional[list[dict]] = None,
    recent_context: Optional[dict] = None,
    dry_run: bool = False,
    force: bool = False,
    console: Optional[Console] = None,
) -> SyncStats:
    """Pull tasks, enrich new/changed ones, upsert to Chroma."""
    settings = get_settings()
    console = console or Console()
    stats = SyncStats()

    # Strand catalog + recent context are mandatory for enrichment. If the source
    # itself provides them (SampleFileSource does), prefer that; otherwise the
    # caller must supply.
    if strand_catalog is None and isinstance(source, SampleFileSource):
        strand_catalog = source.strand_catalog
    if recent_context is None and isinstance(source, SampleFileSource):
        recent_context = source.recent_context
    if strand_catalog is None:
        raise ValueError("strand_catalog is required for enrichment")
    if recent_context is None:
        recent_context = {"user_recent_strands": [], "recent_titles_in_same_list": []}

    store = ChromaMemoryStore(settings)
    client = AzureOpenAIChatClient(settings) if not dry_run else None
    connect_goals = load_connect_goals()

    known_ids = store.known_ids()
    tasks = list(source.list_tasks())
    stats.total_tasks = len(tasks)
    console.print(
        f"[cyan]Source[/cyan] {source.name}: {stats.total_tasks} tasks. "
        f"Chroma has {len(known_ids)} memories already."
    )

    # Deletion sweep: any memory we previously ingested from this source
    # whose id is NOT in the live pull (and is in a list we just covered)
    # has been deleted at the source. Honour that and remove from Chroma.
    # Scoping to ``covered_lists`` is critical when the user filters to
    # specific lists (Outlook ``list_names``) — without it, a narrow sync
    # would erase memories from lists we didn't even read.
    live_ids = {t.id for t in tasks}
    covered = source.covered_lists()
    orphans = store.find_orphan_ids(source.name, live_ids, covered_lists=covered)
    for mid, title, list_name in orphans:
        if dry_run:
            console.print(
                f"  [DRY] [magenta]DELETE[/magenta] {title} "
                f"[dim](from list '{list_name}', source removed it)[/dim]"
            )
            continue
        store.delete_memory(mid)
        stats.deleted += 1
        console.print(
            f"  [magenta]DELETE[/magenta] {title} [dim](from list '{list_name}', source removed it)[/dim]"
        )
        _audit_write(
            {
                "mode": "sync",
                "task_id": mid,
                "source": source.name,
                "reason": "deleted-at-source",
                "list_name": list_name,
                "title": title,
            }
        )

    # Decide which tasks need re-enrichment (or just a column-only nudge for
    # completion drift, which doesn't require an LLM call).
    to_enrich: list[tuple[RawTask, str]] = []  # (task, change_reason)
    column_only_updates: list[RawTask] = []
    for t in tasks:
        if force:
            to_enrich.append((t, "force"))
            continue
        if t.id not in known_ids:
            to_enrich.append((t, "new"))
            continue
        existing = store.get_memory(t.id)
        if existing is None:
            to_enrich.append((t, "missing"))
            continue
        # Title or notes edited in the source → full re-enrich so why/impact/
        # strand reflect the new wording. (Outlook doesn't always bump
        # LastModificationTime on every edit, so compare contents directly.)
        if (t.title or "").strip() != (existing.title or "").strip():
            to_enrich.append((t, "title-changed"))
            continue
        if (t.notes or "").strip() != (existing.original_notes or "").strip():
            to_enrich.append((t, "notes-changed"))
            continue
        if t.last_modification_time and existing.source_last_modified:
            try:
                if t.last_modification_time > existing.source_last_modified:
                    to_enrich.append((t, "modified"))
                    continue
            except Exception:
                pass
        # Completion drift: source marked it done but our kanban hasn't caught
        # up. Cheap column-only update, no LLM call.
        if t.completed and existing.column != "closed":
            column_only_updates.append(t)
            continue
        stats.skipped_unchanged += 1

    # Apply column-only updates immediately (no LLM, no concurrency needed).
    for t in column_only_updates:
        mem = store.get_memory(t.id)
        if mem is None:
            continue
        mem.completed = True
        mem.completed_at = t.completed_at or mem.completed_at
        mem.column = "closed"
        store.upsert_memory(mem)
        stats.updated_enriched += 1
        console.print(
            f"  [green]CLOSE [/green] (auto-close) {mem.title} "
            f"[dim](source marked complete; no re-enrich needed)[/dim]"
        )
        _audit_write(
            {
                "mode": "sync",
                "task_id": t.id,
                "source": source.name,
                "reason": "auto-close",
                "column": "closed",
            }
        )

    if not to_enrich:
        console.print(
            f"[green]All tasks already enriched and unchanged.[/green] "
            f"[dim]({len(column_only_updates)} auto-closed, "
            f"{stats.deleted} deleted, "
            f"{stats.skipped_unchanged} unchanged)[/dim]"
        )
        return stats

    console.print(
        f"[yellow]{len(to_enrich)}[/yellow] task(s) need enrichment "
        f"([dim]{stats.skipped_unchanged} unchanged[/dim])."
    )

    if dry_run:
        for t, reason in to_enrich:
            console.print(f"  [DRY] {reason:8} {t.title}")
        stats.skipped_dry_run = len(to_enrich)
        return stats

    # Run enrichment with bounded concurrency
    def _do(task_reason: tuple[RawTask, str]) -> tuple[RawTask, str, Optional[Memory], Optional[str]]:
        task, reason = task_reason
        try:
            result = enrich_task(
                task,
                strand_catalog=strand_catalog,
                recent_context=recent_context,
                client=client,
                connect_goals=connect_goals,
            )
            if reason in ("force", "modified", "title-changed", "notes-changed"):
                existing = store.get_memory(task.id)
                if existing is not None:
                    mem = overlay_regeneration(existing, task, result)
                else:
                    mem = _build_memory(task, result)
            else:
                mem = _build_memory(task, result)
            return task, reason, mem, None
        except Exception as e:
            return task, reason, None, str(e)

    with ThreadPoolExecutor(max_workers=settings.enrichment_concurrency) as ex:
        futures = [ex.submit(_do, tr) for tr in to_enrich]
        for fut in as_completed(futures):
            task, reason, mem, err = fut.result()
            if err is not None or mem is None:
                stats.failed += 1
                console.print(f"  [red][FAIL][/red] {task.title}: {err}")
                _audit_write({"mode": "sync", "task_id": task.id, "error": err, "source": source.name})
                continue

            store.upsert_memory(mem)
            stats.tokens_used += mem.tokens_used
            if reason == "new":
                stats.new_enriched += 1
            else:
                stats.updated_enriched += 1
            needs_review = (
                mem.needs_human_strand_review
                or mem.confidence_strand < settings.enrichment_confidence_threshold
                or mem.confidence_impact < settings.enrichment_confidence_threshold
            )
            if needs_review:
                stats.review_queue += 1
                marker = "[yellow]REVIEW[/yellow]"
            else:
                marker = "[green]OK    [/green]"
            console.print(
                f"  {marker} ({reason:8}) {mem.title} "
                f"[dim]s={mem.confidence_strand:.2f} i={mem.confidence_impact:.2f} "
                f"a={mem.connect_alignment_confidence:.2f}[/dim]"
            )
            _audit_write(
                {
                    "mode": "sync",
                    "task_id": task.id,
                    "source": source.name,
                    "reason": reason,
                    "tokens": mem.tokens_used,
                    "memory_id": mem.id,
                }
            )

    console.print(
        f"\n[cyan]Done.[/cyan] new={stats.new_enriched}, "
        f"updated={stats.updated_enriched}, unchanged={stats.skipped_unchanged}, "
        f"deleted={stats.deleted}, review={stats.review_queue}, "
        f"failed={stats.failed}, tokens={stats.tokens_used}"
    )
    return stats
