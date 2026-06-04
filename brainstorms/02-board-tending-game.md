---
title: Garden — Board-Tending Game for Pensieve
date: 2026-06-04
status: design
phase: 3-design
related_issues:
  - "#6"  # Garden v1 — Board Health + Card Freshness
  - "#7"  # Garden v2 — Daily Quests
  - "#8"  # Garden v3 — Achievements + Friday level-summary
depends_on:
  - vial v1 (shipped 48c73b6)
---

# Garden — Pensieve as a Board-Tending Game

## Goal

Make keeping the Pensieve board healthy and up-to-date **feel rewarding**.
Track stale cards, reward hygiene actions (updating, closing-with-Vial, burying
ghosts), and surface it all in a way that is **diagnostic, not punitive** and
**fun, not gamey**.

## Guiding principle

**The card is the unit of play.** Fresh cards thrive, neglected cards wither,
closed-without-evidence cards leak value. This is a **garden-tending** game
dressed in a HUD aesthetic — never cartoonish, never naggy. Every mechanic
must answer: *does this make the board healthier or the work clearer?*
If not, kill it.

This is a **complementary frame** to the promo-readiness HUD (which lives at
the `Promo Readiness` brainstorm tier and is tracked separately) — that one
gamifies *promo packet evidence*; this one gamifies *board hygiene*. They
share the Vial substrate but answer different questions.

## The 4 reward loops (layered dopamine schedule)

| Loop | Trigger | Reward | Why it works |
|------|---------|--------|--------------|
| **Immediate** (seconds) | Move card · update card · capture Vial · bury ghost | Micro-animation (subtle particle burst, color flash), optional sound | Instant feedback → habit formation |
| **Daily quests** (minutes) | 2–3 auto-generated micro-tasks each morning | Quest checkmarks + small board-health boost on completion | Bounded, finishable in <10 min, never nags |
| **Weekly recap** (Friday) | Auto-digest (Issue #3) reframed as "level summary" | Board health Δ vs. last week, top contributions, biggest cleanup | End-of-week "look what I did" moment |
| **Achievements** (rare) | Hitting a meaningful first/milestone | Permanent badge in a quiet gallery, brief confetti | Long-tail surprise, no grind |

## The core mechanic: Board Health Score (0–100)

One number, top of the kanban. Color-graded (🟢 90+ / 🟡 70–89 / 🔴 <70).
Andy's job is to keep it green.

Draft formula:

```
health = 100
  - (% stale_cards   × 30)    # main penalty
  - (overdue_cards   ×  5)    # overdue stings
  - (ghost_cards     × 10)    # >30d untouched = ugly
  + (vial_capture_%  × 10)    # closing with evidence = bonus
  + (clean_streak_d  ×  1, capped at 10)
clamp 0..100
```

Behaviors:

- Hover the score → tooltip breaks down each term.
- Click the score → filter board to stale + overdue + ghosts (the offenders).
- Persist `last_tended_at` on every card so the staleness clock has a single
  source of truth.

## Per-card freshness state

A small colored dot in the corner of each card (and an optional border tint
for the extreme states).

| State | Trigger | Visual | Notes |
|-------|---------|--------|-------|
| 🌱 Fresh | updated <3 days | green dot | newly-touched delight |
| 🌿 Active | updated 3–7 days | no dot (default) | the normal case |
| 🍂 Stale | 8–14 days no update | yellow dot + slight desaturation | gentle nudge |
| 💀 Ghost | >30 days no movement | red dot + ghost icon, action: "revive or bury?" | the only state that prompts a decision |
| ✨ Closed+Vialed | closed lane AND ≥1 Vial captured | gold star, drifts to bottom of closed | the win state |
| ⚠️ Overdue | due_date passed, not closed | red border on due-date pill (already exists) | extend existing pill |

The board becomes **visually alive** — at a glance you see what needs water.

### What counts as "tending"?

A tending action resets `last_tended_at` to now:

- Moving a card between lanes
- Editing card title/description (manual or via the AI title-revision flow)
- Capturing a Vial on a closed card
- Acknowledging a stale-card prompt (the "still relevant?" flow)
- Re-aligning the card to a new Connect goal

Auto-sync from To-Do does **not** count (otherwise every poll keeps cards
artificially fresh). Only deliberate, in-Pensieve actions tend.

## Daily Quests (the fun engine)

Each morning Pensieve auto-generates **≤3 quests** based on the current
board state. Quest types:

- *"Tend the 2 stale cards in CISO GRC"* (specific IDs, click to jump)
- *"Capture Vials on yesterday's 3 closures"*
- *"Triage 1 inbox card"* (only when Inbox is non-empty)
- *"Bury or revive the ghost in `<lane>`"*
- *"Hit a 95+ board health score today"* (only when within 5 points)

Constraints:

- Max 3 per day.
- Each must be finishable in <10 minutes of work.
- Completing all 3 → small board-health boost (+5 transient).
- Quests **do not carry over** — today's misses don't haunt tomorrow.
- Quest panel collapses to a single line when complete: `✅ ✅ ✅ +5`.

## Achievements (quiet gallery, no popups)

Permanent badges unlocked on meaningful firsts. Browseable from a `🏆`
button in the header. **Not grindy** — these reward real work, not clicks.

| Badge | Trigger |
|-------|---------|
| 🌱 Sprout | First card created |
| 📜 Scribe | First 10 Vials captured |
| 🧹 Custodian | First ghost buried |
| 🏆 Clean Week | 7 days with zero stale cards |
| 🔥 Streak Keeper | 30-day clean board |
| ⚡ Storm | 5 cards closed in a single day |
| 🎯 Sharpshooter | Hit 95+ board health |
| 🌟 Centurion | 100 lifetime Vials |
| 🌳 Gardener | All achievements above unlocked |

Achievement unlock → brief confetti at the badge gallery icon (no blocking
popup), and the badge animates in. No sound by default.

## Weekly level-summary

Piggyback on the Friday auto-digest (Issue #3). One card at the top of the
recap reframed as:

```
This week:
  Board health: 87 → 92 (+5)
  Closed:       14 cards
  Vials:        9 captured (64% capture rate)
  Cleanup:      2 ghosts buried, 5 stale cards tended
  Streak:       4-day clean board, longest this quarter
```

No new ingestion plumbing — pure derived data over the existing memory and
Vial stores.

## Anti-patterns — explicitly don't build

These look like gamification but actively hurt a single-user productivity tool:

- ❌ **Login / daily-use streaks** — pressure on a tool that should reduce pressure
- ❌ **XP / levels without semantic meaning** — vanity numbers
- ❌ **Per-click rewards on card creation** — incentivizes spam, not quality
- ❌ **Popups / nags / push notifications** — Pensieve is a HUD, not a Tamagotchi
- ❌ **Quest carry-over** — today's misses must not accumulate as debt
- ❌ **Leaderboards** — single user
- ❌ **Penalty for closing without a Vial** — make capturing *rewarding*, not closing *punishing*
- ❌ **Sound on by default** — opt-in only
- ❌ **Animations that block work** — all in-flow and dismissable

## Roadmap (three shippable issues)

### Garden v1 — Board Health + Card Freshness (Issue #6)

The minimum shippable surface to deliver the *game feel*. Estimated S/M
effort.

Scope:

1. Add `last_tended_at: datetime | None` to `Memory` schema (server-side).
   Backfill from `updated_at` on existing memories.
2. Compute per-card `freshness` (`fresh / active / stale / ghost / closed_vialed`)
   in the API response — derive at the boundary, do not persist.
3. Render the colored freshness dot on each card; ghost icon for ghosts.
4. Compute Board Health Score in the API. Render in the header strip with
   color-coding and a hover tooltip that breaks down each term.
5. Click-the-score filter: shows stale + overdue + ghosts only.
6. Wire all five "tending actions" (move, edit, vial-save, vial-skip,
   goal-realign) to bump `last_tended_at` server-side.
7. Tests:
   - Freshness derivation across all 5 states.
   - Board Health formula correctness with seeded fixtures.
   - Tending actions bump `last_tended_at`; auto-sync does not.

Non-goals for v1: daily quests, achievements, confetti, sounds.

### Garden v2 — Daily Quests (Issue #7)

After v1 lands and the freshness/health data is trustworthy.

Scope:

- Quest generator: pure function over current board state. Selects up to 3.
- Quest persistence (1 row per day): id, generated_at, completed_at, items.
- Quest panel in the dashboard header (collapsible, dismissable).
- Completion detection: ties to the v1 tending actions.
- Daily reset at local midnight (or first session of the day).
- Tests for the quest generator across boards in different health states.

### Garden v3 — Achievements + Weekly Level-Summary (Issue #8)

After v2 lands and the system has produced enough events to be interesting.

Scope:

- Achievement definitions in code (list of named predicates).
- Unlocked-set persisted as `data/achievements.json` (single-user, trivial).
- Achievement gallery UI behind a `🏆` button.
- Confetti micro-burst at the gallery icon on unlock (no popup).
- Friday digest gains a `level_summary` block: deltas vs. last week.
- Tests for each achievement predicate.

## Synergy with other in-flight work

- **Issue #1 (Vial v1)** — already shipped. Powers `vial_capture_%` in the
  health formula and the "Capture Vials on yesterday's closures" quest.
- **Issue #2 (IC behaviors)** — orthogonal. Garden tracks board hygiene;
  IC behaviors track promo-evidence balance. Don't merge.
- **Issue #3 (Friday digest)** — Garden v3 piggybacks on this. Sequence:
  ship #3 first, then v3.
- **Issue #4 (strand-health panel)** — shares the staleness math. Garden v1
  defines `last_tended_at` and the freshness derivation function; #4 then
  applies the same function at the strand level. **Ship Garden v1 before #4.**
- **Issue #5 (personal-device merge)** — independent.

## Open questions

- **Should "📌 pinned" memories be exempt from staleness?** Lean yes — pinned
  signals "this is durable context, not a task." Tracked under v1.
- **What happens to ghosts that get tended?** They should pop back to Fresh
  with a brief acknowledgment ("revived"). Confetti micro-burst at the card.
- **Should auto-sync from To-Do bump `last_tended_at`?** No, per the section
  above. Only deliberate Pensieve actions count.
- **Should the Board Health Score have a public ceiling lower than 100 when
  Inbox is non-empty?** Open — maybe cap at 95 to leave room to demonstrate
  triage. Decide in v1 implementation.
- **Quest generator personalization** — should it learn what kinds of quests
  Andy completes more reliably and bias toward those? Defer to a v2.5 issue
  if Garden v2 ships and Andy wants more.

## Definition of done (per phase)

**v1 done** when: every card shows a freshness dot; the header shows a
color-coded health score; clicking it filters to offenders; tending actions
bump the score; tests pass; README updated.

**v2 done** when: each morning Pensieve generates ≤3 quests; completing one
visibly checks it off; completing all 3 yields the +5 transient boost;
the panel is invisible when no quests are pending.

**v3 done** when: the achievement gallery renders all defined badges with
locked/unlocked state; new unlocks animate in; the Friday digest contains
the level-summary block.

## Status

- **2026-06-04** — design captured. Issues #6/#7/#8 opened. Vial v1
  shipped earlier today is the foundational dependency. No implementation
  started.
