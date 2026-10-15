@AGENTS.md

# Pensieve, hard rules for AI sessions

The import above inlines AGENTS.md, the authoritative agent guide. Read it. Even if you skim it, the following are non-negotiable:

- LLM calls go through GitHub Copilot on this branch: every classification or generation call uses get_chat_client(), whose default provider is github_copilot (Copilot SDK, tools disabled, sessions deleted) under the Copilot sign-in from the Accounts screen or the GitHub login pinned in COPILOT_GITHUB_USER. Azure OpenAI and GitHub Models are the only other allowed providers. Never add any other endpoint.
- Sources are read-only. TaskSource implementations (pensieve/sources/outlook_com.py and every other source) have zero mutation methods, enforced by tests/test_sources.py::test_sources_are_read_only_no_write_methods. Never add save, update_task, patch, delete_task, set_notes, or create_task to a source class.
- Writeback only via the namespaced TaskSink. The separate TaskSink interface (pensieve/sources/sink.py) is opt-in via PENSIEVE_MIRROR_TO_SOURCE and only touches Categories entries starting with the configured pensieve/col: prefix. User-authored categories are preserved byte for byte. Completion mirroring is a second, separately gated flag (PENSIEVE_MIRROR_COMPLETION, default off) and is one-way, close only.
- The one additive exception: voice capture (pensieve/capture/, deliberately outside pensieve/sources) may CREATE a new task in the user's own list, only after they confirm it in the dashboard and only while PENSIEVE_ALLOW_TASK_CREATE is on. It never edits, completes, or deletes an existing task.
- Reversibility for any writeback. Clearing the mirror tag restores the source task exactly to its pre-Pensieve state. No sink ever mutates Notes, Body, Subject, or Due Date.
- No corporate Microsoft Graph and no app registrations in Microsoft's corporate tenant (SFI locks down corp app consent), so work tasks come from local Outlook COM via pywin32. The one Graph path allowed is personal Microsoft accounts in To Do (Tasks.ReadWrite: sync only reads, voice capture only adds confirmed new tasks) through pensieve/connections.py, using an app registration in a personal Entra directory (see desktop/SHARING.md).
- All data stays local. ChromaDB persists to data/chroma/. Network egress is limited to the configured LLM provider (GitHub Copilot by default), Microsoft Graph for a connected personal To Do account, and the browser's speech service while dictating a task. The vault bridge only writes local files (Agents/Pensieve/Now.md and the status of `to: pensieve` request notes); Obsidian Sync, not Pensieve, moves them.
- No em-dashes in any generated content. Anonymize anything committed to sample data, tests, or prompt examples (role labels, not real people or employer-internal names); this repo is public.

## Quick orientation

- App code lives in the pensieve/ package (Typer CLI in pensieve/cli.py, FastAPI in pensieve/api/server.py). The dashboard is vanilla HTML/CSS/JS in frontend-proto/. scripts/ is legacy Phase 0 PowerShell; do not extend it.
- Tests: activate .venv, pip install -e .[dev], then run pytest from the repo root. tests/test_sources.py guards the read-only contract; keep it green.
- Run: pensieve sync --source outlook_com (or --source sample_file for dev), then pensieve serve --port 8765 and open http://localhost:8765/, or build the desktop app with desktop/build.ps1.
- Phase status: Phase 1 shipped 2026-05-28 and is the daily-driver state. Phase 2 (Vials) v1 MVP is shipped. Phase 2.5 (Reverie) and Phase 3 are planned. Phase 4 calendar work is parked on the SFI timeline.
- One ship gate per phase; see PHASES.md. Do not start Phase N+1 until Phase N's gate is met.
