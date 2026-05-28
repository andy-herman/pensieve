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

## Phase 1 — Live Graph, round-trip enrichment (target: 1.5–2 weeks)

**Goal:** Pensieve reads real To-Do tasks, enriches them, and writes the
enrichment back to the task's `body.content` (the Notes field) so it's
visible in To-Do itself. Memories are also captured locally (file or
SQLite, see Phase 2 question).

### Prerequisite

Graph unblock decision from the [Inbox Copilot 2026-05-22 decisions log
entry](../../Luna%20Master/AI%20Agents%20-%20Copilot/Memory/Decisions%20Log.md) must
be resolved. Three paths there:
1. **Custom Entra app registration** (long-term right answer, days of admin
   consent turnaround).
2. **Azure CLI client minting Graph tokens** — needs verification that the
   pre-consented scope set includes `Tasks.Read` / `Tasks.ReadWrite` for
   Microsoft tenant accounts.
3. **Wait for built-in PS SDK app to be allow-listed** — not under our
   control.

Phase 1 can't start until one of (1) or (2) is confirmed working for
`Tasks.ReadWrite` scope.

### Ships

- Graph client (PowerShell or Python — defer until unblock path is known).
- Round-trip sync: read all tasks from a configured list → enrich any that
  lack the `[pensieve-enriched]` sentinel → write enrichment to Notes →
  add sentinel.
- Closure capture: on status transition to `done`, prompt user for closure
  context + impact statement.
- Idempotency: re-running the sync doesn't re-enrich already-enriched tasks.
- Reversibility: dry-run mode shows the diff before write. `--apply` flag
  required to actually call `PATCH /me/todo/lists/{lid}/tasks/{tid}`.

### Ship gate

Andy lets Pensieve run on his real To-Do for a week. At end of week:
*"Did this make my To-Do better or worse?"* Better = Phase 1 done.

---

## Phase 2 — SQLite memory store + kanban UI (target: 2–3 weeks)

**Goal:** Pensieve becomes more than a To-Do sidecar — it has its own
view of work as a kanban board and its own searchable memory store.

### Ships

- SQLite schema per `SPEC.md` section 6:
  - `memories` (the core enriched record)
  - `strands` (projects / workstreams)
  - `vials` (closed-task impact snapshots — created at closure in Phase 1
    but only surfaced UI-side here)
- FastAPI backend with REST + WebSocket on a localhost port (suggest
  `:8420` — collides with Synapse, so pick `:8430` or `:8440`).
- Sync command CRUD: list memories, filter by strand, get a memory, update
  a memory's strand assignment.
- React + Vite kanban UI:
  - 5 columns: `open` / `in_flight` / `blocked` / `review` / `done`
  - Color-coded by strand
  - Drag-and-drop status transitions write back to To-Do via Phase 1
    pipeline
  - Strand sidebar with counts
- Strand management: create / rename / archive strands; LLM-suggest a
  strand for a memory with no human-assigned strand.

### Ship gate

Andy opens the kanban >1x/day for 5 consecutive days. Pattern is the same
as Inbox Copilot cockpit gate.

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
