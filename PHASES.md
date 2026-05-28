# Pensieve — Phase Plan

Six-to-eight-week MVP across **Phases 0–3**. Each phase has one ship gate.
Don't start Phase N+1 until Phase N's gate is met.

---

## Phase 0 — Local enrichment, canned samples (target: 1 week)

**Goal:** Validate that an LLM can produce useful *why* / *strand* / *impact*
enrichment given only a task title + brief notes + surrounding context.
Graph stays disabled — work against canned samples mirroring Inbox Copilot
Phase 0.

### Ships

- `scripts/Enrich-Memories.ps1` — PowerShell pipeline with `-DryRunSampleFile`
  flag.
- `scripts/lib/Load-DotEnv.ps1` — copied from Inbox Copilot.
- `scripts/lib/Invoke-AzureOpenAI.ps1` — copied from Inbox Copilot
  (`gpt-5.4-2`, omits `temperature`, uses `max_completion_tokens`, Cortex hub).
- `prompts/enrich-memory-prompt.md` — the canonical enrichment prompt with
  schema: `why`, `strand_suggestion`, `impact_hypothesis`, `confidence`.
- `data/samples.json` — 8–10 canned tasks covering each strand archetype:
  RFI work, internal meetings, learning, side projects, mentoring, ops chores.
- `.env.example` mirroring Inbox Copilot.

### Ship gate

Andy reads through the enriched samples and judges:
*"If this enrichment were running on my real To-Do, would I trust it?"*
Answer = yes for ≥ 80% of samples → Phase 0 done.

### Out of scope for Phase 0

- Any Graph call (corp CA blocked).
- Any persistent store (run output goes to stdout / JSON file).
- Any UI.

---

## Phase 1 — Outlook COM (read-only) + ChromaDB + dashboard ✅ shipped 2026-05-28

**Goal:** Pensieve reads Andy's real To-Do tasks via local Outlook COM (no Graph, no Entra app, no admin consent), enriches them with the v2 prompt (Connect-Goal aware), persists Memories locally in ChromaDB, and renders them on an HP-themed kanban dashboard he can use daily. Zero writes to To-Do — Phase 1 is observe-only.

### Architecture pivot (the headline)

Original Phase 1 plan: live Graph (`Tasks.ReadWrite`) read + writeback to Notes. That path is dead under SFI:

- Microsoft Graph PS SDK built-in app blocked by corp CA (verified 2026-05-22 in Inbox Copilot session)
- Azure CLI client token reconfirmed to have **zero** Tasks/Mail/Calendar scopes (JWT decoded 2026-05-28)
- Custom corp Entra app reg requires admin consent for Tasks scopes; FTE self-service is locked down under SFI
- Personal MSA app is a workaround but only sees personal tasks, not work tasks

**Decision (2026-05-28):** Pivot Phase 1 to local Outlook COM via pywin32. Outlook desktop already authenticates against the corp tenant; COM gives us the same tasks Graph would, with zero auth surface and zero tenant-policy dependency. Writeback deferred to Phase 2 pending a real Graph unblock.

### Ships

- **`pensieve/` Python package** (replaces Phase 0 PowerShell entry point; PS scripts kept as legacy):
  - `pensieve/sources/outlook_com.py` — read-only COM source (zero `.Save()` calls)
  - `pensieve/sources/sample_file.py` — dev source against `data/samples.json`
  - `pensieve/sources/base.py` — `TaskSource` abstract; **no write methods on the interface**
  - `pensieve/enrichment/` — LLM client (port of Inbox Copilot helper), v2 prompt loader, Connect-Goals context, single-task enricher
  - `pensieve/store/chroma.py` — `ChromaMemoryStore` wrapping `chromadb.PersistentClient` at `data/chroma/`
  - `pensieve/store/schema.py` — `Memory` Pydantic model + Chroma-metadata flattening (CSV for list fields) + dashboard serializer
  - `pensieve/sync.py` — orchestrator with ThreadPoolExecutor concurrency=3, idempotency via `source_last_modified`, audit log
  - `pensieve/api/server.py` — FastAPI: `/api/healthz`, `/api/memories`, `PATCH /api/memories/{id}` (in-card edit), `PATCH /api/memories/{id}/column` (drag-drop), `/api/search?q=` (semantic), `/api/goals` + StaticFiles mount for the dashboard
  - `pensieve/cli.py` — Typer CLI: `init`, `sync`, `status`, `search`, `serve`, `goals`
- **`frontend-proto/` HP-themed dashboard** (already existed; rewired to API)
  - Fetches Memories from `/api/memories` with seed-data fallback when API is offline
  - Drag-drop column changes PATCH the API
  - Semantic-search input runs `/api/search?q=`
  - Click any card → full edit modal: title, strand, column, review flag, why, impact, Connect-Goal multi-select chips, alignment note, private note → Save PATCHes API and updates board
  - Footer shows connection status + source label
- **`data/connect-goals.json`** — canonical Connect-Goal catalog (mirrors vault `Memory\Connect Goals\Current.md`); enrichment prompt feeds these to the LLM as context
- **`tests/`** — 15 pytests covering sources read-only contract, store CRUD + idempotency + semantic search, enrichment prompt build
- **End-to-end verified:** 10/10 samples enriched successfully (54,935 tokens, 1 flagged for review), idempotent re-sync correctly skips unchanged tasks, dashboard live at `http://localhost:8765/`, in-card edits round-trip through Chroma

### Ship gate

Andy runs `pensieve sync --source outlook_com` against his real To-Do, uses the dashboard daily for one week, and at end of week:
*"My real To-Do tasks are untouched, and the Pensieve dashboard is the place I look first when planning my day."* → Phase 1 done.

### Explicitly deferred from Phase 1

- **Writeback to To-Do Notes** — Phase 2. Pending: a viable Graph or COM write path that respects user-edited Notes.
- **Calendar integration** — Phase 2.5 (Reverie). Andy manually blocks focus time for now.
- **Reflection export to Synapse** — Phase 3.

---

## Phase 2 — Writeback + closure capture (target: 1.5–2 weeks)

**Goal:** Make the enrichment visible *inside* Microsoft To-Do itself (not just on the Pensieve dashboard), and capture impact statements at task closure so the Phase 3 Vials have richer fuel.

### Prerequisite

A viable write path to the To-Do `body.content` Notes field. Options:

| Path | Status | Notes |
|---|---|---|
| Outlook COM `.Save()` on the TaskItem | Likely viable — same auth surface that Phase 1 already proves works | Need to validate Outlook doesn't strip / reformat the markdown we write |
| Custom corp Entra app reg with `Tasks.ReadWrite` | Blocked under SFI — see OPEN-QUESTIONS Q1 | Long-term right answer if admin consent eventually lands |
| Personal MSA Graph app | Only sees personal tasks | Not viable for work tasks |

**Leaning:** Outlook COM write, sentinel-guarded so user-edited Notes are never overwritten. This breaks the Phase 1 read-only-source contract — Phase 2 introduces a separate `TaskSink` interface; sources stay read-only.

### Ships

- `pensieve/sinks/` — new abstract `TaskSink` interface; `OutlookCOMSink` implementation
- Sentinel-comment scheme: `<!-- pensieve-managed:v1 -->` markers around Pensieve-written sections; manual edits outside the markers are preserved
- Dry-run mode shows the diff before write; `--apply` required
- Closure capture flow: when sync detects a task transitioned to `Completed`, surface a one-shot prompt ("What changed? What's the impact?") via the dashboard; persisted as Vial fuel on the Memory
- New dashboard control: per-Memory "exclude from writeback" toggle for sensitive tasks

### Ship gate

Andy opts in to writeback for ≥ 5 consecutive days and reports no destructive overwrites of his manual edits.

---

## Phase 2.5 — Reverie (calendar focus auto-blocking) (target: 1–1.5 weeks)

**Goal:** Pensieve doesn't just remember work — it protects time to do it.
Selected memories on the kanban can be converted to a **Reverie**: a
tentative focus block on the Outlook calendar, scoped to a strand, with
the chosen memories listed in the event body. Round-trip closes when the
Reverie fires and Pensieve prompts the user for which memories were
actually advanced.

### Prerequisites

- Phase 2 kanban shipped (need the "select these N memories" UX).
- Calendar MCP enabled (already in `agency.toml` `phase2` profile;
  also live in new `reverie` profile).
- Graph `Calendars.ReadWrite` scope confirmed (same auth path as
  Phase 1 `Tasks.ReadWrite` — see OPEN-QUESTIONS.md Q1).

### Ships

- **`reveries` SQLite table** per `SPEC.md` section 6.
- **`prompts/reverie-proposal-prompt.md`** (pre-staged 2026-05-28) — system
  prompt for the Reverie planner; strict JSON schema with hard rules
  (no invented memory IDs, no strand mixing, cap at 3 per call, respect
  default minutes plus or minus 25 percent, no em-dashes).
- **`prompts/reverie-debrief-prompt.md`** (pre-staged 2026-05-28) — system
  prompt that converts the user's post-Reverie checkbox + free-text reply
  into structured `actual_memories_advanced`, `impact_seeds` (Vial fuel),
  and `unplanned_work_candidates` (new-memory suggestions).
- **Reverie proposal flow** in kanban UI:
  - User multi-selects memories on the kanban → "Schedule a Reverie" CTA.
  - Pensieve groups by strand, asks LLM (or rules-only fallback) to suggest
    duration based on strand defaults + memory count + memory complexity.
  - Pensieve calls Graph `findMeetingTimes` to propose 2–3 slot options
    in the next N days that don't conflict with existing meetings.
  - User picks a slot → Pensieve `POST /me/events` with:
    - `subject = "🧠 Pensieve Reverie — <strand display_name>"`
    - `showAs = "tentative"`
    - `body.content = markdown list of memory titles + links back to Pensieve`
    - `categories = ["Pensieve", strand_display_name]`
- **Daily Reverie suggester** (background loop, runs each morning):
  - Looks at open memories with no scheduled Reverie + `priority` signal.
  - Suggests up to 3 Reveries for today, surfaced as a kanban banner.
  - Never auto-creates the calendar event — always one click away.
- **Post-Reverie prompt:**
  - When a Reverie fires (detected next-sync after `proposed_end`),
    surface a single prompt: "Which memories did you advance during the
    Pensieve Reverie at 2pm?" → checkbox list of the Reverie's memories.
  - Captured answers update `reveries.actual_memories_advanced` AND feed
    into Phase 3 Reflection synthesis ("how much focus time on what
    strand").
- **Conflict handling:**
  - If a meeting later lands on an accepted Reverie, Pensieve marks the
    Reverie `bumped`, surfaces it on the kanban with "rescheduled?"
    affordance, and lets user re-propose without re-entering memories.
- **Viva Focus Time integration (optional, time-permitting):**
  - If Viva Insights Focus Time category is available on the user's
    calendar, write Reveries as Focus Time events so they get Viva's
    Teams-status / chat-suppression treatment for free.

### Ship gate

Andy accepts **≥ 3 Pensieve-proposed Reveries** in a week and reports
"yes, I actually worked the planned strand during those blocks" for at
least 2 of them. Failure mode = Reverie acceptance rate < 30% or
Reveries get bumped without re-acceptance → revisit proposal logic.

### Out of scope for Phase 2.5

- Multi-user / shared Reveries (Phase 6 — team rollout).
- Reverie templates ("recurring deep-work mornings").
- Auto-rescheduling bumped Reveries without user input.
- Integration with Outlook's auto-accept rules.

---

## Phase 3 — Reflection export → Synapse Promo Coach (target: 1–1.5 weeks)

**Goal:** Close the loop. The memories Pensieve has been capturing for
weeks become structured input for Andy's IC4→IC5 promo case via Synapse
Promo Coach.

### Ships

- **Reflection builder** — given a review period (last week / last month /
  H1 / H2), aggregates memories + vials in that window into a single
  narrative. Strand-aware: groups by strand, highlights highest-impact
  vials, suppresses noise.
- **Vial export format** — JSON / markdown matching Synapse's `journal_entries`
  table schema. Tags align with Synapse's existing tag taxonomy
  (`workstream`, `ado_item`, etc.) plus a new `pensieve_vial` tag.
- **Synapse import path** — write entries directly to Synapse's SQLite
  (`data/agent_i.db`) `journal_entries` table, or POST to Synapse's
  `/api/neural/log` endpoint. Decision deferred until we read Synapse's
  current import code.
- **Promo Coach feedback loop** — after Synapse runs Promo Coach analysis
  on imported vials, surface any "missing evidence" gaps back into Pensieve
  as prompts ("you don't have evidence for `architecture-review` criterion;
  any closed task that fits?").

### Ship gate

One real Vial from Pensieve makes it into a real Synapse Promo Coach
analysis and Andy judges the resulting impact statement as
*"better than what I would have written from memory two weeks later."*

---

### Phase 3 inputs gained from Phase 2.5

Phase 3 Reflections become richer because Phase 2.5 captured "how much
focus time did I commit to which strand, and what did I actually advance
during it." Vials gain a "this work happened in N Reveries totalling X
hours of focused time" enrichment automatically.

---

## Post-MVP backlog (Phase 4+)

- **Phase 4 — Tauri desktop shell.** Same packaging pattern as Argus +
  Synapse (PyInstaller sidecar + WiX MSI).
- **Phase 5 — Automatic closure-impact extraction.** Instead of prompting
  user at closure, scrape surrounding signals (recent commits, ADO items,
  emails, calendar events around the closure time) and propose an impact
  statement automatically.
- **Phase 6 — Team rollout / multi-user.** Multi-tenant Entra app, shared
  strand catalog, team kanban view, anonymized telemetry.
- **Phase 7 — Agent C unification.** Merge the To-Do half (Pensieve) and
  the ADO half (Agent C / Neural Work Logger) into a single coherent
  Work Memory product. Existing Agent C imports into Synapse become
  Pensieve memories.
