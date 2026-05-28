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
  OpenAI (Cortex hub `https://agents-wus3-02.services.ai.azure.com/`,
  deployment `gpt-5.4-2`, keyless via `DefaultAzureCredential`) or
  Microsoft 365 Copilot via MCP. Never an external endpoint. Inherited
  from the CISO GRC pillar 1 constraint and matched to Inbox Copilot and
  Synapse for consistency.
- **Reversibility in Phase 0/1.** No task is modified without a
  user-visible diff. Phase 0 is dry-run only.
- **Phase 0 must work without live Graph.** Corp Conditional Access blocks
  the built-in `Microsoft.Graph` PS SDK app on Andy's account
  (verified 2026-05-22 in the Inbox Copilot session — same problem here).
  Phase 0 operates against canned task samples; Phase 1 unblocks Graph.

---

## Tech stack (planned)

| Layer | Choice | Why |
|---|---|---|
| Phase 0 entry | PowerShell + dotenv-style `.env` | Matches Inbox Copilot Phase 0 — fastest path to validating enrichment quality |
| LLM (all phases) | Azure OpenAI `gpt-5.4-2` via Cortex hub, keyless | Same as Argus + Synapse |
| Phase 1 Graph access | Microsoft Graph SDK (Python) or Graph REST direct | Tied to Graph-unblock decision (see [`OPEN-QUESTIONS.md`](./OPEN-QUESTIONS.md)) |
| Phase 2 backend | Python 3.12 + FastAPI + Uvicorn + Pydantic v2 | Matches Argus / Synapse / Inbox Copilot |
| Phase 2 store | SQLite (memories, strands, vials, reflections) | Matches Synapse `agent_i.db` pattern |
| Phase 2 UI | React 18 + Vite (kanban view, localhost-only) | Matches frontend_shell pattern |
| Phase 4 polish (post-MVP) | Tauri v2 desktop shell | Matches Argus + Synapse packaging |
| Telemetry | App Insights via `logger` MCP / SDK | Inherited from baseline |

---

## Repo layout (current + planned)

```
Pensieve/
├── AGENTS.md              # this file
├── README.md              # one-page pitch + how to run
├── SPEC.md                # authoritative product spec
├── PHASES.md              # Phase 0–3 plan
├── OPEN-QUESTIONS.md      # known unknowns + decision triggers
├── agency.toml            # Agency MCP config (baseline + Pensieve-specific)
├── .env.example           # Azure OpenAI env vars
├── .gitignore
│
├── data/                  # (planned) canned task samples, exported reflections
│   └── samples.json
├── prompts/               # enrichment / Reverie / reflection prompt files
│   ├── README.md          # index + conventions for all prompts
│   ├── reverie-proposal-prompt.md   # Phase 2.5, pre-staged 2026-05-28
│   ├── reverie-debrief-prompt.md    # Phase 2.5, pre-staged 2026-05-28
│   └── enrich-memory-prompt.md      # (planned, Phase 0)
├── scripts/               # (planned) Phase 0 PowerShell pipeline
│   ├── Enrich-Memories.ps1
│   └── lib/
│       ├── Load-DotEnv.ps1
│       └── Invoke-AzureOpenAI.ps1
└── src/                   # (planned, Phase 2+) Python backend
```

`scripts/lib/` mirrors Inbox Copilot's helper layout so the dotenv loader and
Azure OpenAI REST wrapper can be lifted verbatim.

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
