@AGENTS.md

# Pensieve, hard rules for AI sessions

The import above inlines AGENTS.md, the authoritative agent guide. Read it. Even if you skim it, the following are non-negotiable:

- No external LLMs. Every classification or generation call goes to Azure OpenAI (Cortex hub, deployment gpt-5.4-2, keyless via DefaultAzureCredential) or Microsoft 365 Copilot via MCP. Never any other endpoint.
- Sources are read-only. TaskSource implementations (pensieve/sources/outlook_com.py and every other source) have zero mutation methods, enforced by tests/test_sources.py::test_sources_are_read_only_no_write_methods. Never add save, update_task, patch, delete_task, set_notes, or create_task to a source class.
- Writeback only via the namespaced TaskSink. The separate TaskSink interface (pensieve/sources/sink.py) is opt-in via PENSIEVE_MIRROR_TO_SOURCE and only touches Categories entries starting with the configured pensieve/col: prefix. User-authored categories are preserved byte for byte. Completion mirroring is a second, separately gated flag (PENSIEVE_MIRROR_COMPLETION, default off) and is one-way, close only.
- Reversibility for any writeback. Clearing the mirror tag restores the source task exactly to its pre-Pensieve state. No sink ever mutates Notes, Body, Subject, or Due Date.
- No Microsoft Graph, no Entra app registrations. Microsoft SFI locks down corp app consent, so Phase 1 deliberately uses local Outlook COM via pywin32. Do not introduce Graph calls or app registrations.
- All data stays local. ChromaDB persists to data/chroma/. The only network egress is the Azure OpenAI enrichment call.
- No em-dashes in any generated content. Anonymize anything committed to sample data or prompt examples; this repo is public.

## Quick orientation

- App code lives in the pensieve/ package (Typer CLI in pensieve/cli.py, FastAPI in pensieve/api/server.py). The dashboard is vanilla HTML/CSS/JS in frontend-proto/. scripts/ is legacy Phase 0 PowerShell; do not extend it.
- Tests: activate .venv, pip install -e .[dev], then run pytest from the repo root. tests/test_sources.py guards the read-only contract; keep it green.
- Run: pensieve sync --source outlook_com (or --source sample_file for dev), then pensieve serve --port 8765 and open http://localhost:8765/.
- Phase status: Phase 1 shipped 2026-05-28 and is the daily-driver state. Phase 2 (Vials) v1 MVP is shipped. Phase 2.5 (Reverie) and Phase 3 are planned. Phase 4 calendar work is parked on the SFI timeline.
- One ship gate per phase; see PHASES.md. Do not start Phase N+1 until Phase N's gate is met.
