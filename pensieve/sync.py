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
from pensieve.store import ChromaMemoryStore, Memory


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


def _audit_write(entry: dict) -> None:
    s = get_settings()
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with s.audit_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _build_memory(task: RawTask, result) -> Memory:
    return Memory(
        id=task.id,
        source=task.source,
        source_task_id=task.id,
        list_name=task.list_name,
        title=task.title,
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
        source_created_at=task.created_at,
        source_last_modified=task.last_modification_time,
        completed=task.completed,
        completed_at=task.completed_at,
        due_date=task.due_date,
        categories=task.categories,
        tokens_used=result.tokens_used,
        enriched_at=datetime.now(timezone.utc),
    )


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

    # Decide which tasks need re-enrichment
    to_enrich: list[tuple[RawTask, str]] = []  # (task, change_reason)
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
        if t.last_modification_time and existing.source_last_modified:
            try:
                if t.last_modification_time > existing.source_last_modified:
                    to_enrich.append((t, "modified"))
                    continue
            except Exception:
                pass
        stats.skipped_unchanged += 1

    if not to_enrich:
        console.print("[green]All tasks already enriched and unchanged.[/green]")
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
        f"review={stats.review_queue}, failed={stats.failed}, tokens={stats.tokens_used}"
    )
    return stats
