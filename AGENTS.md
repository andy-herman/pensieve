# Pensieve: AGENTS.md

Project-level context for AI coding agents (GitHub Copilot, Claude Code,
Cursor, etc.) working in this repo. Read this first; it summarizes the
architecture, conventions, and hard constraints so you don't have to
re-derive them from the code.

## Project intent

A magical bowl for your work. Pensieve sits on top of Microsoft To Do and
adds the memory layer To Do can't hold (why a task was opened, which
project / strand it belongs to, what changed when it closed, what impact
it had), then surfaces a kanban view. The captured memories feed a
downstream promo / self-reflection step at semi-annual review time.

See [`SPEC.md`](./SPEC.md) for the product spec and [`PHASES.md`](./PHASES.md)
for the phased build plan. This `personal-device` branch carries the Harry
Potter themed dashboard, the GitHub Copilot provider, and the desktop app.

---

## Hard constraints

- **LLM calls go through GitHub Copilot (this `personal-device` branch).**
  Every classification or generation goes through `get_chat_client()`;
  the default provider is `github_copilot` (official GitHub Copilot SDK,
  `pensieve/enrichment/copilot_client.py`). Identity is the Copilot CLI
  sign-in from the Accounts screen, or the GitHub login pinned in
  `COPILOT_GITHUB_USER`; either way it must be an account whose Copilot
  license may process this data (for work tasks, the company-managed
  account). Sessions run with every tool disabled and are deleted after
  each call. Azure OpenAI and GitHub Models remain selectable via
  `LLM_PROVIDER`. Never add any other endpoint. Model choice per purpose is
  set in the dashboard (`pensieve/ai_prefs.py`, `data/ai-models.json`).
- **Sources are read-only.** `pensieve/sources/outlook_com.py` and every
  other `TaskSource` implementation has zero mutation methods. Enforced by
  a unit test (`tests/test_sources.py::test_sources_are_read_only_no_write_methods`)
  that asserts forbidden method names (`save`, `update_task`, `patch`,
  `delete_task`, `set_notes`, `create_task`) don't exist on any source
  class, and at edit time by `.claude/hooks/guard_sources.py`. Writeback to
  existing tasks lives behind a separate `TaskSink` interface in
  `pensieve/sources/sink.py` (opt-in via `PENSIEVE_MIRROR_TO_SOURCE`).
- **TaskSink writeback is namespace-scoped.** The column mirror tags the
  source task's `Categories` field with `pensieve/col:<column>` so a second
  PC syncing from the same mailbox sees the same kanban view.
  `OutlookCOMSink` in `pensieve/sources/outlook_com_sink.py` only touches
  categories whose string starts with the configured prefix. User-authored
  categories are preserved byte for byte. Conflict policy: source wins when
  the upstream `LastModificationTime` is newer than the local `enriched_at`.
  Completion remains terminal (a completed task lands in `closed` even if a
  remote mirror tag says otherwise).
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
- **Vault bridge for other agents** (`pensieve/bridge.py`). With
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
  single-writer constraint. It syncs `PENSIEVE_AUTO_SYNC_SOURCE` if set,
  else the source chosen in the Accounts screen
  (`pensieve.connections.effective_source`), and silently skips
  `sample_file`.
- **No corporate Microsoft Graph, no corporate app registrations.** SFI
  (late 2025+) requires admin consent for new corp Entra apps accessing
  `Tasks.*` / `Mail.*` / `Calendars.*` scopes; see
  [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1. Work tasks therefore come
  from local Outlook COM via `pywin32`. The one Graph path is personal
  Microsoft To Do: people connect their own personal Microsoft account in
  the dashboard's Accounts screen (`pensieve/connections.py`, device-code
  sign-in, DPAPI-encrypted token cache, `Tasks.ReadWrite` so voice capture
  can add tasks; sync only reads). The app registration lives in a personal
  Entra directory, never Microsoft's corporate tenant; see
  `desktop/SHARING.md`.
- **All data is local.** ChromaDB persists to `data/chroma/`. Network egress
  is limited to the configured LLM provider, Microsoft Graph for a connected
  personal To Do account, and the browser's speech service while dictating.
  The vault bridge only writes local files; Obsidian Sync, not Pensieve,
  moves them.
- **Sync deletion sweep is scoped.** A narrow sync (single list) can only
  delete memories whose `source + list_name` was actually covered by that
  sync. Never globally orphan-prune across all sources / lists. Closed
  memories are never orphaned, and the sweep is skipped when a source
  reports `read_errors`. See
  `pensieve/store/chroma.py::ChromaMemoryStore.find_orphan_ids`.
- **The local API stays locked down.** It binds `127.0.0.1`, a
  `TrustedHostMiddleware` refuses other host names (DNS rebinding), and when
  `Pensieve.exe` starts it with `PENSIEVE_SESSION_TOKEN`, every `/api/*` call
  except `/api/healthz` needs that launch's session cookie or header
  (`pensieve/api/security.py`). Every response carries a CSP that only runs
  the app's own scripts. Don't add open API paths or loosen the CSP.
- **Connect recaps are list-scoped by default.** Only tasks whose source
  `list_name` is in `PENSIEVE_RECAP_LIST_NAMES` (default `CISO GRC`)
  feed into `POST /api/recap`. Personal lists never end up in a work recap
  unless the operator explicitly overrides via the env var or per-call
  `list_names` body field. The filter is applied in
  `pensieve/recap.py::filter_by_list_names` before scope / goal grouping;
  the resolved allowlist is echoed back on the response as
  `list_names_applied` and written into the docx meta line so the user can
  see what fed in.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Primary stack | Python 3.12 + Typer CLI + FastAPI + Pydantic v2 | Small, local, testable |
| LLM | GitHub Copilot via the Copilot SDK (default `gpt-5.4`, changeable per purpose in the dashboard); Azure OpenAI / GitHub Models as fallbacks | Uses the Copilot license on the signed-in GitHub account; no keys in `.env` |
| Task sources | Classic Outlook desktop via `pywin32` COM (work), or personal Microsoft To Do via Graph; both **read-only** | SFI bypass for work; see [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md) Q1 |
| Memory store | **ChromaDB** `PersistentClient` at `data/chroma/` (cosine HNSW), unpadded MiniLM embedder, read cache keyed on SQLite `data_version` | Local-only, semantic search out of the box |
| Dashboard | Vanilla HTML/CSS/JS at `frontend-proto/`, Harry Potter themed on this branch (day parchment / night / Marauder easter egg; rendered art in `frontend-proto/assets/`), served by FastAPI StaticFiles | Small enough to stay framework-free; no build step |
| Desktop app | `desktop/Pensieve.exe` (C# launcher built with the in-box .NET Framework csc via `desktop/build.ps1`) starts the backend hidden and opens Edge in app mode | No SDK/Rust/Node toolchain needed; see `desktop/README.md` |
| Installer | `desktop/installer/` bundles the backend with PyInstaller and builds an x64 Inno Setup installer; installed copies keep data and `pensieve.env` under `%LOCALAPPDATA%\Pensieve` | Lets a friend run Pensieve without Python; see `desktop/SHARING.md` |
| Phase 0 (legacy) | PowerShell + dotenv in `scripts/` | Validated enrichment quality; kept for reference only |

---

## Repo layout (current)

```
Pensieve/
├── AGENTS.md / CLAUDE.md  # agent rules (CLAUDE.md imports this file)
├── README.md              # overview, writeback summary, configuration
├── SETUP.md               # install + first run
├── SETUP-personal-device.md  # GitHub Models fallback, separate boards
├── SPEC.md / PHASES.md / OPEN-QUESTIONS.md
├── agency.toml            # Agency MCP config
├── LICENSE                # MIT
├── pyproject.toml / .env.example
│
├── pensieve/
│   ├── cli.py             # Typer CLI: init / sync / status / search / serve / goals / lists
│   ├── config.py          # pydantic-settings .env loading
│   ├── connections.py     # Accounts screen: Microsoft + Copilot sign-in, source choice
│   ├── ai_prefs.py        # per-purpose model choice (AI models panel)
│   ├── bridge.py          # Obsidian vault bridge (Now.md + agent task requests)
│   ├── sync.py            # orchestrator: sources → enrichment → ChromaDB
│   ├── sync_state.py      # single-job tracker / atomic gate
│   ├── scheduler.py       # AutoSyncScheduler + start_sync_job
│   ├── garden.py, quests.py, quest_state.py, achievements.py, achievement_state.py  # Garden v1-v3
│   ├── recap.py, recap_export.py, recap_history.py  # Connect recaps
│   ├── graph.py           # Constellation graph payload
│   ├── docs_store.py      # in-app markdown docs
│   ├── capture/           # voice capture: parse.py (draft), creators.py (create NEW tasks)
│   ├── sources/           # TaskSources (READ-ONLY) + the opt-in TaskSink
│   │   ├── base.py, sample_file.py, outlook_com.py, personal_graph.py
│   │   └── sink.py, outlook_com_sink.py
│   ├── enrichment/
│   │   ├── chat_provider.py   # get_chat_client(): provider factory
│   │   ├── copilot_client.py  # GitHub Copilot SDK client (default)
│   │   ├── llm_client.py      # Azure OpenAI fallback
│   │   ├── github_models_client.py  # GitHub Models fallback
│   │   ├── enricher.py, prompt.py, connect_goals.py
│   │   └── goals_importer.py  # Connect PDF → goals + 8-lane palette
│   ├── store/
│   │   ├── schema.py      # Memory + Vial Pydantic models
│   │   ├── chroma.py      # ChromaMemoryStore
│   │   ├── vials.py       # ChromaVialStore (closure-capture; outlives Memories)
│   │   ├── embedding.py   # shared unpadded MiniLM embedder
│   │   └── read_cache.py  # whole-collection read cache
│   └── api/
│       ├── server.py      # FastAPI routes + StaticFiles mount for the dashboard
│       └── security.py    # session token, CSP and security headers
│
├── frontend-proto/        # HP-themed dashboard (index.html, pensieve.js, pensieve.css, assets/)
├── desktop/               # Pensieve.exe launcher source, build + icon scripts, installer/, SHARING.md
├── prompts/               # LLM system prompts (see prompts/README.md)
├── tools/                 # optional backend auto-start helpers
├── scripts/               # LEGACY Phase 0 PowerShell + backfill_mirror_tags.py
├── data/                  # samples.json + connect-goals.json (anonymized); runtime data gitignored
└── tests/                 # pytest suite; test_sources.py guards the read-only contract
```

---

## Canonical commands

```powershell
# one-time setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]

# verify config (provider, model, task source)
pensieve init

# pull tasks, enrich, persist to ChromaDB
pensieve sync                         # source chosen in Accounts, else .env
pensieve sync --source outlook_com
pensieve sync --source sample_file    # dev sample file

# inspect what's in the store
pensieve status
pensieve search "DORA regulator"
pensieve goals

# run the dashboard
pensieve serve --port 8765            # http://localhost:8765/
.\desktop\build.ps1                   # or build Pensieve.exe

# checks
pytest -q
ruff check pensieve tests
```

---

## Running Agency in this project

```powershell
agency copilot                          # default profile (Phase 0 baseline)
agency copilot --profile phase0         # explicit Phase 0 (Graph disabled)
agency copilot --profile phase1         # live Graph for To-Do CRUD
agency copilot --profile phase2         # + kanban dev
agency copilot --profile reverie        # Phase 2.5, calendar focus-block work
agency copilot --profile promo-feed     # + promo export work
agency config list --show-source        # verify config + provenance
```

See [`agency.toml`](./agency.toml) for the full MCP set per profile.

---

## Conventions

- **No em-dashes** in generated content. Use commas, periods, or hyphens with spaces.
- **US English.**
- **Complete file replacements** preferred over partial diffs for tight
  scaffolding work; surgical edits otherwise.
- **One ship gate per phase**: see `PHASES.md`. Don't start Phase N+1 until
  Phase N's gate is met.
- **Reversibility first**: any change that touches live To Do must have an
  undo path documented before it ships.
- **Anonymize sample data.** Anything committed to `data/samples.json`,
  `data/connect-goals.json`, frontend seed memories, tests, or prompt
  examples must use generic role labels (`manager`, `direct report`, `peer`,
  `supplier contact`) and generic team and program names, not real people or
  internal-org-specific identifiers. No credentials or real task content.
  This repo is public.
