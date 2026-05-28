# Pensieve — Open Questions

Decisions deferred to a specific phase or specific data point. Update as
they resolve; don't delete — leave the resolved trail so the next session
can see what was tried.

---

## Q1 — Graph unblock path (was: blocks Phase 1)

**Status:** CLOSED 2026-05-28 — Phase 1 architecturally bypassed Graph entirely via local Outlook COM. Question remains open for Phase 2 writeback and Phase 2.5 Reverie, but no longer blocks shipping.

**Background:** Microsoft Graph PS SDK app (`14d82eec-204b-4c2f-b7e8-296a70dab67e`) is blocked by corp Conditional Access for Andy's account (verified 2026-05-22 in Inbox Copilot session).

**Three paths evaluated:**

| Path | Result | Notes |
|---|---|---|
| Custom Entra app registration via corp onboarding | **Blocked under SFI for FTE self-service.** | Late-2025+ Microsoft Security Future Initiative tightened delegated `Tasks.*` / `Mail.*` / `Calendars.*` scopes — corp Entra app reg requires admin consent and FTE self-service is locked down. Long-term right answer if admin consent eventually lands; not viable as ship-blocker for Phase 1. |
| Azure CLI client minting Graph tokens | **Dead.** | Reconfirmed 2026-05-28 via JWT decode: `az account get-access-token --resource https://graph.microsoft.com` returns a token from the Azure CLI client (`appid: 04b07795-8ddb-461a-bbee-02f9e1bf7b46`) whose `scp` claim contains only admin-style scopes (Application.ReadWrite.All, Group.ReadWrite.All, User.ReadWrite.All, Directory.AccessAsUser.All, AuditLog.Read.All, AppRoleAssignment.ReadWrite.All, DelegatedPermissionGrant.ReadWrite.All, openid, profile, email). **Zero** Tasks-, Mail-, or Calendar-related scopes. |
| Wait for built-in PS SDK app to be allow-listed | **Not viable.** | Not under our control. |

**Phase 1 decision (2026-05-28):** **Pivot Phase 1 to local Outlook COM via pywin32.** Outlook desktop already authenticates against the corp tenant for the user; COM gives Pensieve the same task data Graph would, with zero auth surface and zero tenant-policy dependency. `pensieve/sources/outlook_com.py` ships read-only (no `.Save()` calls anywhere; enforced by a unit test that asserts forbidden method names don't exist on any source class).

**Phase 2 + Phase 2.5 implications:**

- **Writeback (Phase 2)** will likely use Outlook COM `.Save()` on the TaskItem (same auth surface that Phase 1 proves works). Sentinel-guarded so user-edited Notes are never overwritten.
- **Calendar (Phase 2.5)** will likely use Outlook COM `AppointmentItem` rather than Graph `POST /me/events`. Personal MSA fallback remains an option for personal-calendar dogfooding.
- **Corp Entra app reg** stays on the long-term roadmap but is not on the critical path for any phase.

---

## Q12 — When (if ever) do we revisit Graph-based writeback?

**Status:** Open. Affects Phase 2.

Phase 1 ships entirely on local Outlook COM. Phase 2 writeback can either:

- **Stay on COM** — same auth surface, no admin-consent dependency, no SFI risk. Limits Pensieve to machines with Outlook desktop installed.
- **Add a Graph path behind a feature flag** — would unlock headless / non-Outlook-desktop machines and a future team rollout. Requires admin-consent unblock or alternative.

**Decision trigger:** When Andy hits a "I want to use Pensieve from a machine without Outlook desktop" moment, or when the team rollout (Phase 6) starts.

---

## Q13 — Calendar integration approach when Phase 2.5 lands

**Status:** Open. Affects Phase 2.5.

Same architectural fork as Q12 but for calendar:

- **Outlook COM `AppointmentItem`** — same SFI-safe path Phase 1 uses for tasks. Likely default.
- **Graph `POST /me/events`** — only if Q1 corp Entra app reg eventually lands. Better for Reverie suggestions that need calendar-density awareness via `findMeetingTimes`.

**Decision trigger:** Start of Phase 2.5 design.

---

## Q2 — Where does enriched detail live?

**Status:** RESOLVED 2026-05-28 — **Option C (both), with Phase 1 shipping the local half only.**

Memories live canonically in ChromaDB (`data/chroma/memories` collection). Phase 1 does NOT mirror back to To-Do Notes — keeps the read-only-source contract. Phase 2 will add a sentinel-guarded mirror (`why` + `strand` only) so the enrichment is visible inside To-Do itself; manual edits between the sentinels are preserved.

Original options + decision context:

| Option | Pro | Con |
|---|---|---|
| **A. To-Do Notes field only** (round-trip) | Visible in native To-Do UI; survives if Pensieve dies | Notes field is plain text; no structure; size limits; hard to query |
| **B. ChromaDB only** (Pensieve never writes back) | Clean schema; full structure; fast queries; semantic search out of the box | Enrichment invisible inside To-Do — half the value |
| **C. Both** — ChromaDB canonical, Notes mirrors a subset | Best of both | Sync complexity; potential drift; needs sentinel |

Phase 1 ships B; Phase 2 promotes to C.

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
