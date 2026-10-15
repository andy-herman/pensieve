# Pensieve prompts

System prompts Pensieve sends to the LLM. One prompt per file, named for its lifecycle stage. Every call goes through `get_chat_client()` (`pensieve/enrichment/chat_provider.py`), so the prompts run on whichever provider is configured: GitHub Copilot by default, with the model picked per purpose in the dashboard's **AI models** panel (`pensieve/ai_prefs.py`). Azure OpenAI and GitHub Models are the fallback providers.

## Files

| File | Phase | Stage | Model purpose | Status |
|---|---|---|---|---|
| `enrich-memory-prompt.md` | Phase 1 | Memory enrichment (why / strand / impact / Connect-goal alignment from a To-Do task), used by sync and Regenerate | `enrichment` | Live (v2) |
| `extract-connect-goals.md` | Phase 1 | Goals importer: structured Connect goals from an uploaded Connect PDF | `goals` | Live |
| `connect-recap-prompt.md` | Phase 1+ | Connect recap: one accomplishments block per goal (also used by per-section Revise) | `recap` | Live |
| `reverie-proposal-prompt.md` | Phase 2.5 | Reverie planner: propose 1-3 focus-block Reveries from selected memories | n/a | Pre-staged, not wired |
| `reverie-debrief-prompt.md` | Phase 2.5 | Reverie debrief: user reply to advanced memories, impact seeds, unplanned work | n/a | Pre-staged, not wired |

Voice capture's prompt is short and lives inline in `pensieve/capture/parse.py` (model purpose `capture`).

## Conventions for all prompts

- Single JSON object output, no surrounding prose, no markdown fences. The Copilot client also strips stray fences before parsing.
- No em-dashes in any text field returned by the LLM, and none in the prompts themselves. Hyphens, colons, commas, periods only.
- The LLM must never invent IDs. Only IDs that appear in the input may be referenced in the output.
- Examples use role labels ("my manager", "a supplier contact") and generic team and program names. Never real people or employer-internal names: this repo is public.
- A confidence field (`0.0` to `1.0`) is required on any output that drives a user-facing surface. Below 0.5 means the user should review.

## Caller responsibilities (NOT the LLM's job)

- Choosing the provider and model, and authentication (Copilot sign-in in the Accounts screen, or the fallback provider's settings in `.env`).
- Parsing and validating the JSON before persistence.
- Cross-referencing returned IDs against the local ChromaDB store.
- Calendar scheduling for Reveries (Phase 2.5; not yet wired). The LLM proposes intent; Pensieve would handle the calendar API.

## Versioning

Prompts evolve. Each prompt file's first line carries a `version: vN` marker so a later eval run can attribute quality changes to a specific prompt revision.
