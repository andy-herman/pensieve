# Pensieve — Product Spec

> Carried over from the CISO GRC brainstorm at
> `Coding Projects (Local)\CISO GRC\brainstorms\01-day-to-day.md` on
> 2026-05-28. This is the authoritative product spec going forward.
> Edit here, not in the brainstorm — the brainstorm is now historical.

## 1. Vision

**Pensieve is a memory store for your work.** It sits on top of
Microsoft To-Do, enriches each task with the context To-Do can't hold,
gives you a kanban view of active work, and at promo-review time pours
the captured memories into Synapse Promo Coach as structured IC4→IC5
evidence.

It does not replace Microsoft To-Do. You keep entering tasks in To-Do.
Pensieve adds the *why*, the *strand*, the *closure context*, and the
*impact* — all the things that go missing the moment a task title is
written down.

## 2. Problem statement

Microsoft To-Do has three layered problems for someone trying to land
an IC4→IC5 promo:

1. **Context loss at task creation** (MVP focus). A task title is a
   3–10 word fragment. Two weeks later the title is meaningless without
   the why-I-opened-this context.
2. **Flat list ≠ work shape.** Real work has phases (incoming → in
   flight → blocked → review → done), strands (which project / regulator
   / workstream this belongs to), and dependencies. To-Do collapses all
   of this into a single linear list.
3. **No memory at perf-review time.** Closed tasks vanish. By H1 review
   the title-only fragments are useless and there's no captured impact
   statement to draw from. *This is the killer use case.*

MVP attacks (1) and (3). (2) is attacked partially in Phase 2.

## 3. MVP scope — Phases 0–3

| Phase | What ships | Ship gate |
|---|---|---|
| **0** | Local PS enrichment of canned To-Do task samples | Enrichment quality is good enough that Andy would trust it on real tasks |
| **1** | Live Graph integration → read tasks → enrich → write back to Notes field | Andy lets it run on his real To-Do for a week without disabling it |
| **2** | Local SQLite memory store + kanban web view | Andy opens the kanban >1x/day for 5 days |
| **2.5** | **Reverie** — Pensieve proposes focus-block calendar events from selected memories; user confirms before write | Andy accepts ≥ 3 Pensieve-proposed Reveries in a week and actually works the planned strand during the block |
| **3** | Reflection export → Synapse Promo Coach format | One real Vial makes it into a real Synapse Promo Coach analysis |

**Out of MVP:**
- Phase 4 — Tauri desktop polish (post-MVP)
- Phase 5 — Automatic closure-impact extraction (post-MVP)
- Phase 6 — Team rollout / multi-user (post-MVP)

## 4. Users

- **Pilot user #1:** Andy Herman (CISO GRC team, EU Reg + AI Transformation
  workstreams, IC4 targeting IC5 promo). Architectural decisions must
  not preclude a CISO GRC team rollout, but Phase 0–3 are single-user.
- **Pilot user #2 (post-MVP):** A CISO GRC team member to validate the
  pattern generalizes.
- **Downstream consumer:** Synapse Promo Coach (`agents/promo_coach_agent.py`)
  reads exported Reflections from Pensieve.

## 5. Concepts

| Term | What it is | Persistence |
|---|---|---|
| **Memory** | An enriched task record: original To-Do title + notes + LLM-extracted *why* / *impact* / *strand* / *closure context* | SQLite `memories` table; To-Do task `body` field for the round-trip subset |
| **Strand** | A project / workstream a memory belongs to. Examples: `dora-rfi`, `inbox-copilot-build`, `1on1-prep`, `ic5-promo-evidence` | SQLite `strands` table; manually curated + LLM-suggested |
| **Dive** | A query against memories — time window + strand + status filter | Ephemeral (UI state) |
| **Reverie** | A calendar-blocked focus session scheduled to work on one or more memories (typically grouped by strand). Pensieve proposes; user confirms; on write, a tentative Outlook event is created with strand metadata in the body. Round-trip: when the Reverie fires, Pensieve prompts user for which memories were actually advanced. | SQLite `reveries` table + corresponding Outlook calendar event id |
| **Reflection** | A synthesis of memories over a review period (week / month / H1 / H2) — narrative form, framed for the audience | SQLite `reflections` table; exported as markdown for Synapse |
| **Vial** | A single closed task's distilled impact statement, IC4→IC5 framed, ready for promo-evidence hand-off | SQLite `vials` table; exported as Synapse journal entry rows |

## 6. Data shape

### Memory (the core record)

| Field | Source | Type |
|---|---|---|
| `id` | UUID | string |
| `todo_task_id` | Graph `/me/todo/lists/{lid}/tasks/{tid}` | string |
| `todo_list_id` | Graph | string |
| `title` | To-Do task title | string |
| `original_notes` | To-Do task `body.content` at first sync | string |
| `why` | LLM-extracted from notes + surrounding context | string |
| `strand_id` | FK to `strands` | string |
| `status` | `open` / `in_flight` / `blocked` / `review` / `done` | enum |
| `created_at` | task creation (Graph) | timestamp |
| `closed_at` | when status transitions to `done` | timestamp \| null |
| `closure_context` | What changed when closed (LLM + user prompt) | string \| null |
| `impact` | LLM-extracted impact statement | string \| null |
| `confidence` | LLM self-rated confidence in the enrichment | float 0–1 |
| `last_synced_at` | last Graph round-trip | timestamp |

### Strand

| Field | Type |
|---|---|
| `id` | string (slug, e.g. `ic5-promo-evidence`) |
| `display_name` | string |
| `description` | string |
| `color` | string (kanban tag color) |
| `external_link` | optional ADO project / SharePoint / brainstorm URL |
| `default_reverie_minutes` | int — Pensieve's default block size when proposing a Reverie for memories in this strand (e.g. `60` for deep RFI work, `25` for chore strands) |

### Reverie (Phase 2.5)

| Field | Type |
|---|---|
| `id` | UUID |
| `proposed_start` | timestamp |
| `proposed_end` | timestamp |
| `strand_id` | FK to `strands` (Reveries are strand-scoped, not per-task) |
| `memory_ids` | list[str] — memories the user picked to work on in this block |
| `status` | `proposed` / `accepted` / `declined` / `fired` / `completed` / `bumped` |
| `outlook_event_id` | Graph calendar event id (null until accepted) |
| `outlook_event_etag` | for conflict detection on later edits |
| `actual_memories_advanced` | list[str] — populated by the post-Reverie prompt; what user actually worked on |
| `proposed_at` | timestamp |
| `accepted_at` | timestamp \| null |
| `fired_at` | timestamp \| null |

## 7. Pipeline (Phase 0 → 3)

```
                  ┌───────────────────────┐
                  │  Microsoft To-Do      │
                  │  (Phase 1+)           │
                  └───────────┬───────────┘
                              │ Graph read
              ┌───────────────▼───────────────┐
              │  Pensieve sync                │
              │  (Phase 0: canned samples)    │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │  Enrich prompt (Azure OpenAI) │
              │  → why / strand / impact      │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │  SQLite memories table        │
              │  (Phase 2)                    │
              └───────────────┬───────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐  ┌──────────▼──────────┐  ┌──────▼─────────┐
│ Kanban UI     │  │ Reflection builder  │  │ To-Do write-   │
│ (Phase 2)     │  │ (Phase 3)           │  │ back to Notes  │
└───────────────┘  └──────────┬──────────┘  │ (Phase 1)      │
                              │              └────────────────┘
                   ┌──────────▼──────────┐
                   │ Synapse Promo Coach │
                   │ (Phase 3 export)    │
                   └─────────────────────┘
```

## 8. Out-of-scope (MVP)

- Mobile app
- Multi-user / team rollout
- Notion sync (Synapse already has this — Pensieve exports to Synapse, not Notion directly)
- Real-time webhooks (Phase 1 is batch sync; webhooks are post-MVP)
- Calendar integration (Phase 2.5 candidate, not core MVP)

## 9. Hard constraints (architectural invariants)

1. **No external LLMs.** Inherited from CISO GRC pillar; matched to Inbox Copilot and Synapse.
2. **Reversibility.** Any phase that mutates To-Do shows a diff before writing. Phase 0 never writes.
3. **Phase 0 works without Graph.** Corp CA still blocks the built-in PS SDK app.
4. **Strand assignment is human-in-the-loop.** LLM suggests; user confirms before persistence (in Phase 1+).
5. **Closed tasks remain immutable in Pensieve.** A Vial is a snapshot; if To-Do data later changes, the Vial doesn't.
6. **Reverie write to calendar requires explicit user confirmation.** Pensieve never silently puts events on the user's calendar. Proposed Reveries appear in the UI as tentative cards; only after user clicks Accept does Pensieve `POST /me/events` via Graph. Reverie events are marked `showAs = "tentative"` on first write so they're visually distinct from meetings.

## 10. Open questions

See [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md).

## 11. Tech-stack inheritance

Pensieve deliberately re-uses architecture decisions from sibling projects:

| Decision | Inherited from |
|---|---|
| PowerShell Phase 0 + dotenv | Inbox Copilot |
| Azure OpenAI Cortex hub endpoint | Argus + Synapse |
| `Invoke-AzureOpenAI.ps1` REST wrapper | Inbox Copilot |
| FastAPI + asyncio + Pydantic v2 backend (Phase 2+) | Argus + Synapse + Inbox Copilot |
| SQLite for structured memory | Synapse |
| React + Vite frontend | Argus `frontend_shell` |
| Tauri v2 desktop packaging (post-MVP polish) | Synapse + Argus |
| No-external-LLM constraint | Inbox Copilot |
| Vault-aligned session lifecycle | Global Copilot Instructions |
| Agency `agency.toml` per project + baseline `remote_config` | Agency Copilot rollout 2026-05-28 |

This is deliberate: less to invent, less to maintain, less surface area
to debug when something breaks.
