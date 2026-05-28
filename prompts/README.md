# Pensieve prompts

System prompts used by Pensieve when calling the LLM. One prompt per file, named for its lifecycle stage. All prompts target Azure OpenAI `gpt-5.4-2` via the Cortex hub (`https://agents-wus3-02.services.ai.azure.com/`, keyless via `DefaultAzureCredential`).

## Files

| File | Phase | Stage | Status |
|---|---|---|---|
| `enrich-memory-prompt.md` | Phase 0 / 1 | Memory enrichment (why / strand / impact / Connect-goal alignment from a To-Do task) | **Live (v2 Connect-aware, 2026-05-28)** |
| `extract-connect-goals.md` | Phase 1 | Goals importer: extract structured Connect goals from an uploaded Connect PDF | **Live (2026-05-28)** |
| `reverie-proposal-prompt.md` | Phase 2.5 | Reverie planner: propose 1-3 focus-block Reveries from user-selected memories | Pre-staged 2026-05-28 |
| `reverie-debrief-prompt.md` | Phase 2.5 | Reverie debrief: convert user reply into structured "actual memories advanced" + impact seeds + unplanned-work captures | Pre-staged 2026-05-28 |
| `reflection-synthesis-prompt.md` | Phase 3 | Reflection synthesis (weekly / monthly / H1 / H2) | Not yet authored |
| `vial-distill-prompt.md` | Phase 3 | Vial distillation: a closed Memory's impact statement, IC4 to IC5 framed | Not yet authored |

## Conventions for all prompts

- Single JSON object output, no surrounding prose, no markdown fences.
- No em-dashes in any text field returned by the LLM. Hyphens, colons, commas, periods only.
- LLM must never invent IDs. Only IDs that appear in the input may be referenced in the output.
- Settings: omit `temperature` (use model default), set `response_format = {"type": "json_object"}`, set `max_completion_tokens` per-prompt (documented in each file).
- A confidence field (`0.0` to `1.0`) is required on any output that drives a user-facing surface (Reverie proposals, Vial drafts, etc.). Pensieve hides outputs below 0.5 by default.

## Caller responsibilities (NOT the LLM's job)

- Token / credential acquisition via `DefaultAzureCredential` with the `https://cognitiveservices.azure.com/.default` scope.
- Schema validation of LLM output before persistence.
- Real calendar scheduling via Microsoft Graph `findMeetingTimes` and `POST /me/events` (Phase 2.5; not yet wired). The LLM proposes intent; Pensieve handles the calendar API.
- Cross-referencing returned IDs against the local ChromaDB store.
- Logging the prompt + completion via the `logger` MCP for later eval / regression analysis.

## Versioning

Prompts evolve. Each prompt file's first line carries a `version: vN` marker. Pensieve includes the prompt version in telemetry on every call so a later eval run can attribute quality changes to a specific prompt revision.
