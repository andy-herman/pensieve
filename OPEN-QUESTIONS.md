# Pensieve — Open Questions

Decisions deferred to a specific phase or specific data point. Update as
they resolve; don't delete — leave the resolved trail so the next session
can see what was tried.

---

## Q1 — Graph unblock path (blocks Phase 1)

**Status:** Open. Same blocker as Inbox Copilot Phase 1.

**Background:** Microsoft Graph PS SDK app (`14d82eec-204b-4c2f-b7e8-296a70dab67e`)
is blocked by corp Conditional Access for Andy's account. Verified
2026-05-22 in the Inbox Copilot session.

**Three paths:**

| Path | Time to unblock | Sustainability |
|---|---|---|
| Custom Entra app registration via corp onboarding | Days of admin-consent turnaround | High — long-term right answer |
| Azure CLI client minting Graph tokens | Hours | Depends on whether pre-consented scope includes `Tasks.ReadWrite` |
| Wait for built-in PS SDK to be allow-listed | Indefinite, not under our control | Not viable |

**Decision trigger:** Before Phase 1 kickoff.

**Tasks.ReadWrite probe (do this first):**
```powershell
$token = az account get-access-token --resource https://graph.microsoft.com `
    --query accessToken -o tsv
# Decode the JWT scp claim and check for Tasks.ReadWrite / Tasks.Read
```
If the scope is present, Path 2 is viable for now. If not, file the
Entra app registration and proceed Path 1.

---

## Q2 — Where does enriched detail live?

**Status:** Open. Affects Phase 1 + Phase 2 design.

**Options:**

| Option | Pro | Con |
|---|---|---|
| **A. To-Do Notes field only** (round-trip) | Visible in native To-Do UI; survives if Pensieve dies | Notes field is plain text; no structure; size limits; hard to query |
| **B. SQLite only** (Pensieve never writes back) | Clean schema; full structure; fast queries | Enrichment invisible inside To-Do — defeats half the value |
| **C. Both** — SQLite is canonical, Notes mirrors a subset | Best of both | Sync complexity; potential drift |

**Leaning:** (C). Notes mirror = title + why + strand. SQLite = everything
including closure_context, impact, vial. Mirror is one-way (Pensieve → To-Do
Notes); Notes are not parsed back. This means manual Notes edits in To-Do
are lost on next sync — needs a sentinel comment so Pensieve can detect
"user wrote here" and skip overwrite.

**Decision trigger:** Phase 1 design.

---

## Q3 — Sync cadence

**Status:** Open. Affects Phase 1 ops.

**Options:**

- **Manual** — Andy runs `Enrich-Memories.ps1` when he wants. Simple, no
  background process.
- **Scheduled** — Windows Task Scheduler entry running every 15 minutes.
- **Webhook** — Graph subscription on `/me/todo/lists/{lid}/tasks`. Real
  time but requires Phase 2 backend to receive callbacks. Post-MVP.

**Leaning:** Manual for Phase 1; Scheduled for Phase 2; Webhook for Phase 6.

---

## Q4 — Closure prompt UX

**Status:** Open. Affects Phase 1 ship gate.

When a To-Do task is marked done, when does Pensieve prompt Andy for the
closure context + impact statement?

- **At sync time, batch** — all tasks closed since last sync get prompted
  at once. Easy to skip; can pile up.
- **End-of-day batch** — one daily prompt covering today's closures. Lower
  friction; impact memory still fresh.
- **At closure time** — requires webhook (Post-MVP).

**Leaning:** End-of-day batch for Phase 1; webhook for Phase 5+.

---

## Q5 — Strand catalog management

**Status:** Open. Affects Phase 2.

How does the strand catalog get bootstrapped?

- **All LLM-suggested** — every new memory triggers a strand suggestion;
  catalog grows organically. Risk: too many near-duplicate strands.
- **Manual seed + LLM extension** — Andy seeds 8–12 strands (his
  current workstreams + promo themes), LLM proposes additions when none
  fit.
- **Pulled from ADO projects** — strands mirror ADO area-paths Andy works
  in. Tight integration with Agent C lineage.

**Leaning:** Manual seed + LLM extension. Seed list: `dora-rfi`,
`uk-ctp-self-assessment`, `nis2-mapping`, `inbox-copilot-build`,
`pensieve-build`, `argus-build`, `synapse-build`, `1on1-prep`,
`team-mgmt`, `learning`, `ic5-promo-evidence`, `ops-chores`.

---

## Q6 — Reflection export integration with Synapse

**Status:** Open. Affects Phase 3.

Options for getting Vials into Synapse Promo Coach:

- **Direct DB write** — Pensieve writes to Synapse's `data/agent_i.db`
  `journal_entries` table. Tight coupling; brittle if Synapse schema
  changes.
- **POST to `/api/neural/log`** — Synapse's existing ingest endpoint. Clean
  contract; Synapse owns its DB. Need to verify the endpoint accepts the
  fields a Vial carries.
- **Markdown export → drag into Synapse Feed** — laziest path; Andy is the
  glue. Good Phase 3 starting point; upgrade later.

**Leaning:** Markdown export (Phase 3 v1) → POST to `/api/neural/log`
(Phase 3 v2). Read Synapse's `api/routes/neural.py` before committing.

---

## Q7 — Pensieve backend port

**Status:** Open. Trivial but needs a single source of truth.

- Inbox Copilot: TBD (no backend yet, probably `:8000` Phase 2+).
- Argus: `:8000`.
- Synapse: `:8420`.

**Decision:** Pensieve = `:8440` (skips `:8430` to leave Pensieve and Inbox
Copilot adjacent if Inbox Copilot lands on `:8430`).

---

## Q9 — Reverie proposal aggressiveness (blocks Phase 2.5)

**Status:** Open. Affects Phase 2.5 ship gate.

How aggressive should the daily Reverie suggester be?

| Stance | Behavior |
|---|---|
| **Quiet** | Only proposes Reveries when user multi-selects memories and clicks "Schedule a Reverie". No daily suggestions. |
| **Daily nudge** | Background loop suggests up to 3 Reveries per day for the highest-priority open memories. Banner on kanban; no auto-write. |
| **Calendar-aware** | Same as daily nudge but also looks at calendar density — if user has > N hours of meetings tomorrow, suppress suggestions; if user has > N hours of open time, suggest more. |

**Leaning:** Start at **Daily nudge**. Add **Calendar-aware** if Andy
finds Daily nudge proposes Reveries that get instantly bumped by
meetings. Quiet is too passive for the cockpit feel.

**Decision trigger:** First week of Phase 2.5 dogfooding.

---

## Q10 — Viva Insights Focus Time integration (Phase 2.5 stretch)

**Status:** Open. Affects Phase 2.5 polish layer.

Microsoft Viva Insights has a built-in **Focus Time** calendar category
that automatically silences Teams notifications + auto-replies with
"focusing now" during the block. Should Pensieve Reveries piggy-back on
this?

| Option | Pro | Con |
|---|---|---|
| **Plain calendar events** | Simple — just `POST /me/events` with `categories: ["Pensieve"]` | No silencing benefit; collides with manual Focus Time blocks |
| **Tagged as Focus Time** | Free Teams / notification suppression | Tenant must have Viva Insights provisioned (verify for Andy's tenant); Focus Time categorization API may be Insights-API-only, not core Graph |
| **Both — user toggle** | Best of both | More UI; more code |

**Leaning:** Plain calendar events for first ship; add Focus Time
tagging as a toggle if Andy asks for it after using the plain version
for a week.

**Decision trigger:** Phase 2.5 v1 → after one-week dogfood.

---

## Q11 — Reverie default duration per strand

**Status:** Open. Trivial seed, but worth committing.

Each strand has a `default_reverie_minutes` field (`SPEC.md` section 6).
Seed values:

| Strand archetype | Default minutes | Why |
|---|---|---|
| `dora-rfi`, `uk-ctp-self-assessment`, `nis2-mapping` (deep regulatory work) | 90 | Context-switch heavy; needs runway |
| `inbox-copilot-build`, `pensieve-build`, `argus-build`, `synapse-build` (coding) | 90 | Same — coding needs runway |
| `1on1-prep`, `team-mgmt` | 30 | Short tactical items |
| `learning` | 60 | Reading / training videos |
| `ic5-promo-evidence` | 45 | Writing reflection prose |
| `ops-chores` | 25 | Pomodoro-style |

**Decision trigger:** Implement these as defaults; let the UI override
per Reverie.

---

## Q8 — Does Pensieve need its own Microsoft.Graph SDK install, or can it share with Inbox Copilot?

**Status:** Open. Affects Phase 1 dev ergonomics.

Both projects need the same Graph SDK + auth flow. Three options:

- **Per-project venv** (current Inbox Copilot pattern) — full isolation.
- **Shared `.venv`** at `Coding Projects (Local)\.venv\` — one Graph SDK
  install, used by both. Risk: version skew across projects.
- **Lift the helpers into a tiny shared package** at
  `Coding Projects (Local)\shared\graph_helpers\` — clean, but introduces a
  cross-project dependency surface for the first time.

**Leaning:** Per-project venv for Phase 0–1 (zero coupling); revisit when
Phase 7 (Agent C unification) is on the table.
