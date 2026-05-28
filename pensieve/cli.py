"""Pensieve CLI — typer entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from pensieve.config import get_settings
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.store import ChromaMemoryStore
from pensieve.sync import run_sync

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _build_source(name: str, list_name: Optional[str] = None):
    settings = get_settings()
    if name == "sample_file":
        from pensieve.sources.sample_file import SampleFileSource
        return SampleFileSource(settings.samples_path)
    if name == "outlook_com":
        from pensieve.sources.outlook_com import OutlookCOMSource
        return OutlookCOMSource(
            list_name=list_name or settings.default_list_name,
            skip_completed_older_than_days=settings.outlook_skip_completed_older_than_days,
        )
    raise typer.BadParameter(f"Unknown source: {name}. Use 'sample_file' or 'outlook_com'.")


def _build_recent_context_from_chroma() -> dict:
    """Compose recent_context from Chroma when not using a sample source."""
    store = ChromaMemoryStore()
    mems = store.list_memories()
    # most-recent first by enriched_at
    mems.sort(key=lambda m: m.enriched_at or "", reverse=True)
    recent_strands: list[str] = []
    recent_titles: list[str] = []
    seen_strands: set[str] = set()
    for m in mems[:30]:
        if m.suggested_strand and m.suggested_strand not in seen_strands:
            seen_strands.add(m.suggested_strand)
            recent_strands.append(m.suggested_strand)
        if len(recent_titles) < 8:
            recent_titles.append(m.title)
    return {
        "user_recent_strands": recent_strands[:10],
        "recent_titles_in_same_list": recent_titles,
    }


@app.command()
def init() -> None:
    """Verify config and prep the data dir."""
    s = get_settings()
    s.ensure_dirs()
    console.print("[cyan]Pensieve init[/cyan]")
    console.print(f"  data_dir   = {s.data_dir}")
    console.print(f"  chroma_dir = {s.chroma_dir}")
    console.print(f"  endpoint   = {s.azure_openai_endpoint or '[red]not set[/red]'}")
    console.print(f"  deployment = {s.azure_openai_deployment}")
    console.print(f"  goals file = {s.connect_goals_path} ({'OK' if s.connect_goals_path.exists() else 'missing'})")
    console.print(f"  samples    = {s.samples_path} ({'OK' if s.samples_path.exists() else 'missing'})")
    store = ChromaMemoryStore(s)
    console.print(f"  chroma     = {store.count()} memories currently")


@app.command()
def sync(
    source: str = typer.Option(None, "--source", "-s", help="sample_file | outlook_com (default from .env)"),
    list_name: Optional[str] = typer.Option(None, "--list", help="Outlook tasks folder name (default: Tasks)"),
    strand_catalog_path: Optional[Path] = typer.Option(
        None, "--strand-catalog", help="JSON file containing strand_catalog + recent_context (for outlook_com source)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be enriched without calling LLM"),
    force: bool = typer.Option(False, "--force", help="Re-enrich every task even if unchanged"),
) -> None:
    """Pull tasks from source, enrich, upsert to Chroma."""
    settings = get_settings()
    src_name = source or settings.default_source
    src = _build_source(src_name, list_name=list_name)
    console.print(f"[bold]Pensieve sync[/bold] source={src_name} dry_run={dry_run} force={force}")

    strand_catalog = None
    recent_context = None
    if strand_catalog_path:
        import json
        with strand_catalog_path.open("r", encoding="utf-8") as f:
            blob = json.load(f)
        strand_catalog = blob.get("strand_catalog")
        recent_context = blob.get("recent_context")
    elif src_name == "outlook_com":
        # Pull strand_catalog from samples.json (acts as the catalog of record),
        # and synthesize recent_context from prior Chroma state.
        if settings.samples_path.exists():
            import json
            with settings.samples_path.open("r", encoding="utf-8") as f:
                blob = json.load(f)
            strand_catalog = blob.get("strand_catalog")
        recent_context = _build_recent_context_from_chroma()

    stats = run_sync(
        src,
        strand_catalog=strand_catalog,
        recent_context=recent_context,
        dry_run=dry_run,
        force=force,
        console=console,
    )
    if stats.failed > 0:
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Print Chroma + config status."""
    s = get_settings()
    store = ChromaMemoryStore(s)
    mems = store.list_memories()
    console.print(f"[cyan]Pensieve status[/cyan]  memories={len(mems)}")
    by_col: dict[str, int] = {}
    by_strand: dict[str, int] = {}
    review = 0
    for m in mems:
        by_col[m.column] = by_col.get(m.column, 0) + 1
        by_strand[m.suggested_strand or "<none>"] = by_strand.get(m.suggested_strand or "<none>", 0) + 1
        if m.needs_human_strand_review or m.confidence_strand < s.enrichment_confidence_threshold:
            review += 1
    t = Table(title="By column", show_header=True)
    t.add_column("column"); t.add_column("count", justify="right")
    for col in ("memory", "dive", "reverie", "reflection", "vial"):
        t.add_row(col, str(by_col.get(col, 0)))
    console.print(t)
    t2 = Table(title="By strand", show_header=True)
    t2.add_column("strand"); t2.add_column("count", justify="right")
    for k, v in sorted(by_strand.items(), key=lambda x: -x[1]):
        t2.add_row(k, str(v))
    console.print(t2)
    console.print(f"review_queue = {review}")


@app.command()
def search(query: str, top_k: int = typer.Option(8, "--top-k", "-k")) -> None:
    """Semantic search the Chroma memories."""
    store = ChromaMemoryStore()
    results = store.search(query, top_k=top_k)
    if not results:
        console.print("[dim]No matches.[/dim]")
        return
    for m in results:
        console.print(f"[bold]{m.title}[/bold] [dim]({m.suggested_strand or '-'})[/dim]")
        if m.why:
            console.print(f"  why:    {m.why}")
        if m.impact:
            console.print(f"  impact: {m.impact}")
        console.print()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: Optional[int] = typer.Option(None, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Start the local FastAPI server."""
    s = get_settings()
    bind_port = port or s.backend_port
    console.print(f"[cyan]Pensieve serve[/cyan] http://{host}:{bind_port}")
    uvicorn.run(
        "pensieve.api.server:app",
        host=host,
        port=bind_port,
        reload=reload,
        log_level="info",
    )


@app.command()
def goals() -> None:
    """Print the loaded Connect goals."""
    gs = load_connect_goals()
    if not gs:
        console.print("[yellow]No Connect goals loaded.[/yellow]")
        return
    for g in gs:
        console.print(f"  #{g.get('number')} {g.get('short_name')} ({g.get('house')}) - {g.get('id')}")


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(main())
