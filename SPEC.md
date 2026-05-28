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
| **0** | Local PowerShell enrichment of canned To-Do task samples | Enrichment quality is good enough that Andy would trust it on real tasks |
| **1** | **Python `pensieve` package**: Outlook COM (read-only) → LLM enrichment → local ChromaDB persistence → FastAPI + HP-themed kanban dashboard at `http://localhost:8765/`. Connect Goal alignment per Memory. | Andy uses the dashboard daily for a week; no destructive change ever lands on his real To-Do tasks |
| **2** | Writeback path (sentinel-guarded mirror of `why` + `strand` into the To-Do Notes field) + closure-capture flow | Andy opts in to writeback for ≥ 5 days without disabling it |
| **2.5** | **Reverie** — Pensieve proposes focus-block calendar events from selected memories; user confirms before write | Andy accepts ≥ 3 Pensieve-proposed Reveries in a week and actually works the planned strand during the block |
| **3** | Reflection export → Synapse Promo Coach format | One real Vial makes it into a real Synapse Promo Coach analysis |

**Phase 1 architecture pivot (2026-05-28):** Original plan called for Microsoft Graph (`Tasks.ReadWrite`) for both read and writeback. Under SFI (late 2025+) corp Entra app registration with delegated `Tasks.*` scopes requires admin consent and is locked down for FTE accounts. Path 2 (Azure CLI token) confirmed dead — see [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1. Phase 1 now bypasses Graph entirely via local Outlook COM interop (read-only). Writeback deferred to Phase 2 pending unblock or alternative path.

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
| **Memory** | An enriched task record: original To-Do title + notes + LLM-extracted *why* / *impact* / *strand* / *Connect-goal alignment* / *closure context* | ChromaDB `memories` collection; (Phase 2) To-Do task `body` field mirrors `why` + `strand` |
| **Strand** | A project / workstream a memory belongs to. Examples: `dora-rfi`, `inbox-copilot-build`, `1on1-prep`, `ic5-promo-evidence` | `data/samples.json` strand catalog; flattened into each Memory record; LLM-suggested with `needs_human_strand_review` flag for low-confidence cases |
| **Connect Goal** | One of the user's semi-annual Connect commitments (House-aligned: 4 canonical Houses + 4 extension Houses for users with more goals). Memories carry `connect_goal_ids` (multi-select) + `connect_alignment_note` so the dashboard can group, filter, and at promo-time generate evidence per Connect goal. | `data/connect-goals.json` (populated via the dashboard's Connect PDF importer or edited by hand); flattened into Memory metadata |
| **Dive** | A query against memories — time window + strand + status + semantic search | Ephemeral (UI state); semantic search uses Chroma `query()` over the document embedding |
| **Reverie** | A calendar-blocked focus session scheduled to work on one or more memories (typically grouped by strand). Pensieve proposes; user confirms; on write, a tentative Outlook event is created with strand metadata in the body. Round-trip: when the Reverie fires, Pensieve prompts user for which memories were actually advanced. | Phase 2.5 — separate ChromaDB collection (`reveries`) + corresponding Outlook calendar event id |
| **Reflection** | A synthesis of memories over a review period (week / month / H1 / H2) — narrative form, framed for the audience. Phase 3 reflections are Connect-Goal-aware: one section per Connect commitment. | Phase 3 — separate ChromaDB collection (`reflections`); exported as markdown for Synapse |
| **Vial** | A single closed task's distilled impact statement, IC4→IC5 framed, ready for promo-evidence hand-off | Phase 3 — separate ChromaDB collection (`vials`); exported as Synapse journal entry rows |

## 6. Data shape

### Memory (the core record — actual `pensieve/store/schema.py`)

| Field | Source | Type | Notes |
|---|---|---|---|
| `id` | source task id (Outlook `EntryID` for `outlook_com`; sample id for `sample_file`) | string | Stable across re-syncs → idempotency key |
| `source` | `outlook_com` / `sample_file` | string | |
| `source_last_modified` | Outlook `LastModificationTime` (or sample equivalent) | ISO timestamp | Used to skip re-enrichment when task unchanged |
| `title` | task title | string | Editable in dashboard |
| `original_notes` | task body content at first sync | string | |
| `why` | LLM-extracted | string | Editable in dashboard |
| `why_concise` | LLM-extracted (≤ 100 chars) | string | Renders on card front |
| `impact` | LLM-extracted impact hypothesis | string | Editable in dashboard |
| `suggested_strand` | LLM-extracted strand id | string \| null | Editable in dashboard |
| `strand_kind` | strand archetype (RFI / build / mentoring / ...) | string | |
| `needs_human_strand_review` | LLM self-flag when strand confidence is low | bool | Editable in dashboard |
| `connect_goal_ids` | LLM-extracted, multi-select | list[string] | Editable in dashboard |
| `connect_alignment_note` | LLM-extracted prose | string | Editable in dashboard |
| `connect_alignment_confidence` | LLM 0–1 | float | |
| `confidence_strand` | LLM 0–1 | float | |
| `confidence_impact` | LLM 0–1 | float | |
| `notes_for_user` | LLM-extracted "things the user should know" | string | Editable in dashboard |
| `categories` | LLM-extracted tags | list[string] | |
| `column` | kanban column — `memory` / `dive` / `reverie` / `reflection` / `vial` | enum | Editable via drag-drop or dashboard dropdown |
| `enriched_at` | when the LLM enrichment ran | ISO timestamp | |
| `prompt_version` | enrichment prompt version (`v2`) | string | |

**Chroma metadata constraint:** ChromaDB only accepts scalar metadata (str/int/float/bool). Lists (`connect_goal_ids`, `categories`) are CSV-flattened on write (`connect_goal_ids_csv`) and reconstructed on read in `Memory.to_chroma_metadata()` / `ChromaMemoryStore._reconstruct()`.

### Strand (catalog entry, sourced from `data/samples.json`)

| Field | Type |
|---|---|
| `id` | string (slug, e.g. `dora-rfi`) |
| `display_name` | string |
| `kind` | string (RFI / build / mentoring / ops / learning / 1on1 / promo) |
| `description` | string |
| `color` | string (kanban tag color) |
| `external_link` | optional ADO / SharePoint / brainstorm URL |
| `default_reverie_minutes` | int — Phase 2.5 default focus-block size |

### Connect Goal (sourced from `data/connect-goals.json`)

| Field | Type | Notes |
|---|---|---|
| `id` | string (slug, e.g. `goal-1-dora-deep-dive`) | |
| `number` | int (1–6) | Display order |
| `name` | string | Full Connect-document phrasing |
| `short_name` | string | Kanban chip label |
| `house` | enum (`gryffindor` / `slytherin` / `ravenclaw` / `hufflepuff`) | Drives dashboard chip color |
| `glyph` | string (1–2 chars) | Visual marker on chip |
| `description` | string | What "good" looks like for this commitment |

### Reverie (Phase 2.5)

| Field | Type |
|---|---|
| `id` | UUID |
| `proposed_start` | timestamp |
| `proposed_end` | timestamp |
| `strand_id` | FK to strand catalog (Reveries are strand-scoped, not per-task) |
| `memory_ids` | list[str] — memories the user picked to work on in this block |
| `status` | `proposed` / `accepted` / `declined` / `fired` / `completed` / `bumped` |
| `outlook_event_id` | Graph or COM calendar event id (null until accepted) |
| `outlook_event_etag` | for conflict detection on later edits |
| `actual_memories_advanced` | list[str] — populated by the post-Reverie prompt |
| `proposed_at` | timestamp |
| `accepted_at` | timestamp \| null |
| `fired_at` | timestamp \| null |

## 7. Pipeline (Phase 1 = built, Phases 2/2.5/3 = planned)

```
                  ┌───────────────────────┐
                  │  Microsoft To-Do      │   read-only
                  │  via local Outlook    │   (no .Save() calls)
                  │  COM interop          │
                  └───────────┬───────────┘
                              │ pywin32
              ┌───────────────▼───────────────┐
              │  pensieve.sources.outlook_com │
              │  (or sample_file for dev)     │
              └───────────────┬───────────────┘
                              │ RawTask
              ┌───────────────▼───────────────┐
              │  pensieve.enrichment.enricher │
              │  Azure OpenAI gpt-5.4-2       │
              │  + Connect-Goals context      │
              │  → why / strand / impact /    │
              │    connect_goal_ids / ...     │
              └───────────────┬───────────────┘
                              │ Memory
              ┌───────────────▼───────────────┐
              │  ChromaDB (PersistentClient)  │
              │  data/chroma/ — local-only    │
              │  collection: memories         │
              └───────────────┬───────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌─────────▼──────────┐  ┌──────▼──────────────┐
│ FastAPI server │  │ Phase 3 Reflection │  │ Phase 2 writeback   │
│ + HP-themed    │  │ builder (planned)  │  │ to To-Do Notes      │
│ dashboard      │  └─────────┬──────────┘  │ (sentinel-guarded,  │
│ localhost:8765 │            │             │  user opt-in)       │
│ + semantic     │  ┌─────────▼──────────┐  └─────────────────────┘
│   search +     │  │ Synapse Promo      │
│   in-card edit │  │ Coach (Phase 3)    │
└────────────────┘  └────────────────────┘
```

**Phase 2.5 Reverie** plugs into the same pipeline: kanban multi-select → Reverie proposal → Outlook calendar write (separate `reveries` collection). Same read-only-COM contract for read paths; explicit-user-confirm gate for the one calendar write.

## 8. Out-of-scope (MVP)

- Mobile app
- Multi-user / team rollout
- Notion sync (Synapse already has this — Pensieve exports to Synapse, not Notion directly)
- Real-time webhooks (Phase 1 is batch sync; webhooks are post-MVP)
- Calendar integration (Phase 2.5 candidate, not core MVP)

## 9. Hard constraints (architectural invariants)

1. **No external LLMs.** Inherited from CISO GRC pillar; matched to Inbox Copilot and Synapse. Azure OpenAI Cortex hub, keyless via `DefaultAzureCredential`.
2. **Sources are read-only.** Every `TaskSource` implementation has zero mutation methods. `OutlookCOMSource` deliberately has no `.Save()` calls anywhere. Enforced by a unit test that asserts forbidden method names (`save`, `update_task`, `patch`, `delete_task`, `set_notes`, `create_task`) don't exist on any source class. Phase 2 writeback, when added, will be a separate `TaskSink` interface — explicitly opt-in.
3. **Phase 1 deliberately bypasses Microsoft Graph.** SFI (late 2025+) requires admin consent for new corp Entra apps accessing `Tasks.*` / `Mail.*` / `Calendars.*` scopes; self-service registration for FTE accounts is locked down. See [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1. Phase 1 uses local Outlook COM interop instead — same data, zero auth surface, zero tenant-policy dependency.
4. **All data is local.** ChromaDB persists to `data/chroma/`. No network egress except the LLM enrichment call. Nothing leaves the machine without an explicit Phase 3 export action.
5. **Strand assignment is human-in-the-loop.** LLM suggests with `confidence_strand`; low-confidence rows are flagged `needs_human_strand_review = true` and the dashboard surfaces them with a review pill. User can override strand inline in the card-edit modal.
6. **Connect-Goal alignment is first-class.** Every Memory carries `connect_goal_ids` + `connect_alignment_note`. Dashboard surfaces House-colored chips. Phase 3 Reflections will be Connect-Goal-grouped by default.
7. **Reversibility for any future writeback.** Phase 2 writeback (when added) must show a diff before write and use a sentinel comment so user-edited Notes are never overwritten.
8. **Closed tasks remain immutable in Pensieve.** A Vial is a snapshot; if To-Do data later changes, the Vial doesn't.
9. **Reverie write to calendar requires explicit user confirmation.** Pensieve never silently puts events on the user's calendar. Proposed Reveries appear in the UI as tentative cards; only after user clicks Accept does Pensieve create the calendar event. Reverie events are marked `showAs = "tentative"` on first write so they're visually distinct from meetings.

## 10. Open questions

See [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md).

## 11. Tech-stack inheritance

Pensieve deliberately re-uses architecture decisions from sibling projects:

| Decision | Inherited from |
|---|---|
| PowerShell Phase 0 (legacy; replaced by Python in Phase 1) | Inbox Copilot |
| Azure OpenAI Cortex hub endpoint | Argus + Synapse |
| `Invoke-AzureOpenAI.ps1` REST wrapper (legacy; ported to `pensieve/enrichment/llm_client.py`) | Inbox Copilot |
| FastAPI + asyncio + Pydantic v2 backend | Argus + Synapse + Inbox Copilot |
| ChromaDB for local memory store (replaced earlier "SQLite" plan) | New choice for Pensieve — semantic search out of the box |
| Vanilla JS + HTML/CSS dashboard (HP-themed) | Custom for Pensieve; small enough to stay framework-free |
| Tauri v2 desktop packaging (post-MVP polish) | Synapse + Argus |
| No-external-LLM constraint | Inbox Copilot |
| Agency `agency.toml` per project + baseline `remote_config` | Agency Copilot rollout 2026-05-28 |
| Outlook COM as the SFI-safe productivity-data source | New choice for Pensieve — first project to hit the SFI Graph block |

This is deliberate: less to invent, less to maintain, less surface area
to debug when something breaks.
