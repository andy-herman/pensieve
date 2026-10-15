---
title: 3-Agent Pensieve Review (2026-06-04) — Findings, Top-5 Roadmap, Vial v1 Design
date: 2026-06-04
status: active
phase: 2-kickoff
related_commits:
  - fac0236  # review-driven quick wins (shipped)
---

# 3-Agent Pensieve Review — Findings, Roadmap, Vial v1 Design

Three sub-agents reviewed Pensieve in parallel on 2026-06-04 across three axes:
architecture / code-quality, dashboard UX, and product strategy. This file
synthesizes the findings, the ranked next features, and the v1 design for
the #1 missing surface: **closure capture (Vial v1)**.

Full reports live in the session workspace (not committed) at
`~/.copilot/session-state/4bc670e8-128c-4d50-8c24-249bfa5b86fb/files/`:

- `pensieve-review-2026-06-04-arch.md` (architecture, 10268 chars)
- `pensieve-review-2026-06-04-ux.md` (UX, 14215 chars)
- `pensieve-review-2026-06-04-strategy.md` (strategy, 16319 chars)

## TL;DR

Pensieve is **80% done with Phase 1** and the right scaffolding is in place.
The single most important gap is that closure context is never captured —
when a task closes, Pensieve auto-routes it to the closed column with zero
LLM tokens and zero prompt to the user. The `Vial` Pydantic stub at
`pensieve/store/schema.py:121` is the unbuilt surface that exists to capture
"what changed when this closed." Everything else in Phase 2 is downstream
of this.

The 6 review-driven quick wins shipped in commit `fac0236` (atomic JSON write,
review-badge click-to-filter, card-title focus on open, due-date pills + title
clamp, sync_state cleanup, chromadb version pin). Tests 117/117 green.

## What the agents converged on

| Finding | Arch | UX | Strategy |
|---|---|---|---|
| **Closure capture / Vial v1 is the #1 unmet need** | ✓ (dead model) | ✓ (no closure surface) | ✓ (mission-critical) |
| No TestClient tests for any `server.py` route | ✓ | — | implicit |
| `connect-goals.json` write is non-atomic | ✓ | — | — |
| Card titles get clipped, no due-date visibility | — | ✓ | — |
| Review-badge is dead-end (count but no filter) | — | ✓ | — |
| Reverie should be deferred until Vials exist | implicit | implicit | ✓ |
| Don't build the graph view past read-only stub | — | — | ✓ |

## Quick wins shipped (commit `fac0236`)

| # | Finding | Fix |
|---|---|---|
| Q1 | Non-atomic `connect-goals.json` write | tmp + fsync + os.replace |
| Q2 | Review badge shows count but doesn't filter | click toggles filter, amber outline when active |
| Q3 | Modal opens but doesn't focus title field | `setTimeout(focus + select, 0)` after unhide |
| Q4 | Card titles clipped, no due-date visibility | 2-line clamp + overflow-wrap + due-date pill (`overdue` / `soon` / `later`) |
| Q5 | Dead `SyncJobTracker.begin()` back-compat wrapper | deleted (no callers) |
| Q6 | `chromadb` version unpinned (next major breaks our API surface) | `>=0.5.0,<0.7.0` |

All 6 verified via `pytest -q` (117/117 pass) and `ruff check pensieve/` (clean).

## Top 5 strategic features (ranked by mission alignment)

Pensieve's two stated missions:

1. **Promo / IC-3 evidence trail** — capture and preserve what shifted
2. **Daily strategic focus** — make today's surface less noisy

Ranked features, with mission impact and effort:

### 1. Closure capture / Vial v1 (M effort) — both missions

The killer gap. Pensieve enriches at creation, goes silent at closure. The
"what changed / what did I learn / what shifted" context that makes a
memory promo-worthy is nowhere captured. The `Vial` stub exists for exactly
this purpose. Design spec below.

**Status:** designing now (rubber-duck'd 2026-06-04), implementation v1 MVP this session.

### 2. IC behaviors as first-class enrichment fields (S effort) — promo mission

`data/connect-goals.json:80-83` already names the four IC-3 behaviors
("Drive Clarity", "Generate Energy", "Deliver Success", "Grow Yourself").
Today the enrichment prompt sees them in the goal blocks but doesn't emit
`connect_behaviors: [...]` per-Memory. Add the field + emit in prompt +
surface in card meta. Forward-compat: Vials should also carry
`connect_behaviors_snapshot`.

### 3. Friday auto-digest (S effort) — both missions

`AutoSyncScheduler` already exists in `pensieve/scheduler.py`. Add a Friday
4pm timer that runs `recap.py` against the last 5 business days,
auto-exports to `data/recaps/auto/YYYY-MM-DD_friday.md`, and shows a small
"📜 Friday recap ready" toast in the HUD on next open. Zero new user action
required.

### 4. Strand-health panel (S/M effort) — daily mission

New `/api/insights` endpoint computing per-strand: count this week vs last,
% closed without Vial (gap signal), and "stagnant" memories (created > 14d
ago, column == "memory", no edits). Render as a small right-side panel in
the HUD. Tells Andy at a glance which strands are getting starved.

### 5. Merge `personal-device` branch behind provider flag (M effort) — pilot user mission

Per the strategy review, pilot user #2 is blocked on a single-machine
assumption. The `personal-device` work needs to land behind a
`PENSIEVE_SOURCE_PROVIDER` flag (default = outlook_com, allow = sample,
outlook_com, future = ms_graph) so a pilot user can wire in their own
source without forking. Mostly docs + a small refactor in `sources/__init__.py`.

## Architecture follow-ups (not strategic, but real)

1. **No TestClient tests for `server.py`** — the biggest risk surface in the
   codebase has zero contract tests. Vial v1 is a natural place to add the
   first `TestClient` scaffolding (it's testing new endpoints anyway).
2. **`sync.py:enrich_loop` is 200+ lines** — one big function doing source
   read, store diff, LLM call, store write, audit. Extract a `PlanRow` dataclass
   per task (new / changed / column-only / unchanged / orphan) and process
   each row through a uniform pipeline. Defer until after Vial v1.
3. **`prompts/*.md` are loaded ad-hoc** — small `prompts.py` loader with
   string-template substitution would be cleaner. Defer.
4. **`Memory.to_chroma_metadata()` is hand-coded** — for Vial v1 we'll follow
   the same pattern; consider a small mixin later.

## Don't-build commitments

These came up in the strategy review and are explicitly NOT roadmap:

- **No Reverie column until Vials exist.** The original 7-column model
  (memory / dive / vial / reverie / reflection / closed) was already
  collapsed to 4 (memory / dive / review / closed) in the 2026-05-28
  lifecycle simplification. Reverie was the "this might come back" lane;
  it adds zero value without closure context to compare against.
- **No graph expansion past the current stub.** The graph view is a fun
  artifact, not a daily-use surface. Don't invest UI polish.
- **No multi-tenant abstractions.** Pensieve is single-user local-only by
  design. Don't add user_id columns "for future". The carve-out for
  pilot user #2 (item #5 above) is provider-pluggability, not tenancy.
- **No real-time websockets.** The 120s auto-poll is fine. Don't add a
  socket layer that needs reconnect logic for one user on localhost.
- **No Microsoft Graph in the runtime.** Carve-out is documented in
  AGENTS.md and the README; this is a hard constraint, not a deferral.

## Vial v1 Design (the next big ship)

### The problem in one sentence

A Memory closes today with **zero** record of why or how it landed — by Friday
the context evaporates, and by promo season the only artifact is a title.

### The shape

`Vial` is a durable closure-capture record attached to a Memory. It outlives
its parent: even if the upstream To-Do task is later deleted (orphan sweep),
the Vial remains as promo evidence. Vials are deliberately scoped narrow in
v1 — one short user-typed note ("what changed when this closed") plus a
frozen snapshot of the closure-time Memory context.

### Schema extensions (`pensieve/store/schema.py`)

Replace the existing `Vial` stub with:

```python
class Vial(BaseModel):
    id: str                            # "vial_" + uuid.uuid4().hex
    memory_id: str                     # FK reference; may outlive its Memory
    captured_at: datetime
    capture_kind: Literal["captured", "skipped"] = "captured"
    captured_text: str = ""            # required if capture_kind=="captured"
    polished_text: str = ""            # reserved for v1.1 AI polish
    # Closure-time snapshots (frozen; do not follow Memory edits)
    title_snapshot: str = ""
    display_title_snapshot: str = ""
    why_snapshot: str = ""
    impact_snapshot: str = ""
    connect_alignment_note_snapshot: str = ""
    connect_goal_ids_snapshot: list[str] = []
    suggested_strand_snapshot: Optional[str] = None
    source_snapshot: str = ""
    source_task_id_snapshot: str = ""
    list_name_snapshot: str = ""
    column_snapshot: str = "closed"
    completed_at_snapshot: Optional[datetime] = None
    due_date_snapshot: Optional[datetime] = None
    # Provenance
    source: str = "user"               # "user" | "ai_drafted" | "ai_edited" (v1: always "user")
    tokens_used: int = 0
```

`to_chroma_metadata()` flattens collections to CSV and datetimes to ISO
(same pattern as `Memory`). `snapshot_from(memory, captured_text, capture_kind)`
classmethod constructs a Vial from a Memory at closure-time.

### New store (`pensieve/store/vials.py`)

Sibling to `ChromaMemoryStore` — wraps the `chroma_collection_vials`
collection (default `"vials"`, already plumbed in `config.py:57`).

```python
class ChromaVialStore:
    upsert_vial(vial)
    get_vial(vial_id) -> Optional[Vial]
    list_vials() -> list[Vial]
    list_vials_for_memory(memory_id) -> list[Vial]
    delete_vial(vial_id)
    captured_count_by_memory() -> dict[str, int]  # bulk for API perf
```

**No cascade delete.** Per the rubber-duck critique, Vials must survive
upstream task deletion or list-coverage changes. They are durable evidence,
not children.

### Derived pending-closure-capture flag

A Memory shows a "needs capture" chevron iff:

```
memory.column == "closed" AND captured_count_by_memory[memory.id] == 0
```

Computed at the API boundary in `GET /api/memories` with a single bulk
Chroma query. Not stored, no flag flip, no migration.

### API endpoints (`pensieve/api/server.py`)

- `GET /api/memories` — enrich each row with `vials_count` (captured only)
  and `pending_closure_capture: bool`. One bulk query at top, not per-row.
- `GET /api/memories/{id}` — same enrichment for a single Memory.
- `GET /api/memories/{id}/vials` — all Vials (captured + skipped) for one Memory.
- `POST /api/memories/{id}/vials` — body `{captured_text, capture_kind?}`.
  Enforces `mem.column == "closed"` (409 if not). Requires non-empty
  `captured_text` if `capture_kind == "captured"`; allows empty if `"skipped"`.
  Snapshots from current Memory at create time.
- `DELETE /api/vials/{vial_id}` — remove one Vial (lets user re-record).
- `GET /api/vials` — flat list of all Vials (for future export / recap).

### Frontend changes (`frontend-proto/pensieve.{js,css}`)

- `renderCard(m)` — append a small chevron button to closed cards with
  `pending_closure_capture`; replace with `📜 N` badge once `vials_count > 0`.
- `#vial-modal` — minimal modal with one textarea, Save button (captured),
  Skip button (skipped, no text required), Cancel button. Stops event
  propagation so it doesn't open the main card modal.
- CSS: `.card-vial-chevron` (amber, subtle), `.card-vial-badge` (📜 + count).

**UX guardrail (per strategy agent):** never auto-open the modal. The chevron
is the only entry point in v1. Closure capture that nags becomes closure
capture that gets ignored.

### Tests

- `tests/test_vial_schema.py` — round-trip, `snapshot_from`, Chroma
  metadata serialization edge cases (empty lists, None datetimes).
- `tests/test_vial_store.py` — upsert, get, list, list_for_memory, delete,
  `captured_count_by_memory` bulk, Vial-survives-Memory-deletion.
- `tests/test_vials_api.py` — first `TestClient` tests in the codebase.
  POST creates with snapshot, 409 on non-closed Memory, 404 on missing
  Memory, empty-captured rejected, skip allowed, GET enriches list/single
  responses, DELETE removes.

### Forward compatibility

- **v1.1 (AI polish):** add `?draft=true` to POST → calls LLM with
  `captured_text` → returns proposed `polished_text` → user accepts/edits →
  separate confirm endpoint saves. `polished_text` and `tokens_used`
  fields are reserved now.
- **v1.2 (recap integration):** `recap.py::_goal_block()` will pour Vials
  alongside Memories. The snapshot fields already hold the promo-relevant
  context, so a deleted Memory doesn't leave its Vial useless.
- **IC behaviors (item #2):** Vial v1 doesn't snapshot `connect_behaviors`
  because that field doesn't exist on Memory yet. Once it lands, add
  `connect_behaviors_snapshot: list[str]` to Vial in the same PR.

## Related sessions

- `2026-06-04_pensieve_sample-data-cleanup-and-readme-refresh.md` (this
  morning — sample-data cleanup + README catch-up to current 4-column
  lifecycle and the mirror env vars)
- `2026-06-04_pensieve_3-agent-review-and-vial-v1-kickoff.md` (this session
  — 3-agent review, 6 quick wins shipped, Vial v1 design + implementation
  kickoff)

## Open questions parked for v1.1+

- Should the Vial chevron be visible on closed memories from BEFORE today
  (the existing closed memories in live Chroma)? **Yes** — derived flag
  means they get it automatically and Andy can backfill recent ones.
- Should the dashboard show a Vials section inside the Memory modal?
  **v1: no.** Chevron + badge is enough. v1.1 can add a small inline list.
- Should we show Vial text in recap exports? **v1.2 work** (recap integration).
