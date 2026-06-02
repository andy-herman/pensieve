"""One-shot back-fill: write `<prefix><column>` to every existing memory's source task.

Use this once on each PC after you first turn on mirror mode, so the second PC
lands every card in the right column on its first sync instead of resetting to
"memory". After this, normal API drag-drops keep the tag in sync on every move.

Run from the repo root:

    python scripts/backfill_mirror_tags.py [--dry-run] [--prefix pensieve/col:]

Default is NOT dry-run. The script writes one tag per outlook_com memory; if a
task already carries the same tag (Pensieve set it on a prior drag) the sink
short-circuits without calling Save(). Memories whose source is not outlook_com
are skipped (sample_file / future sources have no writer wired).

Requires Outlook desktop running on this PC (the sink uses pywin32 Dispatch).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from pensieve.config import get_settings
from pensieve.sources.outlook_com_sink import get_sink_for_source
from pensieve.store.chroma import ChromaMemoryStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be written; do not call .Save() on any Outlook item.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Override the mirror tag prefix (defaults to PENSIEVE_MIRROR_TAG_PREFIX).",
    )
    args = parser.parse_args()

    settings = get_settings()
    prefix = args.prefix or settings.mirror_tag_prefix
    store = ChromaMemoryStore(settings)
    memories = store.list_memories()
    outlook_memories = [m for m in memories if m.source == "outlook_com"]

    print(f"Total memories: {len(memories)}")
    print(f"Outlook tasks to tag: {len(outlook_memories)}")
    print(f"Tag prefix: {prefix!r}")
    print(f"Mode: {'DRY RUN (no writes)' if args.dry_run else 'LIVE (writes Save())'}")
    print()

    if not outlook_memories:
        print("Nothing to do.")
        return 0

    sink = None
    if not args.dry_run:
        sink = get_sink_for_source("outlook_com")
        if sink is None:
            print("ERROR: no sink wired for outlook_com.", file=sys.stderr)
            return 2

    results: Counter[str] = Counter()
    by_column: Counter[str] = Counter()
    failures: list[tuple[str, str]] = []

    for mem in outlook_memories:
        by_column[mem.column] += 1
        label = f"{mem.column:>6} | {mem.title[:60]}"
        if args.dry_run:
            print(f"  would tag: {label}")
            results["dry_run"] += 1
            continue
        try:
            ok = sink.set_column_tag(mem.source_task_id, mem.column, prefix=prefix)
        except Exception as e:  # noqa: BLE001  one-shot script, surface every error
            print(f"  FAIL ({type(e).__name__}): {label}")
            failures.append((mem.source_task_id, f"{type(e).__name__}: {e}"))
            results["error"] += 1
            continue
        if ok:
            print(f"  tagged   : {label}")
            results["written"] += 1
        else:
            print(f"  MISSING  : {label}  (task id not found in Outlook)")
            results["missing"] += 1

    print()
    print("Summary by column:", dict(by_column))
    print("Summary by outcome:", dict(results))
    if failures:
        print()
        print("Failures:")
        for tid, err in failures:
            print(f"  {tid[:24]}... -> {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
