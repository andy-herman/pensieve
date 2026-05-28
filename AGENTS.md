# Pensieve — AGENTS.md

This is a **build project**, spun out from the CISO GRC ideation hub on
2026-05-28. Unlike the hub, this folder ships code — but the same
vault-wired session lifecycle applies.

## Project intent

A magical bowl for your work. Pensieve sits on top of Microsoft To-Do and
adds the memory layer To-Do can't hold (why a task was opened, which
project / strand it belongs to, what changed when it closed, what impact
it had), then surfaces a kanban view. The captured memories feed Synapse
Promo Coach at semi-annual review time.

MVP cut = **Phases 0–3** (~6–8 weeks). See [`SPEC.md`](./SPEC.md) for the
full product spec and [`PHASES.md`](./PHASES.md) for the phased build plan.

---

## Vault wiring

| Vault location | Purpose |
|---|---|
| `C:\Andy Herman\Luna Master\AI Agents - Copilot\Projects\Pensieve.md` | Project landing page (status, decisions, session log) |
| `C:\Andy Herman\Luna Master\AI Agents - Copilot\Sessions\` | All session notes for this project go here, prefixed `YYYY-MM-DD_pensieve_*.md` |
| `C:\Andy Herman\Luna Master\AI Agents - Copilot\Memory\Decisions Log.md` | Append decisions made in Pensieve sessions with `[Pensieve]` prefix |
| `..\CISO GRC\brainstorms\01-day-to-day.md` | Original brainstorm seed (historical; SPEC.md is now authoritative) |

Sessions in this project are tagged with `pensieve` in their frontmatter so
they can be filtered from the global Sessions folder.

---

## Hard constraints

- **No external LLMs.** Every classification or generation MUST hit Azure
  OpenAI (Cortex hub, deployment `gpt-5.4-2`, keyless via
  `DefaultAzureCredential`) or Microsoft 365 Copilot via MCP. Never an
  external endpoint. Inherited from the CISO GRC pillar 1 constraint and
  matched to Inbox Copilot and Synapse for consistency.
- **Sources are read-only.** `pensieve/sources/outlook_com.py` and every
  other `TaskSource` implementation has zero mutation methods. Enforced by
  a unit test (`tests/test_sources.py::test_sources_are_read_only_no_write_methods`)
  that asserts forbidden method names (`save`, `update_task`, `patch`,
  `delete_task`, `set_notes`, `create_task`) don't exist on any source
  class. Phase 2 writeback, when added, will live behind a separate
  `TaskSink` interface that is opt-in.
- **Reversibility for any future writeback.** When Phase 2 lands, no task
  is modified without a user-visible diff and a sentinel-comment scheme
  that preserves user-edited Notes outside the Pensieve-managed section.
- **Phase 1 deliberately bypasses Microsoft Graph.** SFI (late 2025+)
  requires admin consent for new corp Entra apps accessing `Tasks.*` /
  `Mail.*` / `Calendars.*` scopes; FTE self-service is locked down. See
  [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1. Phase 1 uses local
  Outlook COM via `pywin32` — same data, zero auth surface, zero
  tenant-policy dependency.
- **All data is local.** ChromaDB persists to `data/chroma/`. No network
  egress except the LLM enrichment call.

---

## Tech stack (planned)

| Layer | Choice | Why |
|---|---|---|
| Phase 0 entry (legacy) | PowerShell + dotenv | Validated enrichment quality fast; replaced by Python in Phase 1 |
| Phase 1+ primary stack | Python 3.12 + Typer CLI + FastAPI + Pydantic v2 | Matches Argus / Synapse / Inbox Copilot |
| LLM (all phases) | Azure OpenAI `gpt-5.4-2` via Cortex hub, keyless via `DefaultAzureCredential` | Same as Argus + Synapse |
| Phase 1 task source | Local Outlook desktop via `pywin32` COM interop, **read-only** | SFI bypass — see [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1. Zero Graph dependency, zero Entra app reg, zero admin consent. |
| Memory store | **ChromaDB** `PersistentClient` at `data/chroma/` (cosine HNSW) | Local-only, semantic search out of the box, replaces earlier "SQLite" plan |
| Dashboard | Vanilla HTML/CSS/JS at `frontend-proto/`, HP-themed, served by FastAPI StaticFiles | Small enough to stay framework-free; no React/Vite build step |
| Phase 4 polish (post-MVP) | Tauri v2 desktop shell | Matches Argus + Synapse packaging |
| Telemetry | App Insights via `logger` MCP / SDK | Inherited from baseline |

---

## Repo layout (current)

```
Pensieve/
├── AGENTS.md              # this file
├── README.md              # public-facing pitch + quickstart
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
│   ├── sources/           # TaskSource implementations (READ-ONLY contract)
│   │   ├── base.py
│   │   ├── outlook_com.py # pywin32 Outlook COM source
│   │   └── sample_file.py # dev source against data/samples.json
│   ├── enrichment/
│   │   ├── llm_client.py  # port of Inbox Copilot Invoke-AzureOpenAI.ps1
│   │   ├── prompt.py      # loads prompts/enrich-memory-prompt.md
│   │   ├── connect_goals.py
│   │   └── enricher.py
│   ├── store/
│   │   ├── schema.py      # Memory + Vial Pydantic models
│   │   └── chroma.py      # ChromaMemoryStore (PersistentClient)
│   └── api/
│       └── server.py      # FastAPI + StaticFiles mount for the dashboard
│
├── frontend-proto/        # HP-themed kanban dashboard
│   ├── index.html
│   ├── pensieve.js        # vanilla JS; fetches from API; in-card edit modal
│   ├── pensieve.css       # 3 themes (parchment / night / marauder), Houses, polish
│   └── README.md
│
├── data/                  # local-only data
│   ├── samples.json       # canned tasks + strand catalog
│   ├── connect-goals.json # canonical Connect-Goal catalog
│   ├── chroma/            # ChromaDB persistent store (gitignored)
│   └── audit-log.jsonl    # one line per sync action (gitignored)
│
├── prompts/
│   ├── enrich-memory-prompt.md      # v2 (Connect-aware) — used by Phase 1
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
└── tests/                 # pytest suite (15 tests)
    ├── conftest.py
    ├── test_sources.py    # read-only contract enforcement
    ├── test_store.py      # Chroma upsert/idempotent/search/column-update
    └── test_enrichment.py # prompt + goals + payload shape
```

Phase 0 PowerShell scripts are kept under `scripts/` as legacy. The Python
package under `pensieve/` is now the canonical entry point; PowerShell is
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

# pull Andy's real To-Do via Outlook COM, enrich, persist to ChromaDB
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

## Session protocols

### At session START in this folder

When a new session's `cwd` is this folder (or a child), on the first
tool-using turn:

1. Surface the latest Pensieve sessions (TODO: add `.copilot/session-start.ps1`
   matching the Inbox Copilot pattern).
2. Read the most recent Pensieve session note in
   `C:\Andy Herman\Luna Master\AI Agents - Copilot\Sessions\`.
3. Read the project landing page at
   `C:\Andy Herman\Luna Master\AI Agents - Copilot\Projects\Pensieve.md`.
4. Summarize recent context to Andy and offer continuation.

### At session END (or auto-save trigger)

Per the global Copilot Instructions vault-aligned-sessions rule:

1. Write a session note to
   `C:\Andy Herman\Luna Master\AI Agents - Copilot\Sessions\YYYY-MM-DD_pensieve_<short-description>.md`.
2. Append any decisions to
   `C:\Andy Herman\Luna Master\AI Agents - Copilot\Memory\Decisions Log.md`
   with `[Pensieve]` prefix.
3. Update the project landing page (session log, status, `updated:` frontmatter).
4. Cross-link the session note from the project page.

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

## Related projects

- **[../CISO GRC/AGENTS.md](../CISO%20GRC/AGENTS.md)** — the ideation hub this
  project spun out of. The brainstorm seed lives at
  `..\CISO GRC\brainstorms\01-day-to-day.md`.
- **[../Inbox Copilot/AGENTS.md](../Inbox%20Copilot/AGENTS.md)** — sibling
  spinout. Re-use its Phase 0 helpers (`scripts/lib/Load-DotEnv.ps1`,
  `scripts/lib/Invoke-AzureOpenAI.ps1`).
- **[../Synapse/CLAUDE.md](../Synapse/CLAUDE.md)** — downstream consumer of
  Pensieve's Reflections (Promo Coach evidence pipeline).

---

## Conventions

- **No em-dashes** in generated content (matches Synapse / Agent-F rule).
- **Complete file replacements** preferred over partial diffs for tight
  scaffolding work; surgical edits otherwise.
- **One ship gate per phase** — see `PHASES.md`. Don't start Phase N+1 until
  Phase N's gate is met.
- **Reversibility first** — any Phase that touches live To-Do must have an
  undo path documented before it ships.
