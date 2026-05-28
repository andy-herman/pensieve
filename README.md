# Pensieve

> *"I use the Pensieve. One simply siphons the excess thoughts from one's mind, pours them into the basin, and examines them at one's leisure."* — Dumbledore

A memory store for your work. Pensieve enriches Microsoft To-Do tasks with the context To-Do can't hold — *why* you opened them, *which project* they belong to, *what changed* when they closed, *what impact* they had — and gives you a kanban view to dive back into. At semi-annual review time, the captured memories become structured input for your IC4→IC5 narrative, exported directly to [Synapse Promo Coach](../Synapse/CLAUDE.md).

- **Status:** Phase 0 scaffolding (2026-05-28).
- **Spun out from:** [CISO GRC pillar 1 — day-to-day](../CISO%20GRC/brainstorms/01-day-to-day.md).
- **Owner:** Andy Herman (CISO org).
- **Vault landing page:** `C:\Andy Herman\Luna Master\AI Agents - Copilot\Projects\Pensieve.md`.

## Why

Microsoft To-Do is excellent at *capture* and terrible at *memory*. You type "fix the thing" at 4pm Tuesday; two weeks later "fix the thing" is meaningless. By H1 promo review there's no record of what mattered. Pensieve solves that without taking To-Do away from you.

## What it does (MVP)

| Phase | Ships |
|---|---|
| **0** | Local PowerShell enrichment of canned To-Do samples (dry-run, no live Graph) |
| **1** | Live Graph → read tasks → enrich → write back to the Notes field |
| **2** | SQLite memory store + local kanban web view |
| **2.5** | **Reverie** — propose tentative focus-block events on your calendar from selected open memories; round-trip captures what you actually advanced |
| **3** | Reflection export → Synapse Promo Coach format |

See [`PHASES.md`](./PHASES.md) for the full plan and [`SPEC.md`](./SPEC.md) for the product spec.

## Hard constraints

- **No external LLMs.** Azure OpenAI or M365 Copilot only. Same constraint as Inbox Copilot.
- **Reversibility in Phase 0/1.** No task is modified without a user-visible diff.
- **Phase 0 must work without live Graph** (corp Conditional Access still blocks the built-in `Microsoft.Graph` PS SDK app for Andy's account).

## Concepts

| Term | What it is |
|---|---|
| **Memory** | An enriched task record (title + original notes + LLM-extracted *why* / *impact* / *project link*) |
| **Strand** | A project or workstream a memory belongs to (the silver threads in Dumbledore's Pensieve) |
| **Dive** | Viewing memories from a time window, filtered by strand / impact / status |
| **Reverie** | A calendar-blocked focus session scheduled to work on selected memories — Pensieve proposes, you confirm before any event is written |
| **Reflection** | A synthesis of memories for a review period — feeds the perf-review narrative |
| **Vial** | A single closed task's impact statement, ready to hand off to Synapse Promo Coach |

## Running Phase 0 (when scripts land)

```powershell
cd "C:\Andy Herman\Coding Projects (Local)\Pensieve"
# (planned) — dry-run enrichment of canned samples
.\scripts\Enrich-Memories.ps1 -DryRunSampleFile .\data\samples.json
```

## Related projects

- **[CISO GRC](../CISO%20GRC/AGENTS.md)** — the ideation hub Pensieve spun out of.
- **[Inbox Copilot](../Inbox%20Copilot/README.md)** — sibling spinout from pillar 2. Same architectural choices.
- **[Synapse](../Synapse/CLAUDE.md)** — Pensieve's downstream consumer. Reflections become Synapse journal entries / Promo Coach evidence.
- **Agent C** (Neural Work Logger) — Andy's existing ADO-side pattern. Pensieve is the To-Do half; eventual unification is on the table.

## See also (internal)

- Agency CLI: [Reference](../../Luna%20Master/AI%20Agents%20-%20Copilot/Reference/Agency%20CLI%20Reference.md).
- Vault session lifecycle and protocols: this repo's `AGENTS.md`.
