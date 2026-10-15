# Pensieve — AGENTS.md

Project-level context for AI coding agents (GitHub Copilot, Claude Code,
Cursor, etc.) working in this repo. Read this first; it summarizes the
architecture, conventions, and hard constraints so you don't have to
re-derive them from the code.

## Project intent

A magical bowl for your work. Pensieve sits on top of Microsoft To-Do and
adds the memory layer To-Do can't hold (why a task was opened, which
project / strand it belongs to, what changed when it closed, what impact
it had), then surfaces a kanban view. The captured memories feed a
downstream promo / self-reflection step at semi-annual review time.

MVP cut = **Phases 0–3** (~6–8 weeks). See [`SPEC.md`](./SPEC.md) for the
full product spec and [`PHASES.md`](./PHASES.md) for the phased build plan.

---

## Hard constraints

- **LLM calls go through GitHub Copilot (this `personal-device` branch).**
  Every classification or generation goes through `get_chat_client()`;
  the default provider is `github_copilot` (official GitHub Copilot SDK,
  `pensieve/enrichment/copilot_client.py`) under the GitHub login in
  `COPILOT_GITHUB_USER`, which must be an account whose Copilot license
  may process this data (for work tasks, the company-managed account).
  Sessions run with every tool disabled and are deleted after each call.
  Azure OpenAI and GitHub Models remain selectable via `LLM_PROVIDER`.
  Never add any other endpoint. Model choice per purpose is set in the
  dashboard (`pensieve/ai_prefs.py`, `data/ai-models.json`).
- **Sources are read-only.** `pensieve/sources/outlook_com.py` and every
  other `TaskSource` implementation has zero mutation methods. Enforced by
  a unit test (`tests/test_sources.py::test_sources_are_read_only_no_write_methods`)
  that asserts forbidden method names (`save`, `update_task`, `patch`,
  `delete_task`, `set_notes`, `create_task`) don't exist on any source
  class. The Phase 2 writeback lives behind a separate `TaskSink` interface
  in `pensieve/sources/sink.py` (opt-in via `PENSIEVE_MIRROR_TO_SOURCE`).
- **TaskSink writeback is namespace-scoped.** The only writeback Pensieve
  performs by default is tagging the source task's `Categories` field with
  `pensieve/col:<column>` so a second PC syncing from the same Microsoft
  To-Do account sees the same kanban view. `OutlookCOMSink` in
  `pensieve/sources/outlook_com_sink.py` only touches categories whose
  string starts with the configured prefix. User-authored categories are
  preserved byte for byte. Conflict policy: source wins when the upstream
  `LastModificationTime` is newer than the local `enriched_at`. Completion
  remains terminal (a completed task lands in `closed` even if a remote
  mirror tag says otherwise).
- **Completion-mirror is a separately gated carve-out.** When
  `PENSIEVE_MIRROR_COMPLETION=true` (default off), dragging a card to the
  `closed` column ALSO calls `TaskItem.MarkComplete()` on the source. v1
  is one-way (close only): dragging out of `closed` does NOT call
  `set_completion(False)` on the source, because an accidental drag could
  silently un-complete a real task. The user reopens in Outlook; the next
  auto-sync moves the card back via the existing completion-drift handler
  in `pensieve.sync`. The flag is intentionally separate from
  `PENSIEVE_MIRROR_TO_SOURCE` because completion is higher-impact than a
  category tag (visible to delegates, propagates to shared lists).
- **Voice capture is the one additive writeback.** `pensieve/capture/`
  (outside `pensieve/sources` on purpose) turns a spoken note into a draft
  (Copilot, `capture` model purpose) and, only after the user confirms it in
  the dashboard, creates a NEW task: an Outlook TaskItem for `outlook_com`,
  or `POST /me/todo/lists/{id}/tasks` for `personal_graph`. It never edits,
  completes, or deletes existing tasks. Gated by `PENSIEVE_ALLOW_TASK_CREATE`.
- **Vault bridge for Andy's other agents** (`pensieve/bridge.py`). With
  `PENSIEVE_VAULT_DIR` set, Pensieve keeps `Agents/Pensieve/Now.md` in the
  Obsidian vault (rewritten only when the board changes) and lists
  `kind: task, to: pensieve` notes from `Agents/*/Handoffs/` or
  `Agents/Pensieve/Inbox/` under "From your agents". Requests go through the
  same confirm-and-create path as voice capture; Pensieve then writes only
  `status:`, `outcome:` and `outcome_date:` back into the agent's note.
- **Reversibility for any writeback.** Clearing the mirror tag (e.g.
  via `OutlookCOMSink.clear_column_tag`) restores the source task exactly
  to its pre-Pensieve state. Un-completing a task via the completion
  mirror (`set_completion(False)`) is also supported by the sink layer,
  even though v1 of the close writeback doesn't call it. No Notes / Body
  / Subject / Due Date mutation is performed by any sink.
- **Auto-sync is local and lock-coordinated.** The FastAPI app starts an
  `AutoSyncScheduler` (`pensieve/scheduler.py`) on `lifespan` that fires
  every `PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS` (default 120, set to 0 to
  disable). The scheduler funnels through the same `start_sync_job`
  helper as `POST /api/sync` and the same `SyncJobTracker.try_begin`
  atomic gate, so manual and scheduled syncs never collide on Chroma's
  single-writer constraint. The scheduler silently skips ticks whose
  resolved source is `sample_file` (set `PENSIEVE_AUTO_SYNC_SOURCE=outlook_com`
  to make it pull from Outlook when your default source is sample_file).
- **Shared installs (this branch) may read personal Microsoft To Do via Graph.**
  People connect their own personal Microsoft account and GitHub Copilot in the
  dashboard's Accounts screen (`pensieve/connections.py`, device-code sign-ins,
  DPAPI-encrypted token cache, `Tasks.ReadWrite` used to read plus the confirmed-create path of voice capture). The app registration
  lives in a personal Entra directory, never Microsoft's corporate tenant; see
  `desktop/SHARING.md`.
- **Phase 1 deliberately bypasses Microsoft Graph.** SFI (late 2025+)
  requires admin consent for new corp Entra apps accessing `Tasks.*` /
  `Mail.*` / `Calendars.*` scopes; FTE self-service is locked down. See
  [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1. Phase 1 uses local
  Outlook COM via `pywin32` — same data, zero auth surface, zero
  tenant-policy dependency.
- **All data is local.** ChromaDB persists to `data/chroma/`. No network
  egress except the LLM enrichment call.
- **Sync deletion sweep is scoped.** A narrow sync (single list) can only
  delete memories whose `source + list_name` was actually covered by that
  sync. Never globally orphan-prune across all sources / lists.
  See `pensieve/store/chroma.py::ChromaMemoryStore.find_orphan_ids`.
- **Connect recaps are list-scoped by default.** Only tasks whose source
  `list_name` is in `PENSIEVE_RECAP_LIST_NAMES` (default `CISO GRC`)
  feed into `POST /api/recap`. Personal lists (e.g. `home`, `UW
  Lectures`) never end up in a work recap unless the operator
  explicitly overrides via the env var or per-call `list_names` body
  field. The filter is applied in `pensieve/recap.py::filter_by_list_names`
  before scope / goal grouping; the resolved allowlist is echoed back
  on the response as `list_names_applied` and written into the docx
  meta line so the user can see what fed in.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Phase 0 entry (legacy) | PowerShell + dotenv | Validated enrichment quality fast; replaced by Python in Phase 1 |
| Phase 1+ primary stack | Python 3.12 + Typer CLI + FastAPI + Pydantic v2 | Matches sibling Azure-OpenAI projects |
| LLM | GitHub Copilot via the Copilot SDK (default `gpt-5.4`, changeable per purpose in the dashboard); Azure OpenAI / GitHub Models as fallbacks | Uses the Copilot license on the configured GitHub account; no keys in `.env` |
| Phase 1 task source | Local Outlook desktop via `pywin32` COM interop, **read-only** | SFI bypass — see [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1. Zero Graph dependency, zero Entra app reg, zero admin consent. |
| Memory store | **ChromaDB** `PersistentClient` at `data/chroma/` (cosine HNSW) | Local-only, semantic search out of the box, replaces earlier "SQLite" plan |
| Dashboard | Vanilla HTML/CSS/JS at `frontend-proto/`, Harry Potter themed on this `personal-device` branch (day parchment / night / Marauder easter egg; rendered art in `frontend-proto/assets/`), served by FastAPI StaticFiles | Small enough to stay framework-free; no React/Vite build step |
| Desktop app | `desktop/Pensieve.exe` (C# launcher built with the in-box .NET Framework csc via `desktop/build.ps1`) starts the backend hidden and opens Edge in app mode | No SDK/Rust/Node toolchain needed; see `desktop/README.md` |
| Phase 4 polish (post-MVP) | Tauri v2 desktop shell | Matches sibling packaging strategy |
| Telemetry | App Insights via `logger` MCP / SDK | Inherited from baseline |

---

## Repo layout (current)

```
Pensieve/
├── AGENTS.md              # this file
├── README.md              # public-facing pitch + quickstart
├── SETUP.md               # 10-minute install + first-sync walkthrough
├── SPEC.md                # authoritative product spec
├── PHASES.md              # Phase 0–3 plan
├── OPEN-QUESTIONS.md      # known unknowns + decision triggers
├── agency.toml            # Agency MCP config (baseline + Pensieve-specific)
├── pyproject.toml         # Python package metadata (editable install)
├── .env / .env.example    # Azure OpenAI + ChromaDB env vars
├── .gitignore
│
├── pensieve/              # the Python package (Phase 1 primary entry)
│   ├── __init__.py
│   ├── cli.py             # Typer CLI: init / sync / status / search / serve / goals
│   ├── config.py          # pydantic-settings .env loading
│   ├── sync.py            # orchestrator: sources → enrichment → ChromaDB
│   ├── garden.py          # Garden v1: pure-function freshness + board-health derivation
│   ├── quests.py          # Garden v2: pure-function daily quest generator + completion check
│   ├── quest_state.py     # Garden v2: persistence for today's quests + clean-day history
│   ├── achievements.py    # Garden v3: 9-badge predicate evaluator + level-summary builder
│   ├── achievement_state.py  # Garden v3: persistence for unlocked badges
│   ├── sources/           # TaskSource implementations (READ-ONLY contract)
│   │   ├── base.py
│   │   ├── outlook_com.py # pywin32 Outlook COM source
│   │   └── sample_file.py # dev source against data/samples.json
│   ├── enrichment/
│   │   ├── llm_client.py  # Azure OpenAI REST wrapper
│   │   ├── prompt.py      # loads prompts/enrich-memory-prompt.md
│   │   ├── connect_goals.py
│   │   ├── goals_importer.py  # PDF → goals via Azure OpenAI + 8-lane palette
│   │   └── enricher.py
│   ├── store/
│   │   ├── schema.py      # Memory + Vial Pydantic models
│   │   ├── chroma.py      # ChromaMemoryStore (PersistentClient)
│   │   └── vials.py       # ChromaVialStore (closure-capture; outlives Memories)
│   └── api/
│       └── server.py      # FastAPI + StaticFiles mount for the dashboard
│
├── desktop/               # Pensieve.exe launcher source, build + icon scripts, icon art
├── frontend-proto/        # HP-themed kanban dashboard (day / night / Marauder)
│   ├── index.html
│   ├── pensieve.js        # vanilla JS; fetches from API; in-card edit modal; PDF importer
│   ├── pensieve.css       # HP theme tokens + House (lane) color palette
│   ├── assets/            # rendered emblem, owl, Snitch, theme backdrops, splash loop
│   └── README.md
│
├── data/                  # local-only data
│   ├── samples.json       # canned tasks + strand catalog (anonymized sample)
│   ├── connect-goals.json # canonical Connect-Goal catalog (anonymized sample)
│   ├── chroma/            # ChromaDB persistent store (gitignored)
│   └── audit-log.jsonl    # one line per sync action (gitignored)
│
├── prompts/
│   ├── enrich-memory-prompt.md      # v2 (Connect-aware) — used by Phase 1
│   ├── extract-connect-goals.md     # PDF → goals extraction prompt
│   ├── reverie-proposal-prompt.md   # Phase 2.5 pre-stage
│   ├── reverie-debrief-prompt.md    # Phase 2.5 pre-stage
│   └── README.md
│
├── scripts/               # LEGACY — Phase 0 PowerShell pipeline
│   ├── Enrich-Memories.ps1
│   └── lib/
│       ├── Load-DotEnv.ps1
│       └── Invoke-AzureOpenAI.ps1
│
└── tests/                 # pytest suite (32 tests)
    ├── conftest.py
    ├── test_sources.py    # read-only contract enforcement
    ├── test_store.py      # Chroma upsert/idempotent/search/column-update/orphan-sweep
    ├── test_enrichment.py # prompt + goals + payload shape
    ├── test_sync_overlay.py  # column preservation across re-enrichment + auto-close
    └── test_goals_importer.py  # PDF extraction + lane palette assignment
```

Phase 0 PowerShell scripts are kept under `scripts/` as legacy. The Python
package under `pensieve/` is the canonical entry point; PowerShell is
not extended further.

---

## Canonical commands

```powershell
# one-time setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]

# verify config
pensieve init

# pull your real To-Do via Outlook COM, enrich, persist to ChromaDB
pensieve sync --source outlook_com

# or run against the dev sample file
pensieve sync --source sample_file

# inspect what's in the store
pensieve status
pensieve search "DORA regulator"
pensieve goals

# run the dashboard
pensieve serve --port 8765
# open http://localhost:8765/
```

---

## Running Agency in this project

```powershell
agency copilot                          # default profile (Phase 0 baseline)
agency copilot --profile phase0         # explicit Phase 0 (Graph disabled)
agency copilot --profile phase1         # live Graph for To-Do CRUD
agency copilot --profile phase2         # + kanban dev
agency copilot --profile reverie        # Phase 2.5 — calendar focus-block work
agency copilot --profile promo-feed     # + Synapse export work
agency config list --show-source        # verify config + provenance
```

See [`agency.toml`](./agency.toml) for the full MCP set per profile.

---

## Conventions

- **No em-dashes** in generated content. Use commas, periods, or hyphens with spaces.
- **Complete file replacements** preferred over partial diffs for tight
  scaffolding work; surgical edits otherwise.
- **One ship gate per phase** — see `PHASES.md`. Don't start Phase N+1 until
  Phase N's gate is met.
- **Reversibility first** — any Phase that touches live To-Do must have an
  undo path documented before it ships.
- **Anonymize sample data.** Anything committed to `data/samples.json`,
  `data/connect-goals.json`, frontend seed memories, or prompt examples must
  use generic role labels (`manager`, `direct report`, `peer`) and generic
  team names, not real colleague names or internal-org-specific identifiers.
  This repo is public.
