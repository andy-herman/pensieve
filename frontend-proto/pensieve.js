/* ============================================================
   The Pensieve - dashboard JS (v4, parchment edition)
   - Two views: Lifecycle (4 columns: Memory / Dive / Review / Closed) + Houses (Connect goals)
   - Connect goals editable via in-app modal (persisted in localStorage)
   - Themes: day / night (toggle) + marauder (easter egg), persisted in localStorage
   - Hedwig review counter, footprint trail on drag, golden Snitch
   - Drag-and-drop kanban, semantic search, PDF goals import, Recap, Constellation, Docs
   Data model note: goals carry a neutral `lane` slug (crimson, gold, ...). The
   House names and glyphs below are presentation only; ids, data attributes and
   API fields stay neutral.
   ============================================================ */

// ----- 1. Connect goals (canonical defaults; mirrors data/connect-goals.json) -----

const DEFAULT_GOALS = [
  {
    id: "goal-1-dora-deep-dive",
    number: 1,
    short_name: "DORA Deep Dive",
    name: "DORA Deep Dive Compliance",
    lane: "crimson",
    color_primary: "#7a2018",
    color_accent: "#c9a655",
    summary: "Lead CISO GRC role on DORA Core Team through deep dive examination. Deliver accurate JET responses, co-develop regulatory readiness playbook.",
  },
  {
    id: "goal-2-uk-ctp",
    number: 2,
    short_name: "UK CTP",
    name: "UK CTP Year 1 Complete + Year 2 Launch",
    lane: "gold",
    color_primary: "#b08a26",
    color_accent: "#2a1d10",
    summary: "Deliver Year 1 obligations post-designation, submit Self-Assessment in 3-month window. Launch Year 2 roadmap (scenario testing, incident mgmt playbook).",
  },
  {
    id: "goal-3-nis2-foundation",
    number: 3,
    short_name: "NIS2",
    name: "NIS2 Readiness Foundation",
    lane: "emerald",
    color_primary: "#2e5a3a",
    color_accent: "#a8a8a8",
    summary: "Build NIS2 foundational posture during H1. Lead scoping + gap analysis, apply communication-first model day one, identify core team partners.",
  },
  {
    id: "goal-4-ai-transformation",
    number: 4,
    short_name: "AI Program + Argus",
    name: "AI Strategy, Innovation, and Transformation Program for CISO GRC",
    lane: "azure",
    color_primary: "#2c4670",
    color_accent: "#c9a655",
    summary: "Operationalize AI transformation program. Scale Argus from MVP to wider-used regulatory compliance platform. Four capability areas, biweekly triage, quarterly pilots.",
  },
];

// ----- 2. Lifecycle columns + strands -----

const LIFECYCLE_COLUMNS = [
  { id: "memory", title: "Memory", subtitle: "Backlog, awaiting depth" },
  { id: "dive", title: "Dive", subtitle: "Active work" },
  { id: "review", title: "Review", subtitle: "Needs another look" },
  { id: "closed", title: "Closed", subtitle: "Done, complete in your source list" },
];

// Mirror of pensieve/enrichment/goals_importer.py LANE_PALETTE so the
// frontend can auto-assign a lane when the user adds a goal manually.
const LANE_PALETTE = [
  { lane: "crimson",    color_primary: "#7a2018", color_accent: "#c9a655" },
  { lane: "gold",       color_primary: "#b08a26", color_accent: "#2a1d10" },
  { lane: "emerald",    color_primary: "#2e5a3a", color_accent: "#a8a8a8" },
  { lane: "azure",      color_primary: "#2c4670", color_accent: "#c9a655" },
  { lane: "slate",      color_primary: "#5a5a5a", color_accent: "#c9a655" },
  { lane: "ember",      color_primary: "#8a4b1f", color_accent: "#e0c690" },
  { lane: "sage",       color_primary: "#3c5e2c", color_accent: "#c9a655" },
  { lane: "rose",       color_primary: "#a83a1f", color_accent: "#f5d77b" },
];

// Presentation-only House name + glyph for each neutral lane slug. The text
// variation selector (︎) keeps glyphs monochrome so CSS can ink them in
// the House color instead of rendering a color emoji.
const LANE_HOUSE = {
  crimson:    { house: "Gryffindor", glyph: "⚡︎" },
  gold:       { house: "Hufflepuff", glyph: "⚘︎" },
  emerald:    { house: "Slytherin",  glyph: "⚜︎" },
  azure:      { house: "Ravenclaw",  glyph: "⚛︎" },
  slate:      { house: "Internal",   glyph: "⚗︎" },
  ember:      { house: "Muggleborn", glyph: "✎︎" },
  sage:       { house: "Centaur",    glyph: "☘︎" },
  rose:       { house: "Phoenix",    glyph: "❁︎" },
  unassigned: { house: "Unhoused",   glyph: "✦︎" },
};

function houseName(lane) {
  const h = LANE_HOUSE[lane];
  return h ? h.house : (lane || "House");
}

function houseGlyph(lane) {
  const h = LANE_HOUSE[lane];
  return h ? h.glyph : "✦︎";
}

const STRANDS = [
  { id: "dora-rfi", display_name: "DORA RFI Responses", kind: "deep", connect_goal_ids: ["goal-1-dora-deep-dive"] },
  { id: "nis2-mapping", display_name: "NIS2 Crosswalk", kind: "deep", connect_goal_ids: ["goal-3-nis2-foundation", "goal-1-dora-deep-dive"] },
  { id: "uk-ctp-domain", display_name: "UK CTP Domain Write-up", kind: "deep", connect_goal_ids: ["goal-2-uk-ctp"] },
  { id: "argus-build", display_name: "Argus Build", kind: "deep", connect_goal_ids: ["goal-4-ai-transformation"] },
  { id: "pensieve-build", display_name: "Pensieve Build", kind: "deep", connect_goal_ids: ["goal-4-ai-transformation"] },
  { id: "ai-program-launch", display_name: "AI Program Launch", kind: "deep", connect_goal_ids: ["goal-4-ai-transformation"] },
  { id: "1on1-prep", display_name: "1:1 + Team Mgmt", kind: "tactical", connect_goal_ids: [] },
  { id: "leadership-update", display_name: "Leadership Updates", kind: "writing", connect_goal_ids: ["goal-2-uk-ctp", "goal-1-dora-deep-dive", "goal-3-nis2-foundation", "goal-4-ai-transformation"] },
  { id: "ic5-promo-evidence", display_name: "Promo Evidence", kind: "writing", connect_goal_ids: [] },
  { id: "learning-ai", display_name: "Learning (AI / Foundry)", kind: "learning", connect_goal_ids: ["goal-4-ai-transformation"] },
  { id: "ops-chores", display_name: "Ops + Admin", kind: "tactical", connect_goal_ids: [] },
];

// ----- 3. Seed memories (from Phase 0 smoke test + 2 extras for column coverage) -----

const SEED_MEMORIES = [
  {
    id: "mem_todo_sample_01",
    title: "JET RFI 0107: Article 6 ICT risk framework mapping",
    suggested_strand: "dora-rfi",
    needs_human_strand_review: false,
    why: "JET requested explicit mapping of DORA Article 6 to my internal ICT risk policy, with Azure and M365 product owner confirmation before submission. Hard deadline this Thursday.",
    impact: "Closes RFI 0107 on schedule and protects the no-gap streak on DORA deep dive responses.",
    strand_kind: "deep",
    confidence_strand: 0.96, confidence_impact: 0.85,
    connect_goal_ids: ["goal-1-dora-deep-dive"],
    connect_alignment_confidence: 0.97,
    connect_alignment_note: "Direct work on JET deep dive responses, the headline commitment of Goal #1.",
    column: "dive",
  },
  {
    id: "mem_todo_sample_02",
    title: "NIS2 Article 21 to DORA Article 6 crosswalk deck",
    suggested_strand: "nis2-mapping",
    needs_human_strand_review: false,
    why: "Building a two-column NIS2 to DORA crosswalk for the next CISO GRC sync, reusing existing DORA evidence to minimize new asks on product teams.",
    impact: "Shows the team how much of NIS2 we already cover via DORA, and surfaces the genuine gaps that need new evidence work.",
    strand_kind: "deep",
    confidence_strand: 0.95, confidence_impact: 0.80,
    connect_goal_ids: ["goal-3-nis2-foundation", "goal-1-dora-deep-dive"],
    connect_alignment_confidence: 0.90,
    connect_alignment_note: "Primary NIS2 scoping (Goal #3) with explicit DORA playbook reuse (Goal #1 leverage).",
    column: "dive",
  },
  {
    id: "mem_todo_sample_03",
    title: "1:1 prep with manager",
    suggested_strand: "1on1-prep",
    needs_human_strand_review: false,
    why: "Standing 1:1 with manager, need to cover this week's program risks and decisions that need air cover.",
    impact: "Keeps manager informed on weekly program state and ensures escalations are surfaced before they become blockers.",
    strand_kind: "tactical",
    confidence_strand: 0.92, confidence_impact: 0.62,
    connect_goal_ids: [],
    connect_alignment_confidence: 0.85,
    connect_alignment_note: "Recurring team management task with no direct Connect goal alignment.",
    column: "memory",
  },
  {
    id: "mem_todo_sample_04",
    title: "Rewrite enrich-memory-prompt.md to handle empty notes",
    suggested_strand: "pensieve-build",
    needs_human_strand_review: false,
    why: "Three of ten samples have empty notes and the prompt currently leans on them, so output quality drops. Need explicit fallback to title plus recent context.",
    impact: "Makes Pensieve enrichment reliable on sparse tasks and reduces avoidable review-queue churn.",
    strand_kind: "deep",
    confidence_strand: 0.97, confidence_impact: 0.88,
    connect_goal_ids: ["goal-4-ai-transformation"],
    connect_alignment_confidence: 0.94,
    connect_alignment_note: "Direct Pensieve build, a productivity multiplier under the AI program.",
    column: "dive",
  },
  {
    id: "mem_todo_sample_05",
    title: "Foundry Agent Framework deep-dive evaluation",
    suggested_strand: "learning-ai",
    needs_human_strand_review: false,
    why: "45-minute BUILD 2026 session on Foundry Agent Framework. Specifically evaluating whether Foundry agents could replace Pensieve's hand-rolled prompt routing.",
    impact: "Decides whether to keep building Pensieve on raw Azure OpenAI calls or migrate to a managed agent framework.",
    strand_kind: "learning",
    confidence_strand: 0.92, confidence_impact: 0.75,
    connect_goal_ids: ["goal-4-ai-transformation"],
    connect_alignment_confidence: 0.85,
    connect_alignment_note: "Direct R&D for the AI program; informs build-vs-buy on tooling.",
    column: "memory",
  },
  {
    id: "mem_todo_sample_06",
    title: "Approve Argus production VM invoice",
    suggested_strand: "ops-chores",
    needs_human_strand_review: false,
    why: "Standard monthly Azure spend for the Argus production VM. Routes to manager for cost-center confirmation when above the approval threshold.",
    impact: "Keeps Argus paid and running with the right approval path if monthly spend is above threshold.",
    strand_kind: "tactical",
    confidence_strand: 0.90, confidence_impact: 0.85,
    connect_goal_ids: [],
    connect_alignment_confidence: 0.90,
    connect_alignment_note: "Argus is named but this is operational invoice handling, not direct Goal #4 delivery work.",
    column: "memory",
  },
  {
    id: "mem_todo_sample_07",
    title: "H1 self-reflection: stack rank top 6 moments",
    suggested_strand: "ic5-promo-evidence",
    needs_human_strand_review: false,
    why: "Pulling from notes, prior reviews, and peer feedback to stack-rank the strongest contributions since October 2025 for promo case and Connect refresh.",
    impact: "Creates a sharper evidence base for the Connect narrative and promo case.",
    strand_kind: "writing",
    confidence_strand: 0.98, confidence_impact: 0.88,
    connect_goal_ids: [],
    connect_alignment_confidence: 0.86,
    connect_alignment_note: "Promo work supports performance packaging but does not directly advance a specific Connect deliverable.",
    column: "dive",
  },
  {
    id: "mem_todo_sample_08",
    title: "Fix Argus regulator-detail crash on missing acronym",
    suggested_strand: "argus-build",
    needs_human_strand_review: false,
    why: "A reviewer from Legal hit a render crash on the Argus regulator detail page for BaFin. Page should fall back to short_name instead of crashing.",
    impact: "Restores a working regulator persona experience in Argus and removes a visible bug that would undermine confidence in demos.",
    strand_kind: "deep",
    confidence_strand: 0.97, confidence_impact: 0.84,
    connect_goal_ids: ["goal-4-ai-transformation"],
    connect_alignment_confidence: 0.96,
    connect_alignment_note: "Direct Argus product work, clearly advances Goal #4.",
    column: "closed",
  },
  {
    id: "mem_todo_sample_09",
    title: "Renew passport before October trip",
    suggested_strand: null,
    needs_human_strand_review: true,
    why: "Passport renewal needed before an October trip; expedite if the fee is cheaper than the flight-rebooking risk.",
    impact: "Keeps the trip viable and avoids last-minute rebooking costs.",
    strand_kind: "tactical",
    confidence_strand: 0.10, confidence_impact: 0.70,
    connect_goal_ids: [],
    connect_alignment_confidence: 0.99,
    connect_alignment_note: "Personal admin with no work-goal alignment.",
    notes_for_user: "Personal task in the Pensieve queue. Consider routing the Personal list to a separate lane.",
    column: "memory",
  },
  {
    id: "mem_todo_sample_10",
    title: "Review direct report's H2 growth plan draft",
    suggested_strand: "1on1-prep",
    needs_human_strand_review: false,
    why: "Direct report sent their self-authored growth plan covering 3 stretch goals plus a cross-team rotation interest. Need feedback before Friday's 1:1.",
    impact: "Gives the direct report clear development feedback and makes the 1:1 concrete rather than reactive.",
    strand_kind: "tactical",
    confidence_strand: 0.96, confidence_impact: 0.84,
    connect_goal_ids: [],
    connect_alignment_confidence: 0.94,
    connect_alignment_note: "Direct-report management with no specific Connect goal alignment.",
    column: "memory",
  },
  // Two extras to populate Review + Closed columns
  {
    id: "mem_seed_11",
    title: "Friday update to manager: AI program status",
    suggested_strand: "leadership-update",
    needs_human_strand_review: false,
    why: "Weekly Friday update to manager, timed for the Monday leadership sync that follows. Covers AI program governance progress, Argus pilot demos, and Pensieve internal use.",
    impact: "Maintains the structured leadership visibility cadence and ensures the AI program shows up in the broader team's view of the org.",
    strand_kind: "writing",
    confidence_strand: 0.97, confidence_impact: 0.86,
    connect_goal_ids: ["goal-4-ai-transformation", "goal-2-uk-ctp"],
    connect_alignment_confidence: 0.88,
    connect_alignment_note: "Cross-program leadership update; weights to Goal #4 (program theme this week) and Goal #2 (UK CTP cadence anchor).",
    column: "review",
  },
  {
    id: "mem_seed_12",
    title: "UK CTP Domain 9 self-assessment write-up: shipped",
    suggested_strand: "uk-ctp-domain",
    needs_human_strand_review: false,
    why: "Closed the final UK CTP Year 1 self-assessment domain (Domain 9) with sign-off from Legal and the domain SME. All 9 of 9 domains now in submission-ready state.",
    impact: "Completes the Year 1 Self-Assessment evidence base ahead of designation, making the 3-month post-designation submission window comfortable rather than tight.",
    strand_kind: "writing",
    confidence_strand: 0.98, confidence_impact: 0.94,
    connect_goal_ids: ["goal-2-uk-ctp"],
    connect_alignment_confidence: 0.99,
    connect_alignment_note: "Direct Year 1 deliverable for Goal #2.",
    column: "closed",
  },
];

// ----- 4. State -----

const API_BASE = (() => {
  try {
    const saved = localStorage.getItem("pensieve-api-base");
    if (saved) return saved.replace(/\/$/, "");
  } catch (e) { /* ignore */ }
  // When opened over http(s) on the same origin, use same origin; otherwise localhost
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "http://127.0.0.1:8765";
})();

const STATE = {
  goals: loadGoals(),
  goalsMeta: {},
  // Empty until the API answers. The seed memories are only a fallback for
  // when the API is unreachable, so they never flash before live data.
  memories: [],
  booting: true,          // true until the first API answer (or failure)
  boardSig: "",           // last /api/memories + /api/goals payload; unchanged polls skip the re-render
  boardChanged: false,    // set by loadMemoriesFromApi
  mutationEpoch: 0,       // bumped on every local card change (see noteLocalMutation)
  gardenAt: 0,            // when the Garden (health, quests, achievements) was last fetched
  boardDirty: false,      // the board changed while another page was showing
  renderPending: false,   // a render was requested mid-drag; run it on drop/dragend
  view: "lifecycle",      // "lifecycle" | "lanes"
  page: "board",          // "board" | "recap" | "graph" | "docs"
  weeklyFilter: (() => { try { return localStorage.getItem("pensieve-weekly") === "1"; } catch (e) { return false; } })(),
  theme: loadTheme(),     // "day" | "night" | "marauder"
  easterBuffer: "",       // last few keystrokes, for the Marauder's Map easter egg
  inkNextRender: true,    // play the ink-in animation on the next board render
  filter: { strand: null, search: "", reviewOnly: false, boardHealthOffenders: false, questTargetIds: null },
  semanticResultIds: null, // null = no semantic filter; Set<string> = restrict to these ids
  semanticQuery: "",
  apiConnected: false,
  apiSourceLabel: "seed",
  boardHealth: null,       // {score, tier, terms, counts, computed_at} | null
  quests: null,            // {today: {date, quests, generated_at}, clean_streak_d, all_done, quest_bonus} | null
  achievements: null,      // {achievements, total, unlocked_count, new_unlocks} | null
  achievementsSeenIds: (() => {
    try {
      const raw = localStorage.getItem("pensieve-ach-seen");
      if (raw) return new Set(JSON.parse(raw));
    } catch (e) { /* fall through */ }
    return new Set();
  })(),
};

// Active card drag (see section 9). Declared up here so everything can read it.
let DRAG = { id: null, fromCol: null, el: null, overCol: null };

function loadGoals() {
  try {
    const raw = localStorage.getItem("pensieve-goals");
    if (raw) return JSON.parse(raw);
  } catch (e) { /* ignore */ }
  return DEFAULT_GOALS.map(g => ({ ...g }));
}

function saveGoals() {
  localStorage.setItem("pensieve-goals", JSON.stringify(STATE.goals));
}

// Called while STATE is being built, so it must not touch later `const`s.
function loadTheme() {
  try {
    const saved = localStorage.getItem("pensieve-theme");
    if (saved === "day" || saved === "night" || saved === "marauder") return saved;
  } catch (e) { /* storage blocked: fall back to day */ }
  return "day";
}

function saveTheme() {
  try { localStorage.setItem("pensieve-theme", STATE.theme); } catch (e) { /* ignore */ }
}

// Read a CSS custom property from <html> (theme tokens live there).
function cssVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

// One MediaQueryList, queried live (the footprint trail asks on every few
// dragover events, so avoid re-parsing the query each time).
const REDUCED_MOTION_MQL = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

function prefersReducedMotion() {
  return !!(REDUCED_MOTION_MQL && REDUCED_MOTION_MQL.matches);
}

// ----- 5. Helpers -----

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

function getGoal(id) { return STATE.goals.find(g => g.id === id); }
function getStrand(id) { return STRANDS.find(s => s.id === id); }

function strandDisplay(id) {
  const s = getStrand(id);
  return s ? s.display_name : "Unstranded";
}

function isReviewNeeded(m) {
  const t = 0.5;
  return m.needs_human_strand_review === true ||
    (typeof m.confidence_strand === "number" && m.confidence_strand < t) ||
    (typeof m.confidence_impact === "number" && m.confidence_impact < t);
}

function memoryMatchesFilter(m) {
  if (STATE.semanticResultIds && !STATE.semanticResultIds.has(m.id)) return false;
  if (STATE.filter.reviewOnly && !isReviewNeeded(m)) return false;
  if (STATE.filter.boardHealthOffenders && !isBoardHealthOffender(m)) return false;
  if (STATE.filter.questTargetIds && !STATE.filter.questTargetIds.has(m.id)) return false;
  if (STATE.filter.strand && m.suggested_strand !== STATE.filter.strand) return false;
  if (STATE.filter.search) {
    const hay = `${m.display_title || ""} ${m.title} ${m.why} ${m.impact}`.toLowerCase();
    if (!hay.includes(STATE.filter.search.toLowerCase())) return false;
  }
  return true;
}

// Garden v1: a card is an "offender" if it's stale, ghost, or overdue.
// Click the Board Health pill to filter the board down to just these.
function isBoardHealthOffender(m) {
  if (m.is_overdue) return true;
  const f = m.freshness;
  return f === "stale" || f === "ghost";
}

// Format a due_date ISO string as a compact "DUE Mon 8" pill, or null if absent/invalid.
// Returns { text, urgency } where urgency is "overdue" | "soon" | "later".
function formatDueDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  const now = new Date();
  const midnightNow = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const midnightDue = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const daysOut = Math.round((midnightDue - midnightNow) / 86400000);
  let urgency = "later";
  if (daysOut < 0) urgency = "overdue";
  else if (daysOut <= 3) urgency = "soon";
  const weekday = d.toLocaleDateString(undefined, { weekday: "short" });
  const dayNum = d.getDate();
  const month = d.toLocaleDateString(undefined, { month: "short" });
  // Within +/-7 days, show weekday; otherwise show month + day for context.
  const text = (daysOut >= -7 && daysOut <= 7) ? `${weekday} ${dayNum}` : `${month} ${dayNum}`;
  return { text, urgency };
}

// Most recent Monday at 00:00 local time.
function mostRecentMonday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();              // 0=Sun..6=Sat
  const diff = (day === 0 ? 6 : day - 1); // days since Monday
  d.setDate(d.getDate() - diff);
  return d;
}

// Best available "closed on" date for a memory: source completion, else when
// Pensieve enriched it (approximation for manually-closed cards).
function closedDate(m) {
  const iso = m.completed_at || m.enriched_at;
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

// Weekly filter only affects the Closed column: when on, hide closed cards
// from before this week's Monday. Open columns and other views are unaffected.
// Non-destructive: data stays in the store (Recap/graph/search still see it).
function passesWeeklyFilter(m, colId) {
  if (!STATE.weeklyFilter) return true;
  if (colId !== "closed") return true;
  const cd = closedDate(m);
  if (!cd) return true;  // unknown date: keep visible rather than hide silently
  return cd >= mostRecentMonday();
}

function applyWeeklyFilterState() {
  const btn = $("#weekly-filter-btn");
  if (btn) btn.classList.toggle("active", !!STATE.weeklyFilter);
  updateFilterBadge();
}

// ----- 5b. API client + remote sync -----

async function fetchJson(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

async function fetchText(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.text();
}

// Requests where only the newest answer matters (semantic search, graph,
// docs). Starting a new one aborts the previous so a slow, older response can
// never land on top of a newer one.
const SUPERSEDE = {};
function supersede(key) {
  if (SUPERSEDE[key]) SUPERSEDE[key].abort();
  const ctrl = new AbortController();
  SUPERSEDE[key] = ctrl;
  return ctrl.signal;
}
function isAbortError(e) { return !!e && e.name === "AbortError"; }

// Dashboard ids are "mem_<source id>"; the API expects the bare source id.
function apiIdOf(memoryId) { return String(memoryId).replace(/^mem_/, ""); }

function setFooterSource() {
  const el = $("#api-source-label");
  if (el) el.textContent = STATE.apiSourceLabel;
}

// Call before changing a memory locally. A poll that was already in flight
// then discards its (older) snapshot instead of reverting the change on screen.
function noteLocalMutation() {
  STATE.mutationEpoch++;
  STATE.boardSig = "";  // the next successful poll re-applies server state, even if unchanged
}

// Merge the server-authoritative copy of a memory returned by a PATCH.
function mergeServerMemory(memory) {
  if (!memory || !memory.id) return;
  const idx = STATE.memories.findIndex(x => x.id === memory.id);
  if (idx >= 0) STATE.memories[idx] = { ...STATE.memories[idx], ...memory };
}

// Loads the board snapshot (health check, memories, goals) in parallel and
// returns true when the API answered. STATE.boardChanged tells the caller
// whether the payload differs from what is already on screen. The Garden
// (health pill, quests, achievements) refreshes in the background so it
// never delays the cards.
async function loadMemoriesFromApi({ garden = true } = {}) {
  const epoch = STATE.mutationEpoch;
  try {
    const [health, memText, goalsResp] = await Promise.all([
      fetchJson("/api/healthz").catch(() => null),
      fetchText("/api/memories"),
      fetchJson("/api/goals").catch(() => null),  // keep local goals on failure
    ]);
    STATE.apiConnected = true;
    STATE.booting = false;
    const data = JSON.parse(memText);
    const sig = memText + "\n" + (goalsResp ? JSON.stringify(goalsResp) : "");
    // A card was moved or edited while this request was in flight: keep the
    // optimistic local state; the next poll reconciles with the server.
    STATE.boardChanged = sig !== STATE.boardSig && STATE.mutationEpoch === epoch;
    if (STATE.boardChanged) {
      STATE.boardSig = sig;
      const mems = Array.isArray(data.memories) ? data.memories : [];
      STATE.memories = mems.map(m => ({ ...m, column: m.column || "memory" }));
      if (goalsResp && Array.isArray(goalsResp.goals) && goalsResp.goals.length > 0) {
        STATE.goals = goalsResp.goals.map(g => ({ ...g }));
      }
      if (goalsResp && goalsResp._meta) STATE.goalsMeta = goalsResp._meta;
    }
    STATE.apiSourceLabel = (Array.isArray(data.memories) && data.memories.length > 0)
      ? `${(health && health.default_source) || "live"} (${data.count} memories)`
      : "API connected (0 memories, run `pensieve sync`)";
    if (garden) refreshGarden();
    return true;
  } catch (e) {
    STATE.apiConnected = false;
    if (STATE.booting) {
      // Never reached the API this session: show the bundled demo memories.
      STATE.booting = false;
      STATE.memories = SEED_MEMORIES.map(m => ({ ...m }));
      STATE.boardChanged = true;
      STATE.apiSourceLabel = "offline (seed data)";
    } else {
      STATE.boardChanged = false;  // keep whatever is on screen
      if (STATE.apiSourceLabel !== "offline (seed data)") {
        STATE.apiSourceLabel = "offline (showing last refresh)";
      }
    }
    console.warn(`Pensieve API not reachable at ${API_BASE}: ${e.message}. Using seed data.`);
    return false;
  }
}

// Garden v1-v3: health pill, quests, achievements, fetched in parallel.
const GARDEN_MAX_AGE_MS = 5 * 60 * 1000;
function refreshGarden() {
  if (!STATE.apiConnected) return Promise.resolve();
  STATE.gardenAt = Date.now();
  return Promise.all([loadBoardHealth(), loadQuests(), loadAchievements()]);
}

// --- Garden v1: Board Health fetch + render -----------------------------
async function loadBoardHealth() {
  if (!STATE.apiConnected) return;
  try {
    STATE.boardHealth = await fetchJson("/api/board/health");
  } catch (e) {
    STATE.boardHealth = null;
  }
  renderBoardHealth();
}

function renderBoardHealth() {
  const el = document.getElementById("board-health");
  if (!el) return;
  const scoreEl = document.getElementById("board-health-score");
  const tipEl = document.getElementById("board-health-tip");
  const h = STATE.boardHealth;
  if (!h) {
    el.removeAttribute("data-tier");
    if (scoreEl) scoreEl.textContent = "--";
    if (tipEl) { tipEl.hidden = true; tipEl.innerHTML = ""; }
    return;
  }
  el.dataset.tier = h.tier || "yellow";
  if (scoreEl) scoreEl.textContent = String(h.score);
  el.classList.toggle("filter-active", !!STATE.filter.boardHealthOffenders);
  if (tipEl) {
    const t = h.terms || {};
    const c = h.counts || {};
    const streakD = t.clean_streak_d || 0;
    const questB = t.quest_bonus || 0;
    const lines = [
      `<strong>Board Health: ${h.score}/100</strong>`,
      `<ul>`,
      `<li>open: ${c.open ?? 0} / closed: ${c.closed ?? 0}</li>`,
      `<li>stale: ${t.stale_count ?? 0} (-${Math.round((t.stale_pct ?? 0) * 30)} pts)</li>`,
      `<li>ghost: ${t.ghost_count ?? 0} (-${(t.ghost_count ?? 0) * 10} pts)</li>`,
      `<li>overdue: ${t.overdue_count ?? 0} (-${(t.overdue_count ?? 0) * 5} pts)</li>`,
      `<li>capture: ${Math.round((t.capture_pct ?? 0) * 100)}% (+${Math.round((t.capture_pct ?? 0) * 10)} pts)</li>`,
    ];
    if (streakD > 0) {
      lines.push(`<li>clean streak: ${streakD}d (+${Math.min(10, streakD)} pts)</li>`);
    }
    if (questB > 0) {
      lines.push(`<li>quests: all done (+${questB} pts)</li>`);
    }
    lines.push(`</ul>`);
    lines.push(`<div style="opacity:.7;margin-top:6px">click to filter to offenders</div>`);
    tipEl.innerHTML = lines.join("");
  }
}

function toggleBoardHealthFilter() {
  STATE.filter.boardHealthOffenders = !STATE.filter.boardHealthOffenders;
  // Mutually exclusive with the quest filter (avoids confusing combined view).
  if (STATE.filter.boardHealthOffenders) STATE.filter.questTargetIds = null;
  renderBoardHealth();
  renderQuestPanel();
  renderBoard();
}

// --- Garden v2: daily quests fetch + render -----------------------------
async function loadQuests() {
  if (!STATE.apiConnected) return;
  try {
    STATE.quests = await fetchJson("/api/quests");
  } catch (e) {
    STATE.quests = null;
  }
  renderQuestPanel();
}

function renderQuestPanel() {
  const panel = document.getElementById("quest-panel");
  if (!panel) return;
  const chipsEl = document.getElementById("quest-panel-chips");
  const streakEl = document.getElementById("quest-panel-streak");
  const allDoneEl = document.getElementById("quest-panel-alldone");
  const q = STATE.quests;
  const list = q && q.today && Array.isArray(q.today.quests) ? q.today.quests : [];
  if (!q || list.length === 0) {
    panel.hidden = true;
    if (chipsEl) chipsEl.innerHTML = "";
    if (streakEl) { streakEl.hidden = true; streakEl.textContent = ""; }
    if (allDoneEl) allDoneEl.hidden = true;
    panel.classList.remove("is-collapsed");
    return;
  }
  panel.hidden = false;

  if (streakEl) {
    const streak = Number(q.clean_streak_d || 0);
    if (streak > 0) {
      streakEl.hidden = false;
      streakEl.textContent = `\u{1F525} ${streak}-day clean streak`;
    } else {
      streakEl.hidden = true;
      streakEl.textContent = "";
    }
  }

  const allDone = !!q.all_done;
  if (allDoneEl) allDoneEl.hidden = !allDone;
  panel.classList.toggle("is-collapsed", allDone);

  if (chipsEl) {
    chipsEl.innerHTML = "";
    for (const quest of list) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "quest-chip" + (quest.completed_at ? " is-complete" : "");
      chip.dataset.questId = quest.id;
      chip.dataset.targetIds = (quest.target_memory_ids || []).join(",");
      const progress = questProgressFor(quest);
      const icon = quest.completed_at ? "\u2705" : "\u25A2";
      chip.title = quest.description || quest.title || "";
      chip.innerHTML =
        `<span class="quest-chip-icon">${icon}</span>` +
        `<span class="quest-chip-title">${escapeHtml(quest.title || "")}</span>` +
        (progress ? `<span class="quest-chip-progress">${progress}</span>` : "");
      // Filter board to this quest's targets when clicked (if it has targets
      // and is not already complete - completed quests just show status).
      const filterIds = (quest.target_memory_ids || []).filter(Boolean);
      const isActiveFilter =
        STATE.filter.questTargetIds &&
        filterIds.length > 0 &&
        filterIds.every(id => STATE.filter.questTargetIds.has(id)) &&
        STATE.filter.questTargetIds.size === filterIds.length;
      if (isActiveFilter) chip.classList.add("filter-active");
      chip.addEventListener("click", () => {
        if (filterIds.length === 0) return;
        toggleQuestFilter(filterIds);
      });
      chipsEl.appendChild(chip);
    }
  }
}

function questProgressFor(quest) {
  const targets = quest.target_memory_ids || [];
  if (!targets.length) return "";
  if (quest.completed_at) return `${targets.length}/${targets.length}`;
  if (!STATE.memories) return `0/${targets.length}`;
  const byId = new Map(STATE.memories.map(m => [m.id, m]));
  let done = 0;
  for (const id of targets) {
    const m = byId.get(id);
    if (!m) { done += 1; continue; }  // target gone => counts done
    if (quest.kind === "capture-yesterday-closures") {
      if ((m.vials_count || 0) > 0) done += 1;
    } else if (quest.kind === "triage-inbox") {
      if (m.column !== "memory") done += 1;
      else if (isTendedToday(m)) done += 1;
    } else {
      if (isTendedToday(m)) done += 1;
    }
  }
  return `${done}/${targets.length}`;
}

function isTendedToday(m) {
  if (!m.last_tended_at) return false;
  const t = new Date(m.last_tended_at);
  if (isNaN(t.getTime())) return false;
  const now = new Date();
  const todayStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  return t.getTime() >= todayStart.getTime();
}

function toggleQuestFilter(targetIds) {
  if (!Array.isArray(targetIds) || targetIds.length === 0) return;
  const setIds = new Set(targetIds);
  const current = STATE.filter.questTargetIds;
  const sameFilter =
    current &&
    current.size === setIds.size &&
    Array.from(setIds).every(id => current.has(id));
  STATE.filter.questTargetIds = sameFilter ? null : setIds;
  // Mutually exclusive with the offenders filter.
  if (STATE.filter.questTargetIds) STATE.filter.boardHealthOffenders = false;
  renderBoardHealth();
  renderQuestPanel();
  renderBoard();
}

// --- Garden v3: achievements + confetti ---------------------------------
async function loadAchievements({ allowConfetti = true } = {}) {
  if (!STATE.apiConnected) return;
  try {
    STATE.achievements = await fetchJson("/api/achievements");
  } catch (e) {
    STATE.achievements = null;
  }
  renderAchievementsButton();
  if (
    allowConfetti &&
    STATE.achievements &&
    Array.isArray(STATE.achievements.new_unlocks) &&
    STATE.achievements.new_unlocks.length > 0
  ) {
    const unseen = STATE.achievements.new_unlocks.filter(
      id => !STATE.achievementsSeenIds.has(id)
    );
    if (unseen.length > 0) {
      const btn = document.getElementById("achievements-btn");
      if (btn) {
        btn.classList.add("has-new-unlock");
        setTimeout(() => btn.classList.remove("has-new-unlock"), 2600);
        burstConfettiAt(btn);
      }
      const names = unseen.map(id => {
        const def = STATE.achievements.achievements.find(a => a.id === id);
        return def ? `${def.emoji} ${def.name}` : id;
      }).join(", ");
      toast(`Unlocked: ${names}`);
      unseen.forEach(id => STATE.achievementsSeenIds.add(id));
      try {
        localStorage.setItem(
          "pensieve-ach-seen",
          JSON.stringify(Array.from(STATE.achievementsSeenIds)),
        );
      } catch (e) { /* ignore quota */ }
    }
  }
}

function renderAchievementsButton() {
  const countEl = document.getElementById("achievements-btn-count");
  if (!countEl) return;
  const a = STATE.achievements;
  if (!a || !a.total) {
    countEl.hidden = true;
    countEl.textContent = "0";
    return;
  }
  countEl.hidden = false;
  countEl.textContent = `${a.unlocked_count}/${a.total}`;
}

function renderAchievementsModal() {
  const grid = document.getElementById("achievements-grid");
  const summary = document.getElementById("achievements-summary");
  if (!grid) return;
  const a = STATE.achievements;
  if (!a || !Array.isArray(a.achievements)) {
    grid.innerHTML = "<p style='opacity:.6'>No achievement data yet.</p>";
    if (summary) summary.textContent = "";
    return;
  }
  grid.innerHTML = a.achievements.map(def => {
    const state = def.unlocked ? "unlocked" : "locked";
    const when = def.unlocked_at
      ? `<div class="achievement-unlocked-at">${_formatUnlockedDate(def.unlocked_at)}</div>`
      : "";
    const safeName = escapeHtml(def.name);
    const safeDesc = escapeHtml(def.description || "");
    return `<div class="achievement-card" data-state="${state}" title="${safeDesc}">
      <div class="achievement-emoji" aria-hidden="true">${def.emoji}</div>
      <div class="achievement-name">${safeName}</div>
      <div class="achievement-desc">${safeDesc}</div>
      ${when}
    </div>`;
  }).join("");
  if (summary) {
    summary.textContent = `${a.unlocked_count} of ${a.total} unlocked.`;
  }
}

function _formatUnlockedDate(iso) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch (e) { return ""; }
}

function openAchievementsModal() {
  const modal = document.getElementById("achievements-modal");
  if (!modal) return;
  renderAchievementsModal();
  modal.hidden = false;
  // Reset the new-unlock styling on the button once the user has seen them.
  if (STATE.achievements && Array.isArray(STATE.achievements.achievements)) {
    STATE.achievements.achievements.forEach(def => {
      if (def.unlocked) STATE.achievementsSeenIds.add(def.id);
    });
    try {
      localStorage.setItem(
        "pensieve-ach-seen",
        JSON.stringify(Array.from(STATE.achievementsSeenIds)),
      );
    } catch (e) { /* ignore */ }
  }
}

function closeAchievementsModal() {
  const modal = document.getElementById("achievements-modal");
  if (modal) modal.hidden = true;
}

// Hand-rolled canvas confetti burst centered on the target element. ~30 lines
// so we avoid an external library. Particles fall under gravity for ~1s.
function burstConfettiAt(targetEl) {
  const canvas = document.getElementById("confetti-canvas");
  if (!canvas || !targetEl) return;
  const rect = targetEl.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  canvas.style.width = `${window.innerWidth}px`;
  canvas.style.height = `${window.innerHeight}px`;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  canvas.classList.add("is-firing");
  // House colors for the current theme (tokens --confetti-1..5 in pensieve.css).
  const colors = [1, 2, 3, 4, 5].map(i => cssVar(`--confetti-${i}`, "#c9a655"));
  const N = 36;
  const particles = Array.from({ length: N }, () => {
    const angle = Math.random() * Math.PI * 2;
    const speed = 3 + Math.random() * 5;
    return {
      x: cx, y: cy,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 2,
      size: 4 + Math.random() * 4,
      color: colors[Math.floor(Math.random() * colors.length)],
      life: 0,
    };
  });
  const start = performance.now();
  function frame(now) {
    const t = now - start;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => {
      p.vy += 0.18;
      p.x += p.vx;
      p.y += p.vy;
      p.life = t;
      ctx.globalAlpha = Math.max(0, 1 - t / 1100);
      ctx.fillStyle = p.color;
      ctx.fillRect(p.x, p.y, p.size, p.size);
    });
    if (t < 1100) {
      requestAnimationFrame(frame);
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      canvas.classList.remove("is-firing");
    }
  }
  requestAnimationFrame(frame);
}

// --- Auto-refresh poll ---------------------------------------------------
// The backend has an auto-sync scheduler (PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS,
// default 120s) that pulls fresh Microsoft To-Do data and writes enrichments
// to Chroma. To surface those updates without a manual page reload, the
// dashboard polls /api/memories every AUTO_REFRESH_MS. The poll bails out
// in any situation where a re-render would clobber unsaved UI state:
//   - the user is editing a card (`#card-modal` open)
//   - the user is editing Connect goals (`#goals-modal` open)
//   - the user is viewing achievements (`#achievements-modal` open)
//   - a card is mid-drag (DRAG.id set)
//   - a PATCH from the dashboard is in flight (patchesInFlight > 0)
//   - the document is hidden (Page Visibility API) - saves API calls when the tab is in the background
//   - another page (Recap, Graph, Docs) is showing; switching back to Board refreshes
// `pollInFlight` prevents stacked refreshes if the network call takes longer than the interval.
// An unchanged snapshot skips the re-render entirely, and a changed one only
// touches the cards that differ (see renderBoard), so scroll, focus, hover,
// and open menus survive a refresh. The Garden refetches when the board
// changed, or every GARDEN_MAX_AGE_MS so day rollovers still show up.
const AUTO_REFRESH_MS = 30000;
let pollInFlight = false;
let patchesInFlight = 0;

// Wrap a dashboard write so the poll stands down while it is in flight.
async function trackPatch(fn) {
  patchesInFlight++;
  try {
    return await fn();
  } finally {
    patchesInFlight = Math.max(0, patchesInFlight - 1);
  }
}

function _isModalOpen(id) {
  const el = document.getElementById(id);
  return !!(el && !el.hidden);
}

function anyModalOpen() {
  return ["card-modal", "goals-modal", "vial-modal", "achievements-modal", "ai-modal", "accounts-modal", "capture-modal", "agents-modal"].some(_isModalOpen);
}

async function refreshMemoriesIfSafe() {
  if (document.hidden || pollInFlight || patchesInFlight > 0) return;
  if (DRAG.id || anyModalOpen() || STATE.page !== "board") return;
  pollInFlight = true;
  try {
    const ok = await loadMemoriesFromApi({ garden: false });
    setFooterSource();
    if (!ok) return;
    if (STATE.boardChanged || Date.now() - STATE.gardenAt > GARDEN_MAX_AGE_MS) refreshGarden();
    if (STATE.boardChanged) {
      renderStrandFilter();
      renderBoard();
    }
  } catch (_) {
    // soft-fail; the next tick will try again. loadMemoriesFromApi already
    // logs its own warning to the console.
  } finally {
    pollInFlight = false;
  }
}

function startAutoRefreshLoop() {
  setInterval(refreshMemoriesIfSafe, AUTO_REFRESH_MS);
  // Refresh as soon as the tab comes back into focus so the user sees fresh
  // data immediately instead of waiting up to AUTO_REFRESH_MS for the next tick.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshMemoriesIfSafe();
  });
}

async function regenerateMemory(memoryId) {
  if (!STATE.apiConnected) {
    toast("Regenerate needs the API server (run `pensieve serve`)");
    return;
  }
  const btn = $("#edit-regen");
  const original = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.classList.add("is-regenerating");
    btn.innerHTML = "&#x2728; Brewing...";
  }
  try {
    const res = await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiIdOf(memoryId))}/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text.slice(0, 160)}`);
    }
    const body = await res.json();
    const fresh = body.memory;
    if (!fresh) throw new Error("API returned no memory");
    const newId = `mem_${fresh.source_task_id || fresh.id}`;
    fresh.id = newId;
    noteLocalMutation();
    const idx = STATE.memories.findIndex(x => x.id === memoryId);
    if (idx >= 0) STATE.memories[idx] = { ...STATE.memories[idx], ...fresh };
    renderStrandFilter();
    renderBoard();
    // Garden v1+v2+v3: regenerate is a tend - refresh pill, quests, and achievements.
    refreshGarden();
    // Show the regenerated text live, but only if this card's modal is still
    // open (brewing takes a while; never pop a closed or different card back up).
    if (cardModalShows(memoryId)) openModal(STATE.memories[idx] || fresh);
    toast(`Regenerated (+${body.tokens_used || 0} tokens)`);
  } catch (e) {
    toast(`Regenerate failed: ${e.message}`);
    if (btn && btn.isConnected) {
      btn.disabled = false;
      btn.classList.remove("is-regenerating");
      btn.innerHTML = original;
    }
  }
}

async function pollSyncUntilDone(buttonEl, { intervalMs = 1500, maxMs = 600000 } = {}) {
  const start = Date.now();
  let lastMsg = "";
  while (Date.now() - start < maxMs) {
    let state;
    try {
      state = await fetchJson("/api/sync/status");
    } catch (e) {
      throw new Error(`status check failed: ${e.message}`);
    }
    if (state.message && state.message !== lastMsg) {
      lastMsg = state.message;
      if (buttonEl) buttonEl.title = state.message;
    }
    if (state.status === "done") {
      const s = state.stats || {};
      const parts = [];
      if (s.new_enriched != null) parts.push(`${s.new_enriched} new`);
      if (s.updated_enriched != null) parts.push(`${s.updated_enriched} updated`);
      if (s.skipped_unchanged != null) parts.push(`${s.skipped_unchanged} unchanged`);
      if (s.failed) parts.push(`${s.failed} failed`);
      toast(`Pulled from Microsoft To-Do, ${parts.join(", ") || "complete"}`);
      return state;
    }
    if (state.status === "error") {
      throw new Error(state.error || "sync failed");
    }
    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error("sync timed out");
}

// PATCH a memory (`suffix` is "" for the general edit endpoint or "/column"),
// merge the server-authoritative copy back into STATE, and return the parsed
// payload. Throws with a short message on failure.
async function patchMemoryApi(memoryId, suffix, body) {
  return trackPatch(async () => {
    const res = await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiIdOf(memoryId))}${suffix}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status}: ${text.slice(0, 120)}`);
    }
    // The API returns the enriched memory so freshness updates in place
    // (the dot must refresh, not just the score pill). Best-effort parse.
    const payload = (await res.json().catch(() => null)) || {};
    if (payload.memory) mergeServerMemory(payload.memory);
    // If we got here, the API is up. Flip the flag so UI affordances that
    // gate on apiConnected (e.g. semantic search) work without a reload.
    if (!STATE.apiConnected) {
      STATE.apiConnected = true;
      if (STATE.apiSourceLabel === "offline (seed data)") {
        STATE.apiSourceLabel = "live (reconnected)";
        setFooterSource();
      }
    }
    return payload;
  });
}

async function persistColumnChange(memoryId, column) {
  // Always attempt the PATCH. Gating this on `apiConnected` caused silent data
  // loss when the dashboard first loaded against a down server (apiConnected
  // stuck on false), the user later dragged cards, and then Pull-from-To-Do
  // succeeded and triggered loadMemoriesFromApi which overwrote the un-saved
  // local drags with Chroma's columns.
  try {
    const payload = await patchMemoryApi(memoryId, "/column", { column });
    // Surface the completion-mirror outcome so the user knows whether the
    // close also propagated to Microsoft To-Do (only fires when dragging to
    // 'closed' AND PENSIEVE_MIRROR_COMPLETION=true).
    const cm = payload.completion_mirror;
    if (cm && cm.reason === "ok") {
      toast("Marked complete in To-Do");
    } else if (cm && cm.reason && cm.reason.startsWith("sink-error")) {
      toast(`Closed locally but To-Do writeback failed: ${cm.reason}`);
    } else if (cm && cm.reason === "task-not-found-at-source") {
      toast("Closed locally - upstream task not found in To-Do");
    }
    renderBoard();
    // Garden v1+v2+v3: refresh pill, quest panel, achievements so they all
    // reflect this tend (and a potential confetti burst on new unlocks).
    refreshGarden();
  } catch (e) {
    // Loud toast so the user knows the drag did NOT persist and the next
    // Pull-from-To-Do or Refresh will revert this card.
    toast(`Move not saved (${e.message}) - card will revert on next refresh`);
  }
}

// Houses view drop: persist the new Connect alignment (it used to live only
// in the browser and silently revert on the next 30s refresh).
async function persistGoalAlignment(memoryId, goalIds) {
  try {
    await patchMemoryApi(memoryId, "", { connect_goal_ids: goalIds });
    renderBoard();
    refreshGarden();
  } catch (e) {
    toast(`House change not saved (${e.message}) - card will revert on next refresh`);
  }
}

async function runSemanticSearch(q) {
  if (!q || !q.trim()) {
    supersede("search");  // drop any query still in flight
    STATE.semanticResultIds = null;
    STATE.semanticQuery = "";
    renderBoard();
    return;
  }
  if (!STATE.apiConnected) {
    toast("Semantic search needs the API server (run `pensieve serve`)");
    return;
  }
  const signal = supersede("search");
  try {
    const data = await fetchJson(`/api/search?q=${encodeURIComponent(q)}&top_k=20`, { signal });
    STATE.semanticResultIds = new Set((data.memories || []).map(m => m.id));
    STATE.semanticQuery = q;
    if (STATE.semanticResultIds.size === 0) {
      toast(`No semantic matches for "${q}"`);
    }
    renderBoard();
  } catch (e) {
    if (!isAbortError(e)) toast(`Search failed: ${e.message}`);
  }
}

// ----- 6. Rendering -----

function applyTheme() {
  document.documentElement.setAttribute("data-theme", STATE.theme);
  const label = $("#theme-label");
  if (label) label.textContent = `${STATE.theme} mode`;
  const btn = $("#theme-toggle");
  if (btn) {
    const next = STATE.theme === "day" ? "night" : "day";
    btn.setAttribute("aria-label", `Switch to ${next} mode`);
    btn.title = STATE.theme === "marauder" ? "Mischief managed: back to day" : `Switch to ${next} mode`;
  }
  // Canvas colors come from theme tokens; drop the cached palette and repaint
  // the Constellation if it is visible and settled.
  GRAPH.pal = null;
  if (STATE.page === "graph" && GRAPH.nodes.length && !GRAPH.raf) drawGraph();
}

// Theme switches crossfade the whole page as one GPU snapshot (View
// Transitions) instead of letting each surface run its own CSS transition,
// which repainted every column for ~0.6s and showed half-switched states.
// Falls back to the plain switch where unsupported or with reduced motion.
function setTheme(theme, announce) {
  const apply = () => {
    STATE.theme = theme;
    saveTheme();
    applyTheme();
    if (announce) toast(announce);
  };
  const root = document.documentElement;
  if (!document.startViewTransition || prefersReducedMotion() || document.hidden) {
    apply();
    return;
  }
  const done = () => root.classList.remove("theme-switching");
  root.classList.add("theme-switching");  // CSS: transitions off, so the new snapshot is final
  try {
    const vt = document.startViewTransition(apply);
    vt.ready.catch(() => { /* skipped transition: apply still ran, nothing to do */ });
    vt.finished.then(done, done);
  } catch (e) {
    done();
    apply();
  }
}

function applyView() {
  document.documentElement.setAttribute("data-view", STATE.view);
  $$(".view-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.view === STATE.view));
  STATE.inkNextRender = true;
  renderBoard();
}

function renderStrandFilter() {
  const root = $("#strand-filter");
  const usedStrandIds = new Set();
  STATE.memories.forEach(m => { if (m.suggested_strand) usedStrandIds.add(m.suggested_strand); });
  const strands = STRANDS.filter(s => usedStrandIds.has(s.id));
  // Rebuild the pills only when the strand set changes (clicks are delegated,
  // see init), so a poll never steals focus from the open Filter popover.
  const ids = strands.map(s => s.id).join(",");
  if (root.dataset.ids !== ids) {
    root.dataset.ids = ids;
    root.innerHTML = strands.map(s =>
      `<button type="button" class="strand-pill" data-strand="${escapeHtml(s.id)}">${escapeHtml(s.display_name)}</button>`
    ).join("");
  }
  $$(".strand-pill", root).forEach(btn => btn.classList.toggle("active", btn.dataset.strand === STATE.filter.strand));
  updateFilterBadge();
}

// ----- 6a. Board rendering (keyed reconcile) -----
// renderBoard reconciles instead of rebuilding. Column shells are reused while
// the column set is unchanged, and each column keeps its card elements keyed
// by memory id plus the card's full markup. Only cards whose markup changed
// are replaced, so the 30s refresh, a search keystroke, or a Garden update
// leaves scroll position, focus, hover, and running animations alone.

const INK_MS = 10 * 60 + 550 + 100;  // max stagger + ink-fade-in duration + slack
let inkTimer = null;

function renderBoard() {
  // Never rebuild under an active drag: the dragged card would be detached
  // and its dragend would never fire. endDrag() runs the pending render.
  if (DRAG.id) { STATE.renderPending = true; return; }
  STATE.renderPending = false;
  updateMemoryCount();
  updateReviewIndicator();
  // The board is display:none on other pages; switchPage renders on return.
  if (STATE.page !== "board") { STATE.boardDirty = true; return; }
  STATE.boardDirty = false;

  const board = $("#board");
  // Ink-in only on the first paint of live data and on view switches, never on
  // the 30s auto-refresh or while typing in search, so the board doesn't
  // shimmer constantly. The class outlives this render until the stagger has
  // finished, so a quick follow-up render cannot cut the fade short.
  const ink = !!STATE.inkNextRender && !STATE.booting;
  if (ink) {
    STATE.inkNextRender = false;
    board.classList.add("ink-in");
    clearTimeout(inkTimer);
    inkTimer = setTimeout(() => board.classList.remove("ink-in"), INK_MS);
  }
  board.classList.toggle("is-loading", STATE.booting);

  const specs = boardColumnSpecs();
  const layout = `${STATE.view}|${specs.map(s => s.key).join("|")}`;
  if (board.dataset.layout !== layout) {
    board.textContent = "";
    specs.forEach(() => board.appendChild(createColumnShell()));
    if (STATE.view === "lanes") board.appendChild(renderAddLaneTile());
    board.dataset.layout = layout;
  }
  const shells = board.querySelectorAll(":scope > .column:not(.add-lane-tile)");
  // Ink renders build fresh cards so every one of them plays the fade.
  specs.forEach((spec, i) => updateColumn(shells[i], spec, !ink));
}

function boardColumnSpecs() {
  if (STATE.view === "lifecycle") return LIFECYCLE_COLUMNS.map(lifecycleColumnSpec);
  return STATE.goals.map(laneColumnSpec).concat(unassignedColumnSpec());
}

function lifecycleColumnSpec(col) {
  const inColumn = STATE.memories.filter(m => m.column === col.id && memoryMatchesFilter(m));
  const memos = inColumn.filter(m => passesWeeklyFilter(m, col.id));
  const hidden = inColumn.length - memos.length;
  return {
    key: `lifecycle:${col.id}`,
    data: { column: col.id, view: "lifecycle" },
    title: col.title,
    subtitle: hidden > 0 ? `${col.subtitle} &middot; ${hidden} earlier hidden` : col.subtitle,
    count: `${memos.length} ${memos.length === 1 ? "memory" : "memories"}`,
    memos,
    empty: "The surface is still.",
  };
}

function laneColumnSpec(goal) {
  const memos = STATE.memories.filter(m =>
    Array.isArray(m.connect_goal_ids) &&
    m.connect_goal_ids.includes(goal.id) &&
    memoryMatchesFilter(m)
  );
  return {
    key: `lanes:${goal.id}`,
    data: { column: goal.id, lane: String(goal.lane || ""), view: "lanes" },
    title: `#${goal.number} ${escapeHtml(goal.short_name)}`,
    subtitle: escapeHtml(houseName(goal.lane)),
    count: `${memos.length} aligned`,
    memos,
    empty: "No memories yet for this House.",
  };
}

function unassignedColumnSpec() {
  const memos = STATE.memories.filter(m =>
    (!Array.isArray(m.connect_goal_ids) || m.connect_goal_ids.length === 0) &&
    memoryMatchesFilter(m)
  );
  return {
    key: "lanes:unassigned",
    data: { column: "unassigned", lane: "unassigned", view: "lanes" },
    title: "Unhoused",
    subtitle: "Work not yet tied to a Connect goal",
    count: `${memos.length} drifting`,
    memos,
    empty: "Everything aligns. Rare and excellent.",
  };
}

function createColumnShell() {
  const wrap = document.createElement("section");
  wrap.className = "column";
  wrap.innerHTML = `<div class="column-header"></div><div class="column-cards"></div>`;
  wrap._cards = new Map();  // memory id -> { el, key, delay }
  return wrap;
}

function setDataset(el, data) {
  for (const [k, v] of Object.entries(data)) {
    if (el.dataset[k] !== v) el.dataset[k] = v;
  }
}

function updateColumn(col, spec, reuse) {
  setDataset(col, spec.data);
  const header = col.firstElementChild;
  const headerHtml =
    `<h2 class="column-title">${spec.title}</h2>` +
    `<p class="column-subtitle">${spec.subtitle}</p>` +
    `<span class="column-count">${STATE.booting ? "&hellip;" : spec.count}</span>`;
  if (header._html !== headerHtml) {
    header.innerHTML = headerHtml;
    header._html = headerHtml;
  }

  const prev = reuse ? col._cards : new Map();
  const next = new Map();
  const wanted = spec.memos.map((m, idx) => {
    const parts = cardParts(m);
    let entry = prev.get(m.id);
    if (!entry || entry.key !== parts.key) entry = { el: buildCard(parts), key: parts.key, delay: "" };
    // Stagger the ink-in, capped so long columns don't wait seconds for the tail.
    const delay = `${Math.min(idx, 10) * 60}ms`;
    if (entry.delay !== delay) {
      entry.el.style.setProperty("--ink-delay", delay);
      entry.delay = delay;
    }
    next.set(m.id, entry);
    return entry.el;
  });
  col._cards = next;
  if (!wanted.length) {
    if (!col._empty) {
      col._empty = document.createElement("div");
      col._empty.className = "empty-column";
    }
    col._empty.textContent = STATE.booting ? "Stirring the memories..." : spec.empty;
    wanted.push(col._empty);
  }
  syncChildren(col.lastElementChild, wanted);
}

// Make parent's children exactly `wanted`, in order, moving existing nodes
// instead of recreating them.
function syncChildren(parent, wanted) {
  let cursor = parent.firstChild;
  for (const el of wanted) {
    if (el === cursor) {
      cursor = cursor.nextSibling;
    } else {
      parent.insertBefore(el, cursor);
    }
  }
  while (cursor) {
    const next = cursor.nextSibling;
    parent.removeChild(cursor);
    cursor = next;
  }
}

// A lightweight "+ Add a House" tile shown at the end of the Houses view. Opens
// the goals editor (which adds/edits/deletes lanes), so unclear work can get
// its own House when a Connect goal doesn't fit. It has no data-column, so it
// is never a drop target.
function renderAddLaneTile() {
  const wrap = document.createElement("section");
  wrap.className = "column add-lane-tile";
  wrap.dataset.view = "lanes";
  wrap.innerHTML = `
    <button class="add-lane-btn" title="Add or edit your Houses">
      <span class="add-lane-plus" aria-hidden="true">+</span>
      <span>Add a House</span>
      <span class="add-lane-hint">or edit the ones you have</span>
    </button>
  `;
  wrap.querySelector(".add-lane-btn").addEventListener("click", openGoalsEditor);
  return wrap;
}

// Everything a card's DOM depends on. `key` doubles as the reconcile signature:
// a card is rebuilt only when its key changes.
function cardParts(m) {
  const classes = ["card"];
  const data = { memoryId: m.id };
  // Garden v1: per-card freshness dot via [data-freshness] CSS hook.
  // Only set when truthy so generic selectors aren't accidentally matched.
  if (m.freshness) data.freshness = m.freshness;
  if (m.is_overdue) classes.push("is-overdue");

  // Primary goal color for the left rail
  let goalColor = "";
  const primaryGoal = (m.connect_goal_ids && m.connect_goal_ids.length > 0) ? getGoal(m.connect_goal_ids[0]) : null;
  if (primaryGoal) {
    data.goalColor = "1";
    goalColor = primaryGoal.color_primary || "";
    // data-lane lets CSS swap in the theme-aware House color for the rail.
    if (primaryGoal.lane) data.lane = primaryGoal.lane;
  }

  const strand = getStrand(m.suggested_strand);
  const strandKind = m.strand_kind || (strand ? strand.kind : "");

  const review = isReviewNeeded(m);
  if (review) classes.push("has-review");

  const goalsHtml = (m.connect_goal_ids || []).map(gid => {
    const g = getGoal(gid);
    if (!g) return "";
    return `<span class="goal-chip" data-lane="${escapeHtml(g.lane || "")}" title="${escapeHtml(g.name)} (${escapeHtml(houseName(g.lane))})"><span class="goal-chip-glyph" aria-hidden="true">${houseGlyph(g.lane)}</span>#${g.number} ${escapeHtml(g.short_name)}</span>`;
  }).join("");

  const due = formatDueDate(m.due_date);
  const dueHtml = due
    ? `<span class="card-due" data-urgency="${due.urgency}" title="Due ${escapeHtml(m.due_date)}">${due.urgency === "overdue" ? "Overdue" : "Due"} ${escapeHtml(due.text)}</span>`
    : "";

  const fullTitle = m.display_title || m.title || "";
  const html = `
    ${review ? `<div class="wax-seal" title="Needs review" aria-label="Needs review">R</div>` : ""}
    <h3 class="card-title" title="${escapeHtml(fullTitle)}">${escapeHtml(fullTitle)}</h3>
    <div class="card-meta">
      <span class="card-strand" data-kind="${strandKind || ""}">${escapeHtml(strandDisplay(m.suggested_strand))}</span>
      ${dueHtml}
    </div>
    <p class="card-why">${escapeHtml(m.why)}</p>
    ${goalsHtml ? `<div class="card-goals">${goalsHtml}</div>` : ""}
    ${renderVialAffordance(m)}
  `;
  const cls = classes.join(" ");
  return { cls, data, goalColor, html, key: `${cls}|${JSON.stringify(data)}|${goalColor}|${html}` };
}

// Cards carry no listeners of their own: click, keyboard, and drag are
// delegated from #board (see wireBoardEvents), so reused cards stay live.
function buildCard(parts) {
  const el = document.createElement("article");
  el.className = parts.cls;
  el.draggable = true;
  el.tabIndex = 0;  // keyboard: Tab to a card, Enter or Space opens it
  Object.assign(el.dataset, parts.data);
  if (parts.goalColor) el.style.setProperty("--goal-color", parts.goalColor);
  el.innerHTML = parts.html;
  return el;
}

function renderVialAffordance(m) {
  if (m.pending_closure_capture) {
    return `<button class="card-vial-chevron" type="button" data-memory-id="${escapeHtml(m.id)}" title="Capture what changed when this closed">&#x1F4DC; Capture</button>`;
  }
  if (m.vials_count && m.vials_count > 0) {
    return `<button class="card-vial-badge" type="button" data-memory-id="${escapeHtml(m.id)}" title="${m.vials_count} closure note(s) captured">&#x1F4DC; ${m.vials_count}</button>`;
  }
  return "";
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function updateMemoryCount() {
  const el = $("#memory-count");
  if (STATE.booting) { el.textContent = "gathering memories"; return; }
  const visible = STATE.memories.filter(memoryMatchesFilter).length;
  const total = STATE.memories.length;
  el.textContent = visible === total ? `${total} memories` : `${visible} of ${total} memories`;
}

// Hedwig carries a letter with the review count; her label says "All clear"
// when the queue is empty.
function updateReviewIndicator() {
  const reviewing = STATE.memories.filter(isReviewNeeded).length;
  const count = $("#hedwig-count");
  const label = $("#review-count");
  const block = $(".review-block");
  if (count) count.textContent = reviewing > 99 ? "99+" : String(reviewing);
  if (label) {
    label.textContent = STATE.booting
      ? "Awaiting post"
      : STATE.filter.reviewOnly
        ? "Showing review"
        : (reviewing === 0 ? "All clear" : `${reviewing} need review`);
  }
  if (block) {
    block.classList.toggle("has-review", reviewing > 0);
    block.classList.toggle("filter-active", !!STATE.filter.reviewOnly);
    block.setAttribute("aria-pressed", STATE.filter.reviewOnly ? "true" : "false");
  }
}

// Click handler for Hedwig (the masthead review indicator): toggles a
// board-wide "show only review-flagged cards" filter. Bound once during init().
function toggleReviewOnlyFilter() {
  const reviewing = STATE.memories.filter(isReviewNeeded).length;
  if (reviewing === 0 && !STATE.filter.reviewOnly) return; // nothing to filter to
  STATE.filter.reviewOnly = !STATE.filter.reviewOnly;
  renderBoard();
}

// ----- 7. Modal -----

const LIFECYCLE_OPTIONS = [
  { id: "memory", label: "Memory" },
  { id: "dive", label: "Dive" },
  { id: "review", label: "Review" },
  { id: "closed", label: "Closed" },
];

// Format a Date or ISO string as a YYYY-MM-DD value for <input type="date">.
function toInputDate(d) {
  const x = (d instanceof Date) ? d : new Date(d);
  if (isNaN(x.getTime())) return "";
  const y = x.getFullYear();
  const mo = String(x.getMonth() + 1).padStart(2, "0");
  const day = String(x.getDate()).padStart(2, "0");
  return `${y}-${mo}-${day}`;
}

// Default due date for a card with none set: ~2 weeks from today.
function defaultDueDate() {
  const d = new Date();
  d.setDate(d.getDate() + 14);
  return toInputDate(d);
}

// Card modal bookkeeping: which memory it shows, and what had focus before it
// opened (focus returns there on close, so keyboard users keep their place).
const CARD_MODAL = { memoryId: null, returnFocus: null };

function cardModalShows(memoryId) {
  return _isModalOpen("card-modal") && CARD_MODAL.memoryId === memoryId;
}

// Open the modal for the current copy of a memory (cards are looked up by id
// at click time, so a refresh between render and click can't open stale data).
function openCardById(memoryId) {
  const m = STATE.memories.find(x => x.id === memoryId);
  if (m) openModal(m);
}

function openModal(m) {
  const body = $("#modal-body");
  const review = isReviewNeeded(m);
  if (!_isModalOpen("card-modal")) {
    const active = document.activeElement;
    CARD_MODAL.returnFocus = active && active !== document.body ? active : null;
  }
  CARD_MODAL.memoryId = m.id;
  // Pre-fill the due field with the card's existing due date, or default to
  // ~2 weeks out so saving a card without one sets it roughly two weeks ahead.
  const dueValue = m.due_date ? toInputDate(m.due_date) : defaultDueDate();

  const strandOptions = [`<option value="">&lt;unstranded&gt;</option>`]
    .concat(STRANDS.map(s =>
      `<option value="${escapeHtml(s.id)}" ${m.suggested_strand === s.id ? "selected" : ""}>${escapeHtml(s.display_name)} (${escapeHtml(s.kind)})</option>`
    )).join("");

  const colOptions = LIFECYCLE_OPTIONS.map(c =>
    `<option value="${c.id}" ${m.column === c.id ? "selected" : ""}>${c.label}</option>`
  ).join("");

  const goalCheckboxes = STATE.goals.map(g => {
    const checked = (m.connect_goal_ids || []).includes(g.id);
    return `
      <label class="goal-check" data-lane="${escapeHtml(g.lane || "")}">
        <input type="checkbox" data-goal-id="${escapeHtml(g.id)}" ${checked ? "checked" : ""} />
        <span class="goal-chip" data-lane="${escapeHtml(g.lane || "")}" title="${escapeHtml(g.name)} (${escapeHtml(houseName(g.lane))})">
          <span class="goal-chip-glyph" aria-hidden="true">${houseGlyph(g.lane)}</span>#${g.number} ${escapeHtml(g.short_name)}
        </span>
      </label>`;
  }).join("");

  body.innerHTML = `
    <input id="edit-title" class="modal-title-edit" value="${escapeHtml(m.display_title || m.title)}" placeholder="Card display title (5 to 12 words)" />
    <p class="modal-source-title" title="Verbatim subject from Microsoft To-Do. Pensieve never edits this.">From To-Do: ${escapeHtml(m.title)}</p>

    <div class="modal-meta">
      <label class="inline-label">Strand
        <select id="edit-strand" class="inline-select">${strandOptions}</select>
      </label>
      <label class="inline-label">Column
        <select id="edit-column" class="inline-select">${colOptions}</select>
      </label>
      <label class="inline-label">Due
        <input type="date" id="edit-due" class="inline-select" value="${dueValue}" title="Defaults to ~2 weeks out; clear to remove" />
      </label>
      <label class="inline-label review-toggle">
        <input type="checkbox" id="edit-review" ${m.needs_human_strand_review ? "checked" : ""} />
        Flag for review
      </label>
    </div>
    ${review ? `<div class="review-status-line"><span class="review-status-rule"></span><span class="review-status-label">Sealed for review</span><span class="review-status-rule"></span></div>` : ""}

    <div class="modal-section">
      <div class="modal-label">Why</div>
      <textarea id="edit-why" class="modal-textarea" rows="3">${escapeHtml(m.why || "")}</textarea>
    </div>

    <div class="modal-section">
      <div class="modal-label">Impact hypothesis</div>
      <textarea id="edit-impact" class="modal-textarea" rows="3">${escapeHtml(m.impact || "")}</textarea>
    </div>

    <div class="modal-section">
      <div class="modal-label">Connect alignment</div>
      <div class="goal-check-grid">${goalCheckboxes}</div>
      <textarea id="edit-align-note" class="modal-textarea" rows="2"
        placeholder="Why this Memory aligns (or doesn't)">${escapeHtml(m.connect_alignment_note || "")}</textarea>
    </div>

    <div class="modal-section">
      <div class="modal-label">Pensieve note (visible to you only)</div>
      <textarea id="edit-notes-user" class="modal-textarea" rows="2"
        placeholder="Private note for yourself">${escapeHtml(m.notes_for_user || "")}</textarea>
    </div>

    <div class="modal-actions">
      <span class="modal-meta-line">
        strand ${typeof m.confidence_strand === "number" ? m.confidence_strand.toFixed(2) : "?"}
        &nbsp;|&nbsp; impact ${typeof m.confidence_impact === "number" ? m.confidence_impact.toFixed(2) : "?"}
        &nbsp;|&nbsp; align ${typeof m.connect_alignment_confidence === "number" ? m.connect_alignment_confidence.toFixed(2) : "?"}
        &nbsp;|&nbsp; <code>${escapeHtml(m.id)}</code>
      </span>
      <span class="modal-actions-buttons">
        <button id="edit-regen" class="ghost-button regen-btn" type="button" title="Re-run AI enrichment for this card (why, impact, strand, Connect alignment). Your column and private note are preserved.">&#x2728; Regenerate with AI</button>
        <button id="edit-cancel" class="ghost-button" type="button">Cancel</button>
        <button id="edit-save" class="primary-button" type="button" data-memory-id="${escapeHtml(m.id)}">Save</button>
      </span>
    </div>
  `;
  $("#card-modal").hidden = false;

  $("#edit-save").addEventListener("click", () => saveMemoryEdit(m.id));
  $("#edit-cancel").addEventListener("click", closeModal);
  const regenBtn = $("#edit-regen");
  if (regenBtn) regenBtn.addEventListener("click", () => regenerateMemory(m.id));

  // Auto-focus the display-title field so the user can edit immediately
  // without a mouse click. setTimeout lets the layout settle first so the
  // focus ring renders against the visible modal.
  setTimeout(() => {
    const titleEl = document.getElementById("edit-title");
    if (titleEl) {
      titleEl.focus();
      titleEl.select();
    }
  }, 0);
}

function readEditedFields() {
  const selectedGoalIds = $$("#modal-body .goal-check input[type=checkbox]")
    .filter(cb => cb.checked)
    .map(cb => cb.dataset.goalId);
  return {
    display_title: $("#edit-title").value.trim(),
    suggested_strand: $("#edit-strand").value || null,
    column: $("#edit-column").value,
    needs_human_strand_review: $("#edit-review").checked,
    why: $("#edit-why").value,
    impact: $("#edit-impact").value,
    connect_goal_ids: selectedGoalIds,
    connect_alignment_note: $("#edit-align-note").value,
    notes_for_user: $("#edit-notes-user").value,
    due_date: $("#edit-due").value || null,
  };
}

async function saveMemoryEdit(memoryId) {
  const patch = readEditedFields();
  if (!patch.display_title) {
    toast("Display title cannot be empty");
    return;
  }

  // Always update local state so the UI is responsive even offline
  noteLocalMutation();
  const mem = STATE.memories.find(x => x.id === memoryId);
  if (mem) {
    Object.assign(mem, patch);
  }
  renderStrandFilter();
  renderBoard();
  closeModal();

  if (!STATE.apiConnected) {
    toast("Saved locally (API offline; changes will not persist)");
    return;
  }

  try {
    // Re-syncs local state from the server-authoritative copy.
    await patchMemoryApi(memoryId, "", patch);
    renderStrandFilter();
    renderBoard();
    // Garden v1+v2+v3: editing tends the card - refresh pill, quests, achievements.
    refreshGarden();
    toast("Saved");
  } catch (e) {
    toast(`Save failed: ${e.message}`);
  }
}

function closeModal() {
  const modal = $("#card-modal");
  if (modal.hidden) return;
  modal.hidden = true;
  restoreFocus(CARD_MODAL.returnFocus);
  CARD_MODAL.returnFocus = null;
  CARD_MODAL.memoryId = null;
}

// Return focus after a modal closes. If the opener was a card that has since
// been re-rendered (its markup changed on save), focus its replacement.
function restoreFocus(el) {
  if (!el) return;
  if (!el.isConnected && el.dataset && el.dataset.memoryId) {
    el = document.querySelector(`#board .card[data-memory-id="${CSS.escape(el.dataset.memoryId)}"]`);
  }
  if (el && el.isConnected && typeof el.focus === "function") el.focus({ preventScroll: true });
}

// ----- 7b. Vial modal (closure capture) -----

const VIAL = { memoryId: null, saving: false };

function openVialModal(memoryId) {
  const m = STATE.memories.find(x => x.id === memoryId);
  if (!m) return;
  VIAL.memoryId = memoryId;
  const titleText = m.display_title || m.title || "(untitled)";
  const ctx = $("#vial-context");
  if (ctx) ctx.textContent = titleText;
  const ta = $("#vial-text");
  if (ta) { ta.value = ""; }
  $("#vial-modal").hidden = false;
  setTimeout(() => { if (ta) ta.focus(); }, 0);
}

function closeVialModal() {
  $("#vial-modal").hidden = true;
  VIAL.memoryId = null;
}

async function saveVial(kind) {
  const memoryId = VIAL.memoryId;
  if (!memoryId) return;
  const text = ($("#vial-text").value || "").trim();
  if (kind === "captured" && !text) {
    toast("Add a sentence, or use Skip to dismiss");
    return;
  }
  // A double click on Save must not POST two Vials.
  if (VIAL.saving) return;
  VIAL.saving = true;
  const buttons = [$("#vial-save"), $("#vial-skip")];
  buttons.forEach(b => { if (b) b.disabled = true; });
  try {
    await trackPatch(async () => {
      const res = await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiIdOf(memoryId))}/vials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ captured_text: kind === "captured" ? text : "", capture_kind: kind }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`${res.status}: ${detail}`);
      }
      noteLocalMutation();
      closeVialModal();
      toast(kind === "skipped" ? "Closure skipped" : "Vial saved");
      await loadMemoriesFromApi();
      renderBoard();
    });
  } catch (e) {
    toast(`Vial save failed: ${e.message}`);
  } finally {
    VIAL.saving = false;
    buttons.forEach(b => { if (b) b.disabled = false; });
  }
}

// ----- 6c. Voice capture ("Speak a task") -----
// Speech is recognized by the browser's built-in recognizer (Edge sends audio
// to Microsoft's online speech service). The transcript goes to
// POST /api/capture/parse for a draft; nothing is created until the person
// clicks Add, which calls POST /api/capture/add (see pensieve/capture).
const CAPTURE = { rec: null, listening: false, finalText: "", info: null, request: null };

function speechRecognizer() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function setCaptureHint(text, isError = false) {
  const el = $("#capture-hint");
  el.textContent = text;
  el.classList.toggle("is-error", !!isError);
}

async function openCapture() {
  CAPTURE.request = null;
  $("#capture-title").textContent = "Speak a task";
  $("#capture-modal").hidden = false;
  $("#capture-listen").hidden = false;
  $("#capture-draft").hidden = true;
  $("#capture-transcript").textContent = "";
  $("#capture-text").value = "";
  CAPTURE.finalText = "";
  const mic = $("#capture-mic");
  mic.hidden = !speechRecognizer();
  setCaptureHint(speechRecognizer()
    ? "Listening starts when you click the microphone. Say the task, for example \"Send the status report to my manager by Friday.\""
    : "Speech is not available in this browser; type the task instead.");
  try {
    CAPTURE.info = await fetchJson("/api/capture");
  } catch (_) {
    CAPTURE.info = { enabled: false, lists: [], error: "Pensieve is offline." };
  }
  if (!CAPTURE.info.enabled) {
    setCaptureHint(CAPTURE.info.error || "Adding tasks is switched off for this source.", true);
  }
  if (speechRecognizer() && CAPTURE.info.enabled) startListening();
  else $("#capture-text").focus();
}

function closeCapture() {
  stopListening();
  $("#capture-modal").hidden = true;
}

function startListening() {
  const SR = speechRecognizer();
  if (!SR || CAPTURE.listening) return;
  const rec = new SR();
  rec.lang = navigator.language || "en-US";
  rec.interimResults = true;
  rec.continuous = false;  // stops on its own after a pause
  CAPTURE.finalText = "";
  rec.onresult = e => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) CAPTURE.finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    const text = `${CAPTURE.finalText} ${interim}`.trim();
    $("#capture-transcript").textContent = text;
    $("#capture-text").value = text;
  };
  rec.onerror = e => {
    const why = {
      "not-allowed": "Microphone access is blocked. Allow it in the address-bar prompt or Edge settings, or type the task.",
      "no-speech": "Nothing heard. Click the microphone and try again.",
      "network": "The speech service could not be reached. Type the task instead.",
      "audio-capture": "No microphone was found.",
    }[e.error] || `Speech stopped (${e.error}).`;
    setCaptureHint(why, true);
  };
  rec.onend = () => {
    CAPTURE.listening = false;
    const mic = $("#capture-mic");
    mic.classList.remove("is-listening");
    mic.setAttribute("aria-pressed", "false");
    mic.setAttribute("aria-label", "Start listening");
    if (CAPTURE.finalText.trim() && !$("#capture-modal").hidden) understandCapture();
  };
  try {
    rec.start();
  } catch (_) {
    return;
  }
  CAPTURE.rec = rec;
  CAPTURE.listening = true;
  const mic = $("#capture-mic");
  mic.classList.add("is-listening");
  mic.setAttribute("aria-pressed", "true");
  mic.setAttribute("aria-label", "Stop listening");
  setCaptureHint("Listening... stop talking when you are done.");
}

function stopListening() {
  if (CAPTURE.rec && CAPTURE.listening) {
    try { CAPTURE.rec.stop(); } catch (_) { /* already stopped */ }
  }
}

async function understandCapture() {
  const text = $("#capture-text").value.trim();
  if (!text) { setCaptureHint("Say or type a task first.", true); return; }
  stopListening();
  const btn = $("#capture-understand");
  btn.disabled = true;
  setCaptureHint("Turning that into a task...");
  try {
    const res = await fetch(`${API_BASE}/api/capture/parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lists: (CAPTURE.info && CAPTURE.info.lists) || [] }),
    });
    const draft = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(draft.detail || `${res.status}`);
    showCaptureDraft(draft);
  } catch (e) {
    setCaptureHint(`Could not read that: ${e.message}`, true);
  } finally {
    btn.disabled = false;
  }
}

function showCaptureDraft(draft) {
  const info = CAPTURE.info || { lists: [] };
  $("#cap-title").value = draft.title || "";
  $("#cap-notes").value = draft.notes || "";
  $("#cap-due").value = draft.due_date || "";
  $("#cap-high").checked = draft.importance === "high";
  const chosen = draft.list_name || info.default || "";
  $("#cap-list").innerHTML = (info.lists || []).map(n =>
    `<option value="${escapeHtml(n)}"${n === chosen ? " selected" : ""}>${escapeHtml(n)}</option>`).join("");
  const where = info.source === "personal_graph" ? "Microsoft To Do" : "Outlook";
  if (CAPTURE.request) {
    $("#capture-where").textContent = `Requested by ${CAPTURE.request.from}. It will be added to ${where}, and their note will say you added it.`;
    $("#capture-listen").hidden = true;
    $("#capture-draft").hidden = false;
    $("#cap-title").focus();
    return;
  }
  $("#capture-where").textContent = draft.ai === false
    ? `The AI was unavailable, so the words became the title. It will be added to ${where}.`
    : `It will be added to ${where}. Check it, then Add.`;
  $("#capture-listen").hidden = true;
  $("#capture-draft").hidden = false;
  $("#cap-title").focus();
}

async function addCapturedTask(e) {
  e.preventDefault();
  const btn = $("#capture-add");
  btn.disabled = true;
  try {
    const url = CAPTURE.request
      ? `${API_BASE}/api/bridge/requests/${encodeURIComponent(CAPTURE.request.id)}/add`
      : `${API_BASE}/api/capture/add`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: $("#cap-title").value,
        notes: $("#cap-notes").value,
        due_date: $("#cap-due").value || null,
        list_name: $("#cap-list").value || null,
        importance: $("#cap-high").checked ? "high" : "normal",
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `${res.status}`);
    closeCapture();
    toast(`Added to ${body.list_name || "your list"}. It will surface on the board in a moment.`);
    if (body.request) refreshAgentRequests();
    if (body.sync_started) refreshAfterSync();
  } catch (err) {
    $("#capture-where").textContent = `Not added: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

// Wait for the narrow sync that capture started, then refresh the board.
async function refreshAfterSync() {
  const start = Date.now();
  while (Date.now() - start < 180000) {
    await new Promise(r => setTimeout(r, 1500));
    try {
      const st = await fetchJson("/api/sync/status");
      if (st.status !== "running") break;
    } catch (_) { break; }
  }
  refreshMemoriesIfSafe();
}

// ----- 6d. From your agents (vault bridge, see pensieve/bridge.py) -----
// Other agents (Yor, Luna, Loid) file `to: pensieve` task notes in the vault.
// They show up here; Review opens the Speak-a-task confirm card, and Pensieve
// writes the outcome back to the agent's note.
const AGENT_REQS = { enabled: false, items: [] };

function agentName(s) {
  return (s || "an agent").replace(/^./, c => c.toUpperCase());
}

async function refreshAgentRequests() {
  try {
    const st = await fetchJson("/api/bridge");
    AGENT_REQS.enabled = !!st.enabled;
    AGENT_REQS.items = st.requests || [];
  } catch (_) {
    AGENT_REQS.items = [];
  }
  const n = AGENT_REQS.items.length;
  $("#agents-btn").hidden = !AGENT_REQS.enabled || n === 0;
  $("#agents-count").textContent = String(n);
  if (!$("#agents-modal").hidden) renderAgentRequests();
}

function openAgentRequests() {
  $("#agents-modal").hidden = false;
  renderAgentRequests();
}

function closeAgentRequests() {
  $("#agents-modal").hidden = true;
}

function renderAgentRequests() {
  const items = AGENT_REQS.items;
  if (!items.length) {
    $("#agents-list").innerHTML = `<p class="empty-state">Nothing waiting. Your agents have not asked for anything.</p>`;
    return;
  }
  $("#agents-list").innerHTML = items.map(r => {
    const meta = [r.list_name, r.due_date ? `due ${r.due_date}` : "", r.importance === "high" ? "high importance" : ""]
      .filter(Boolean).map(escapeHtml).join(" &middot; ");
    const notes = r.notes && r.notes.length > 280 ? `${r.notes.slice(0, 277)}...` : r.notes;
    return `
    <article class="agent-req">
      <div class="agent-req-head">
        <span class="agent-req-from">${escapeHtml(agentName(r.from))}</span>
        <span class="agent-req-date">${escapeHtml(r.created || "")}</span>
      </div>
      <h3 class="agent-req-title">${escapeHtml(r.title)}</h3>
      ${meta ? `<p class="agent-req-meta">${meta}</p>` : ""}
      ${notes ? `<p class="agent-req-notes">${escapeHtml(notes)}</p>` : ""}
      <div class="agent-req-actions">
        <button type="button" class="ghost-button" data-req-dismiss="${escapeHtml(r.id)}">Dismiss</button>
        <button type="button" class="primary-button" data-req-review="${escapeHtml(r.id)}">Review and add</button>
      </div>
    </article>`;
  }).join("");
}

async function reviewAgentRequest(id) {
  const r = AGENT_REQS.items.find(x => x.id === id);
  if (!r) return;
  closeAgentRequests();
  CAPTURE.request = r;
  $("#capture-title").textContent = `Task from ${agentName(r.from)}`;
  $("#capture-modal").hidden = false;
  try {
    CAPTURE.info = await fetchJson("/api/capture");
  } catch (_) {
    CAPTURE.info = { enabled: false, lists: [] };
  }
  showCaptureDraft({ ...r, ai: true });
}

async function dismissAgentRequest(id, btn) {
  btn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/bridge/requests/${encodeURIComponent(id)}/dismiss`, { method: "POST" });
    if (!res.ok) throw new Error(`${res.status}`);
    toast("Dismissed. The agent's note now says so.");
  } catch (e) {
    toast(`Could not dismiss: ${e.message}`);
  }
  refreshAgentRequests();
}

// ----- 7a. Accounts ("Connect your accounts") -----
// First-run screen and More > Accounts. Each person connects their own
// Microsoft To Do and GitHub Copilot on their own PC (see pensieve/connections.py).
// Sign-ins use device codes: Pensieve shows a code, the person approves it in
// their browser, and the screen polls GET /api/connect until it lands.
const ACCOUNTS = { status: null, timer: null };

async function maybeOpenAccountsOnFirstRun() {
  try {
    const st = await fetchJson("/api/connect");
    if (!st.setup_complete && !st.dismissed) openAccounts(st);
  } catch (_) { /* older backend or offline: nothing to set up here */ }
}

async function openAccounts(prefetched) {
  $("#accounts-modal").hidden = false;
  if (prefetched) renderAccounts(prefetched);
  else {
    $("#acct-ms-body").innerHTML = $("#acct-gh-body").innerHTML = `<p class="account-wait">Checking...</p>`;
    await refreshAccounts();
  }
}

function closeAccounts() {
  $("#accounts-modal").hidden = true;
  stopAccountsPolling();
}

async function refreshAccounts() {
  try {
    renderAccounts(await fetchJson("/api/connect"));
  } catch (e) {
    $("#acct-ms-body").innerHTML = `<p class="account-error">Could not reach Pensieve (${escapeHtml(e.message)}).</p>`;
  }
}

function stopAccountsPolling() {
  if (ACCOUNTS.timer) clearTimeout(ACCOUNTS.timer);
  ACCOUNTS.timer = null;
}

function accountsPending(st) {
  // Keep polling while a sign-in is waiting for approval, or while the backend
  // is still confirming the Copilot sign-in in the background.
  return ["microsoft", "github"].some(k => st[k] && st[k].flow && st[k].flow.state === "pending")
    || !!(st.github && st.github.verifying);
}

function deviceCodeBlock(provider, flow) {
  return `
    <div class="device-code">
      <p class="device-code-step">1. Open the sign-in page. 2. Enter this code. 3. Approve Pensieve.</p>
      <div class="device-code-row">
        <code class="device-code-value" aria-label="Sign-in code">${escapeHtml(flow.user_code || "")}</code>
        <button type="button" class="ghost-button" data-acct-copy="${escapeHtml(flow.user_code || "")}">Copy code</button>
        <button type="button" class="primary-button" data-acct-open="${escapeHtml(flow.verification_uri || "")}">Open sign-in page</button>
      </div>
      <p class="account-wait">Waiting for you to approve in the browser... <button type="button" class="link-button" data-acct-cancel="${provider}">Cancel</button></p>
    </div>`;
}

function renderAccounts(st) {
  ACCOUNTS.status = st;
  const ms = st.microsoft || {};
  const gh = st.github || {};

  // Microsoft To Do
  const msBadge = $("#acct-ms-badge");
  msBadge.textContent = ms.connected ? "Connected" : (ms.configured === false ? "Not set up" : "Not connected");
  msBadge.dataset.state = ms.connected ? "on" : "off";
  let msHtml;
  if (ms.configured === false) {
    msHtml = `<p class="account-error">This copy of Pensieve has no Microsoft app id yet. Whoever shared it needs to add PERSONAL_GRAPH_CLIENT_ID (see desktop/SHARING.md).</p>`;
  } else if (ms.flow && ms.flow.state === "pending") {
    msHtml = deviceCodeBlock("microsoft", ms.flow);
  } else if (ms.connected) {
    msHtml = `<p class="account-ok">Signed in as <strong>${escapeHtml(ms.account || "your Microsoft account")}</strong>.</p>
      <button type="button" class="ghost-button" data-acct-disconnect="microsoft">Disconnect</button>`;
  } else {
    msHtml = `${ms.flow && ms.flow.error ? `<p class="account-error">${escapeHtml(ms.flow.error)}</p>` : ""}
      <button type="button" class="primary-button" data-acct-connect="microsoft">Sign in with Microsoft</button>`;
  }
  $("#acct-ms-body").innerHTML = msHtml;

  // GitHub Copilot
  const ghBadge = $("#acct-gh-badge");
  ghBadge.textContent = gh.verifying ? "Checking..." : (gh.connected ? "Connected" : "Not connected");
  ghBadge.dataset.state = gh.connected ? "on" : "off";
  let ghHtml;
  if (gh.flow && gh.flow.state === "pending") {
    ghHtml = deviceCodeBlock("github", gh.flow);
  } else if (gh.connected) {
    ghHtml = `<p class="account-ok">Using Copilot as <strong>${escapeHtml(gh.account || "your GitHub account")}</strong>${gh.note ? ` <span class="account-hint">(${escapeHtml(gh.note)})</span>` : ""}.</p>
      ${gh.managed ? "" : `<button type="button" class="ghost-button" data-acct-disconnect="github">Disconnect</button>`}`;
  } else {
    ghHtml = `${gh.flow && gh.flow.error ? `<p class="account-error">${escapeHtml(gh.flow.error)}</p>` : ""}
      <button type="button" class="primary-button" data-acct-connect="github">Sign in with GitHub</button>
      <p class="account-hint">Needs a GitHub Copilot plan (Free, Pro, or Business).</p>`;
  }
  $("#acct-gh-body").innerHTML = ghHtml;

  // Task source
  $$('input[name="task-source"]').forEach(r => { r.checked = r.value === st.source; });

  $("#accounts-done").disabled = !st.setup_complete;

  stopAccountsPolling();
  if (accountsPending(st) && !$("#accounts-modal").hidden) {
    ACCOUNTS.timer = setTimeout(refreshAccounts, 2000);
  }
}

async function accountsPost(path, body = {}, method = "POST") {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status}`);
  return data;
}

async function onAccountsClick(e) {
  const t = e.target;
  if (t.dataset.close === "accounts") { closeAccounts(); return; }
  const connect = t.closest("[data-acct-connect]");
  const disconnect = t.closest("[data-acct-disconnect]");
  const cancel = t.closest("[data-acct-cancel]");
  const open = t.closest("[data-acct-open]");
  const copy = t.closest("[data-acct-copy]");
  try {
    if (connect) {
      const provider = connect.dataset.acctConnect;
      connect.disabled = true;
      connect.textContent = provider === "github" ? "Asking GitHub for a code..." : "Asking Microsoft for a code...";
      await accountsPost(`/api/connect/${provider}/start`);
      if (provider === "microsoft" && ACCOUNTS.status && ACCOUNTS.status.source !== "personal_graph") {
        await accountsPost("/api/connect/source", { source: "personal_graph" }, "PUT");
      }
      await refreshAccounts();
    } else if (disconnect) {
      renderAccounts(await accountsPost(`/api/connect/${disconnect.dataset.acctDisconnect}/disconnect`));
    } else if (cancel) {
      renderAccounts(await accountsPost(`/api/connect/${cancel.dataset.acctCancel}/cancel`));
    } else if (open) {
      await accountsPost("/api/connect/open", { url: open.dataset.acctOpen });
    } else if (copy) {
      await navigator.clipboard.writeText(copy.dataset.acctCopy);
      toast("Code copied");
    }
  } catch (err) {
    toast(`Accounts: ${err.message}`);
    refreshAccounts();
  }
}

async function finishAccounts(dismissOnly) {
  try {
    await accountsPost("/api/connect/finish");
  } catch (_) { /* closing is still fine */ }
  closeAccounts();
  if (!dismissOnly) {
    toast("All set. Pulling your tasks now...");
    fetch(`${API_BASE}/api/sync`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
      .catch(() => {});
  }
}

// ----- 7b. AI models panel -----
// Picks the GitHub Copilot model for each job (GET/PUT /api/ai). Choices
// apply on the backend's next AI call; blank selects inherit the default.
const AI_EDIT = { state: null, models: [] };
// Purpose keys come from the backend (GET /api/ai), so new jobs appear here automatically.
function aiPurposeKeys() {
  return ((AI_EDIT.state && AI_EDIT.state.purposes) || []).map(p => p.key);
}

async function openAiModels() {
  $("#ai-modal").hidden = false;
  $("#ai-test-result").textContent = "";
  $("#ai-account").textContent = "";
  $("#ai-rows").innerHTML = `<p class="empty-state">Asking GitHub Copilot which models you can use...</p>`;
  $("#ai-save").disabled = true;
  try {
    const [state, catalog] = await Promise.all([fetchJson("/api/ai"), fetchJson("/api/ai/models")]);
    AI_EDIT.state = state;
    AI_EDIT.models = catalog.models || [];
    renderAiModels();
  } catch (e) {
    $("#ai-rows").innerHTML = `<p class="empty-state">Could not load models (${escapeHtml(e.message)}). Is the backend running and signed in to Copilot?</p>`;
  }
}

function closeAiModal() {
  $("#ai-modal").hidden = true;
}

function aiModelOptions(selected, inheritLabel) {
  const opts = [`<option value="">${escapeHtml(inheritLabel)}</option>`];
  for (const m of AI_EDIT.models) {
    const label = m.name && m.name !== m.id ? `${m.name} (${m.id})` : m.id;
    const off = m.enabled === false;
    opts.push(`<option value="${escapeHtml(m.id)}"${m.id === selected ? " selected" : ""}${off ? " disabled" : ""}>${escapeHtml(label)}${off ? " - not enabled for your account" : ""}</option>`);
  }
  // Keep a saved choice visible even if it has left the catalog.
  if (selected && !AI_EDIT.models.some(m => m.id === selected)) {
    opts.push(`<option value="${escapeHtml(selected)}" selected>${escapeHtml(selected)} (unavailable)</option>`);
  }
  return opts.join("");
}

function aiDefaultEffective() {
  const sel = $("#ai-sel-default");
  return (sel && sel.value) || AI_EDIT.state.env_default;
}

function renderAiModels() {
  const s = AI_EDIT.state;
  $("#ai-account").innerHTML = s.provider === "github_copilot"
    ? `Using GitHub Copilot as <strong>${escapeHtml(s.account || "the Copilot CLI's signed-in user")}</strong>.`
    : `Provider is <strong>${escapeHtml(s.provider)}</strong>; model choice applies to GitHub Copilot only.`;
  const rows = [
    { key: "default", label: "Default for everything", model: s.default, inherit: `Use .env default (${s.env_default})` },
    ...s.purposes.map(p => ({ key: p.key, label: p.label, model: p.model, inherit: `Use default (${s.default_effective})` })),
  ];
  const lock = s.editable ? "" : " disabled";
  $("#ai-rows").innerHTML = rows.map(r => `
    <div class="ai-row${r.key === "default" ? " ai-row--default" : ""}">
      <label class="ai-row-label" for="ai-sel-${r.key}">${escapeHtml(r.label)}</label>
      <select id="ai-sel-${r.key}" class="ai-select" data-key="${r.key}"${lock}>${aiModelOptions(r.model, r.inherit)}</select>
      <button type="button" class="ghost-button ai-test-btn" data-key="${r.key}"${lock} title="Send one tiny prompt to this model">Test</button>
    </div>`).join("");
  $("#ai-save").disabled = !s.editable;
}

// Purpose rows read "Use default (X)"; keep X in step with the Default row.
function refreshAiInheritLabels() {
  const eff = aiDefaultEffective();
  aiPurposeKeys().forEach(k => {
    const first = $(`#ai-sel-${k} option[value=""]`);
    if (first) first.textContent = `Use default (${eff})`;
  });
}

function aiModelForRow(key) {
  const sel = $(`#ai-sel-${key}`);
  if (sel && sel.value) return sel.value;
  return key === "default" ? AI_EDIT.state.env_default : aiDefaultEffective();
}

async function testAiModel(btn) {
  const model = aiModelForRow(btn.dataset.key);
  const out = $("#ai-test-result");
  btn.disabled = true;
  out.textContent = `Asking ${model}...`;
  try {
    const res = await fetch(`${API_BASE}/api/ai/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `${res.status}`);
    out.textContent = body.ok
      ? `${body.model} answered in ${body.seconds} s.`
      : `${body.model} replied, but not as expected: "${body.reply}"`;
  } catch (e) {
    out.textContent = `Test failed: ${e.message}`;
  } finally {
    btn.disabled = false;
  }
}

async function saveAiModels() {
  const payload = {};
  ["default", ...aiPurposeKeys()].forEach(k => {
    const sel = $(`#ai-sel-${k}`);
    payload[k] = sel ? sel.value : "";
  });
  const btn = $("#ai-save");
  btn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/ai`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `${res.status}`);
    AI_EDIT.state = body;
    const summary = body.purposes.map(p => `${p.label.split(" ")[0]}: ${p.effective}`).join(", ");
    toast(`AI models saved. ${summary}`);
    closeAiModal();
  } catch (e) {
    $("#ai-test-result").textContent = `Not saved: ${e.message}`;
  } finally {
    btn.disabled = false;
  }
}

// ----- 8. Goals editor -----

// The editor works on a draft copy. STATE.goals (and so the board) only
// changes on Save; closing the modal discards the draft. Before, + Add goal,
// delete, reset, and PDF import edited STATE.goals directly, so a cancelled
// edit still left a blank or deleted House on the board.
const GOALS_EDIT = { draft: [], meta: {} };

function openGoalsEditor() {
  GOALS_EDIT.draft = STATE.goals.map(g => ({ ...g }));
  GOALS_EDIT.meta = { ...(STATE.goalsMeta || {}) };
  const status = $("#goals-import-status");
  if (status) status.textContent = "";
  renderGoalsEditor();
  $("#goals-modal").hidden = false;
}

function closeGoalsModal() {
  $("#goals-modal").hidden = true;
}

function renderGoalsEditor() {
  const root = $("#goals-editor");
  root.innerHTML = GOALS_EDIT.draft.map((g, idx) => `
    <div class="goal-card"${g.lane ? ` data-lane="${escapeHtml(g.lane)}"` : ""} style="--goal-color:${escapeHtml(g.color_primary || "")}">
      <button class="goal-delete" data-idx="${idx}" title="Remove this goal" aria-label="Remove goal">&times;</button>
      <div class="goal-card-header">
        <span class="goal-lane-pill" data-lane="${escapeHtml(g.lane || "")}" style="--goal-color:${escapeHtml(g.color_primary || "")}" title="Lane: ${escapeHtml(g.lane || "none")}"><span aria-hidden="true">${houseGlyph(g.lane)}</span> ${escapeHtml(houseName(g.lane))}</span>
        <strong style="font-family:var(--font-display);font-size:13px">Goal #${g.number || idx + 1}</strong>
      </div>
      <label class="goal-input-label">Short name</label>
      <input class="goal-input" data-field="short_name" data-idx="${idx}" value="${escapeHtml(g.short_name || "")}" />
      <label class="goal-input-label">Full name</label>
      <input class="goal-input" data-field="name" data-idx="${idx}" value="${escapeHtml(g.name || "")}" />
      <label class="goal-input-label">Summary</label>
      <textarea class="goal-textarea" data-field="summary" data-idx="${idx}">${escapeHtml(g.summary || "")}</textarea>
    </div>`).join("");
  // Delete buttons are handled by one delegated listener (see init).
}

function collectEditorIntoDraft() {
  $$(".goal-input, .goal-textarea", $("#goals-editor")).forEach(input => {
    const idx = parseInt(input.dataset.idx, 10);
    const field = input.dataset.field;
    if (GOALS_EDIT.draft[idx]) GOALS_EDIT.draft[idx][field] = input.value.trim();
  });
}

async function saveGoalsFromEditor() {
  collectEditorIntoDraft();
  STATE.goals = GOALS_EDIT.draft.map(g => ({ ...g }));
  STATE.goalsMeta = GOALS_EDIT.meta;
  noteLocalMutation();
  // Persist locally first so an API outage never loses the user's edits.
  saveGoals();

  if (STATE.apiConnected) {
    try {
      const res = await fetch(`${API_BASE}/api/goals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          _meta: STATE.goalsMeta || {},
          goals: STATE.goals,
        }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`${res.status}: ${txt.slice(0, 160)}`);
      }
      const body = await res.json();
      toast(`Saved ${body.saved || STATE.goals.length} goals to server`);
    } catch (e) {
      toast(`Saved locally (server save failed: ${e.message})`);
    }
  } else {
    toast("Goals saved locally (server offline)");
  }

  closeGoalsModal();
  renderStrandFilter();
  renderBoard();
}

function resetGoals() {
  GOALS_EDIT.draft = DEFAULT_GOALS.map(g => ({ ...g }));
  renderGoalsEditor();
  toast("Defaults loaded. Save goals to keep them.");
}

function addGoalToState() {
  collectEditorIntoDraft();
  const number = (GOALS_EDIT.draft.length || 0) + 1;
  const palette = LANE_PALETTE[(number - 1) % LANE_PALETTE.length];
  const stamp = Date.now().toString(36);
  GOALS_EDIT.draft.push({
    id: `goal-${number}-new-${stamp}`,
    number,
    short_name: "",
    name: "",
    summary: "",
    lane: palette.lane,
    color_primary: palette.color_primary,
    color_accent: palette.color_accent,
    success_criteria: [],
    impact_statement: "",
    keywords_for_alignment: [],
  });
  renderGoalsEditor();
  const inputs = $$(".goal-input[data-field='short_name']", $("#goals-editor"));
  if (inputs.length) inputs[inputs.length - 1].focus();
}

function deleteGoalAt(idx) {
  collectEditorIntoDraft();
  if (idx < 0 || idx >= GOALS_EDIT.draft.length) return;
  GOALS_EDIT.draft.splice(idx, 1);
  // Re-number so the editor + saved JSON stay in order. Lane assignments
  // are left as-is so existing memories aligned to a goal id keep their color.
  GOALS_EDIT.draft.forEach((g, i) => { g.number = i + 1; });
  renderGoalsEditor();
}

async function uploadConnectPdf(file) {
  const status = $("#goals-import-status");
  const btn = $("#goals-import-btn");
  if (!STATE.apiConnected) {
    if (status) status.textContent = "Need the API server (run `pensieve serve`)";
    return;
  }
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) {
    if (status) status.textContent = "PDF too large (max 5 MB)";
    return;
  }
  if (status) status.textContent = "Reading PDF and asking the AI...";
  if (btn) { btn.disabled = true; btn.classList.add("is-parsing"); }

  try {
    const fd = new FormData();
    fd.append("file", file, file.name);
    const res = await fetch(`${API_BASE}/api/goals/import`, { method: "POST", body: fd });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`${res.status}: ${txt.slice(0, 200)}`);
    }
    const body = await res.json();
    const proposal = body.proposal || {};
    const goals = Array.isArray(proposal.goals) ? proposal.goals : [];
    if (!goals.length) throw new Error("No goals found in PDF");
    // Load the proposal into the editor draft; nothing changes until Save.
    GOALS_EDIT.draft = goals.map(g => ({ ...g }));
    GOALS_EDIT.meta = proposal._meta || {};
    renderGoalsEditor();
    if (status) {
      const notes = (proposal._meta && proposal._meta.extraction_notes) || "";
      status.textContent = `Parsed ${goals.length} goals. Review and Save.` + (notes ? ` (${notes})` : "");
    }
  } catch (e) {
    if (status) status.textContent = `Parse failed: ${e.message}`;
  } finally {
    if (btn) { btn.disabled = false; btn.classList.remove("is-parsing"); }
  }
}

// ----- 9. Drag + drop -----
// All card and column listeners are delegated from #board and bound once in
// wireBoardEvents, so re-renders never re-bind (or leak) handlers.

function resetDragState() {
  return { id: null, fromCol: null, el: null, overCol: null };
}

// Drop targets are real board columns only (they carry data-column); the
// "Add a House" tile has none, so it never accepts a card.
function dropColumnAt(target) {
  return target && target.closest ? target.closest("#board .column[data-column]") : null;
}

function markDropTarget(col) {
  if (DRAG.overCol === col) return;
  if (DRAG.overCol) DRAG.overCol.classList.remove("drop-target");
  DRAG.overCol = col;
  if (col) col.classList.add("drop-target");
}

function endDrag() {
  markDropTarget(null);
  if (DRAG.el) DRAG.el.classList.remove("dragging");
  DRAG = resetDragState();
  FOOTPRINT.last = null;
  if (STATE.renderPending) renderBoard();
}

function wireBoardEvents() {
  const board = $("#board");

  board.addEventListener("click", e => {
    // Chevron / badge clicks open the Vial modal (document-level delegate).
    if (e.target.closest(".card-vial-chevron, .card-vial-badge")) return;
    const card = e.target.closest(".card");
    if (!card || card.classList.contains("dragging")) return;
    openCardById(card.dataset.memoryId);
  });

  board.addEventListener("keydown", e => {
    if (e.key !== "Enter" && e.key !== " ") return;
    if (!e.target.classList || !e.target.classList.contains("card")) return;
    e.preventDefault();
    openCardById(e.target.dataset.memoryId);
  });

  board.addEventListener("dragstart", e => {
    const card = e.target.closest && e.target.closest(".card");
    if (!card) return;
    DRAG = resetDragState();
    DRAG.id = card.dataset.memoryId;
    DRAG.fromCol = card.closest(".column")?.dataset.column || null;
    DRAG.el = card;
    card.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", DRAG.id); } catch (_) { /* ignore */ }
  });

  // dragend fires on the source card; a drop that re-rendered the card away
  // already ran endDrag() itself.
  board.addEventListener("dragend", () => { if (DRAG.id) endDrag(); });

  board.addEventListener("dragover", e => {
    const col = DRAG.id ? dropColumnAt(e.target) : null;
    markDropTarget(col);
    if (col) {
      e.preventDefault();  // allow the drop here
      e.dataTransfer.dropEffect = "move";
    }
  });

  board.addEventListener("dragleave", e => {
    if (!DRAG.id) return;
    if (!e.relatedTarget || !board.contains(e.relatedTarget)) markDropTarget(null);
  });

  board.addEventListener("drop", e => {
    const col = dropColumnAt(e.target);
    if (!col) return;
    e.preventDefault();
    const memId = DRAG.id || e.dataTransfer.getData("text/plain");
    const fromCol = DRAG.fromCol;
    endDrag();
    if (memId) moveMemoryTo(memId, fromCol, col.dataset.column);
  });
}

function sameIds(a, b) {
  return a.length === b.length && a.every((id, i) => id === b[i]);
}

function moveMemoryTo(memId, fromCol, target) {
  const m = STATE.memories.find(x => x.id === memId);
  if (!m || !target) return;

  if (STATE.view === "lifecycle") {
    // Dropped back where it started: nothing to save, and no needless
    // writeback (or "tended" bump) for a card that did not move.
    if (m.column === target) return;
    noteLocalMutation();
    m.column = target;
    renderBoard();
    persistColumnChange(m.id, target);
    return;
  }

  // Houses view: dropping on a House makes it the card's primary House and
  // moves the card out of the House it was dragged from (other alignments
  // stay). Dropping on Unhoused clears every alignment.
  const before = Array.isArray(m.connect_goal_ids) ? m.connect_goal_ids : [];
  const next = target === "unassigned"
    ? []
    : [target, ...before.filter(id => id !== target && id !== fromCol)];
  if (sameIds(before, next)) return;
  noteLocalMutation();
  m.connect_goal_ids = next;
  renderBoard();
  persistGoalAlignment(m.id, next);
}

// Footprint trail: while a card is dragged, faint footprints are stamped under
// the cursor and fade out. They are spaced by distance travelled (not by event
// count), so a resting cursor does not pile prints on one spot. Cosmetic only.
const FOOTPRINT = { last: null, step: 26 };
document.addEventListener("dragover", e => {
  if (!DRAG.id || prefersReducedMotion()) return;
  const last = FOOTPRINT.last;
  if (last && Math.hypot(e.clientX - last.x, e.clientY - last.y) < FOOTPRINT.step) return;
  FOOTPRINT.last = { x: e.clientX, y: e.clientY };
  const layer = $("#footprint-layer");
  if (!layer) return;
  const fp = document.createElement("div");
  fp.className = "footprint";
  fp.style.left = `${e.clientX}px`;
  fp.style.top = `${e.clientY}px`;
  fp.style.setProperty("--rot", `${Math.floor(Math.random() * 60 - 30)}deg`);
  fp.addEventListener("animationend", () => fp.remove(), { once: true });
  layer.appendChild(fp);
  setTimeout(() => fp.remove(), 1800);  // backstop if the animation never runs
});

// ----- 9a. Ambient motion: the Snitch's flights -----
// The Snitch only animates while it is actually on screen: it rests
// off-screen and flits across now and then (CSS .snitch.is-flying), so the
// page is not producing frames all day while nothing visible changes.
const SNITCH_FLIGHT_MS = 28000;          // matches snitch-drift in pensieve.css
const SNITCH_REST_MS = [15000, 45000];   // random rest between flights

function initAmbientMotion() {
  if (prefersReducedMotion()) return;  // CSS already hides the Snitch
  const snitch = $(".snitch");
  if (snitch) {
    const rest = () => SNITCH_REST_MS[0] + Math.random() * (SNITCH_REST_MS[1] - SNITCH_REST_MS[0]);
    const fly = () => {
      if (document.hidden || STATE.theme === "marauder") {
        setTimeout(fly, rest());
        return;
      }
      snitch.classList.add("is-flying");
      setTimeout(() => {
        snitch.classList.remove("is-flying");
        setTimeout(fly, rest());
      }, SNITCH_FLIGHT_MS + 100);
    };
    setTimeout(fly, 4000);  // first flight shortly after load
  }
}

// ----- 9b. Easter egg: the Marauder's Map -----
// Type the oath anywhere outside a text field to reveal the map; type
// "mischief managed" to fold it away again.

const SWEAR = "i solemnly swear that i am up to no good";
const MANAGED = "mischief managed";

document.addEventListener("keydown", e => {
  const t = e.target;
  if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key.length !== 1) {
    if (e.key === "Backspace") STATE.easterBuffer = STATE.easterBuffer.slice(0, -1);
    return;
  }
  STATE.easterBuffer = (STATE.easterBuffer + e.key.toLowerCase()).slice(-60);
  if (STATE.easterBuffer.endsWith(SWEAR)) {
    STATE.easterBuffer = "";
    setTheme("marauder", "I solemnly swear I am up to no good");
  } else if (STATE.easterBuffer.endsWith(MANAGED)) {
    STATE.easterBuffer = "";
    setTheme(STATE.theme === "marauder" ? "day" : STATE.theme, "Mischief managed");
  }
});

// ----- 10. Toast -----

let toastTimer = null;
let toastHideTimer = null;
function toast(msg) {
  const t = $("#toast");
  if (!t) return;
  t.textContent = msg;
  t.hidden = false;
  requestAnimationFrame(() => t.classList.add("show"));
  // Cancel both timers: a toast fired during the previous one's fade-out used
  // to be hidden 350ms later by that fade's leftover timer.
  clearTimeout(toastTimer);
  clearTimeout(toastHideTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("show");
    toastHideTimer = setTimeout(() => { t.hidden = true; }, 350);
  }, 2200);
}

// ----- 12. Wire up -----

function init() {
  // Start the API round trip first so it overlaps with the first render.
  // Until it answers, the board shows empty column shells ("Stirring the
  // memories..."); seed cards only appear if the API is unreachable.
  const firstLoad = loadMemoriesFromApi();

  initDensityToggle();
  applyTheme();
  wireBoardEvents();
  renderStrandFilter();
  applyView();
  applyWeeklyFilterState();
  initHeaderPopovers();
  updateFilterBadge();
  initAmbientMotion();

  firstLoad.then(ok => {
    renderStrandFilter();
    STATE.inkNextRender = true;  // ink the live memories onto the page
    renderBoard();
    try { performance.mark("pensieve:board-live"); } catch (_) { /* ignore */ }
    setFooterSource();
    if (ok) maybeOpenAccountsOnFirstRun();
    if (!ok) {
      toast(`API offline, using seed data. Start with: pensieve serve`);
    }
  });

  // Begin the auto-refresh loop (see refreshMemoriesIfSafe for guards).
  startAutoRefreshLoop();

  // Text filter (fast in-memory match), coalesced so a burst of keystrokes
  // costs one board pass.
  let searchTimer = null;
  $("#search").addEventListener("input", e => {
    STATE.filter.search = e.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(renderBoard, 80);
  });

  // Strand pills live in the Filter popover and are re-rendered in place;
  // one delegated listener handles them.
  $("#strand-filter").addEventListener("click", e => {
    const pill = e.target.closest(".strand-pill");
    if (!pill) return;
    const id = pill.dataset.strand;
    STATE.filter.strand = STATE.filter.strand === id ? null : id;
    renderStrandFilter();
    renderBoard();
  });

  // Semantic search (Enter key on the search input runs a Chroma query)
  $("#search").addEventListener("keydown", e => {
    if (e.key === "Enter") {
      e.preventDefault();
      runSemanticSearch(e.target.value);
    }
  });

  // Semantic-search button (header)
  const semBtn = $("#semantic-btn");
  if (semBtn) {
    semBtn.addEventListener("click", () => {
      runSemanticSearch($("#search").value);
    });
  }

  // Click filter from Board Health pill -> show only stale/ghost/overdue
  const boardHealthEl = document.getElementById("board-health");
  if (boardHealthEl) {
    boardHealthEl.addEventListener("click", toggleBoardHealthFilter);
    boardHealthEl.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleBoardHealthFilter();
      }
    });
    const tipEl = document.getElementById("board-health-tip");
    if (tipEl) {
      const show = () => { tipEl.hidden = false; };
      const hide = () => { tipEl.hidden = true; };
      boardHealthEl.addEventListener("mouseenter", show);
      boardHealthEl.addEventListener("mouseleave", hide);
      boardHealthEl.addEventListener("focus", show);
      boardHealthEl.addEventListener("blur", hide);
    }
  }

  // Clear filters
  $("#clear-filters").addEventListener("click", () => {
    STATE.filter = { strand: null, search: "", reviewOnly: false, boardHealthOffenders: false, questTargetIds: null };
    supersede("search");  // a semantic query still in flight must not re-apply itself
    STATE.semanticResultIds = null;
    STATE.semanticQuery = "";
    $("#search").value = "";
    renderStrandFilter();
    renderBoardHealth();
    renderQuestPanel();
    renderBoard();
  });

  // Click (or Enter/Space on) Hedwig to filter the board to review-flagged cards.
  const reviewBlock = document.querySelector(".review-block");
  if (reviewBlock) {
    reviewBlock.addEventListener("click", toggleReviewOnlyFilter);
    reviewBlock.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleReviewOnlyFilter();
      }
    });
  }

  // Weekly filter toggle (Closed column rolls over each Monday)
  const weeklyBtn = $("#weekly-filter-btn");
  if (weeklyBtn) {
    weeklyBtn.addEventListener("click", () => {
      STATE.weeklyFilter = !STATE.weeklyFilter;
      try { localStorage.setItem("pensieve-weekly", STATE.weeklyFilter ? "1" : "0"); } catch (e) { /* ignore */ }
      applyWeeklyFilterState();
      renderBoard();
      toast(STATE.weeklyFilter ? "Showing Closed from this week only" : "Showing all Closed tasks");
    });
  }

  // Refresh from API
  const refreshBtn = $("#refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      toast("Refreshing from API...");
      await loadMemoriesFromApi();
      renderStrandFilter();
      renderBoard();
      setFooterSource();
      toast(STATE.apiConnected ? "Memories refreshed" : "API offline");
    });
  }

  // Pull from Microsoft To-Do (Outlook) -> kicks off backend sync
  const pullTodoBtn = $("#pull-todo-btn");
  if (pullTodoBtn) {
    pullTodoBtn.addEventListener("click", async () => {
      if (pullTodoBtn.disabled) return;
      pullTodoBtn.disabled = true;
      const original = pullTodoBtn.innerHTML;
      pullTodoBtn.innerHTML = "&#x1F989; Hedwig is flying...";
      pullTodoBtn.classList.add("is-pulling");
      try {
        const res = await fetch(`${API_BASE}/api/sync`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ source: "outlook_com" }),
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(`${res.status}: ${text.slice(0, 120)}`);
        }
        const body = await res.json();
        if (body.already_running) {
          toast("A sync is already in flight - waiting for it to finish");
        } else {
          toast("Pulling from Microsoft To-Do...");
        }
        await pollSyncUntilDone(pullTodoBtn);
        await loadMemoriesFromApi();
        renderStrandFilter();
        renderBoard();
        setFooterSource();
      } catch (e) {
        toast(`Pull failed: ${e.message}`);
      } finally {
        pullTodoBtn.disabled = false;
        pullTodoBtn.innerHTML = original;
        pullTodoBtn.classList.remove("is-pulling");
      }
    });
  }

  // View toggle
  $$(".view-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (STATE.view === btn.dataset.view) return;  // no ink replay on a no-op click
      STATE.view = btn.dataset.view;
      applyView();
    });
  });

  // Theme toggle (day <-> night; marauder is easter-egg only, the toggle folds it back to day)
  const themeBtn = $("#theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const next = STATE.theme === "day" ? "night" : "day";
      setTheme(next, `${next} mode`);
    });
  }

  // From your agents
  $("#agents-btn").addEventListener("click", openAgentRequests);
  $("#agents-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "agents") { closeAgentRequests(); return; }
    const review = e.target.closest("[data-req-review]");
    const dismiss = e.target.closest("[data-req-dismiss]");
    if (review) reviewAgentRequest(review.dataset.reqReview);
    else if (dismiss) dismissAgentRequest(dismiss.dataset.reqDismiss, dismiss);
  });
  refreshAgentRequests();
  setInterval(() => { if (!document.hidden) refreshAgentRequests(); }, 120000);

  // Voice capture
  $("#speak-btn").addEventListener("click", openCapture);
  $("#capture-mic").addEventListener("click", () => (CAPTURE.listening ? stopListening() : startListening()));
  $("#capture-understand").addEventListener("click", understandCapture);
  $("#capture-again").addEventListener("click", () => openCapture());
  $("#capture-draft").addEventListener("submit", addCapturedTask);
  $("#capture-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "capture") closeCapture();
  });
  $("#capture-text").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); understandCapture(); }
  });

  // Accounts
  $("#open-accounts").addEventListener("click", () => openAccounts());
  $("#accounts-modal").addEventListener("click", onAccountsClick);
  $("#accounts-modal").addEventListener("change", async e => {
    if (e.target.name !== "task-source") return;
    try {
      renderAccounts(await accountsPost("/api/connect/source", { source: e.target.value }, "PUT"));
    } catch (err) {
      toast(`Accounts: ${err.message}`);
    }
  });
  $("#accounts-done").addEventListener("click", () => finishAccounts(false));
  $("#accounts-skip").addEventListener("click", () => finishAccounts(true));

  // AI models panel
  $("#open-ai-models").addEventListener("click", openAiModels);
  $("#ai-save").addEventListener("click", saveAiModels);
  $("#ai-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "ai") { closeAiModal(); return; }
    const test = e.target.closest(".ai-test-btn");
    if (test) testAiModel(test);
  });
  $("#ai-modal").addEventListener("change", e => {
    if (e.target.id === "ai-sel-default") refreshAiInheritLabels();
  });

  // Goals editor
  $("#open-goals").addEventListener("click", openGoalsEditor);
  $("#goals-save").addEventListener("click", saveGoalsFromEditor);
  $("#goals-reset").addEventListener("click", resetGoals);
  const addBtn = $("#goals-add");
  if (addBtn) addBtn.addEventListener("click", addGoalToState);

  // PDF import
  const pdfInput = $("#goals-pdf-input");
  const importBtn = $("#goals-import-btn");
  const status = $("#goals-import-status");
  if (pdfInput && importBtn) {
    pdfInput.addEventListener("change", e => {
      const file = e.target.files && e.target.files[0];
      importBtn.disabled = !file;
      if (status) status.textContent = file ? `Ready: ${file.name}` : "";
    });
    importBtn.addEventListener("click", () => {
      const file = pdfInput.files && pdfInput.files[0];
      if (file) uploadConnectPdf(file);
    });
  }

  // Page tabs (Board / Recap)
  $$(".page-tab").forEach(btn => {
    btn.addEventListener("click", () => switchPage(btn.dataset.page));
  });
  const recapGen = $("#recap-generate");
  if (recapGen) recapGen.addEventListener("click", generateRecap);
  const recapExport = $("#recap-export");
  if (recapExport) recapExport.addEventListener("click", exportRecapDocx);
  const recapHistBtn = $("#recap-history-btn");
  if (recapHistBtn) recapHistBtn.addEventListener("click", toggleRecapHistory);

  // Graph page controls
  wireGraphInteraction();
  const gThresh = $("#graph-threshold");
  if (gThresh) {
    gThresh.addEventListener("input", () => {
      const v = parseFloat(gThresh.value).toFixed(2);
      const label = $("#graph-threshold-val");
      if (label) label.textContent = v;
    });
    gThresh.addEventListener("change", () => { if (STATE.page === "graph") loadGraph(); });
  }
  const gRefresh = $("#graph-refresh");
  if (gRefresh) gRefresh.addEventListener("click", loadGraph);

  // Docs page controls
  const docsNew = $("#docs-new");
  if (docsNew) docsNew.addEventListener("click", newDoc);
  const docsEdit = $("#docs-edit");
  if (docsEdit) docsEdit.addEventListener("click", () => { setDocsMode(true); $("#docs-editor").focus(); });
  const docsSave = $("#docs-save");
  if (docsSave) docsSave.addEventListener("click", saveDoc);
  const docsCancel = $("#docs-cancel");
  if (docsCancel) docsCancel.addEventListener("click", () => { if (DOCS.current) openDoc(DOCS.current); });
  const docsDelete = $("#docs-delete");
  if (docsDelete) docsDelete.addEventListener("click", deleteDoc);

  // Modal close
  $("#card-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "1") closeModal();
  });
  $("#goals-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "goals") closeGoalsModal();
  });
  $("#goals-editor").addEventListener("click", e => {
    const del = e.target.closest(".goal-delete");
    if (!del) return;
    e.preventDefault();
    deleteGoalAt(parseInt(del.dataset.idx, 10));
  });
  $("#vial-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "vial") closeVialModal();
  });
  $("#vial-save").addEventListener("click", () => saveVial("captured"));
  $("#vial-skip").addEventListener("click", () => saveVial("skipped"));

  // Garden v3: achievements button + modal.
  const achBtn = document.getElementById("achievements-btn");
  if (achBtn) achBtn.addEventListener("click", openAchievementsModal);
  const achModal = document.getElementById("achievements-modal");
  if (achModal) {
    achModal.addEventListener("click", e => {
      if (e.target.dataset.close === "achievements") closeAchievementsModal();
    });
  }

  // Delegate chevron/badge clicks on the kanban board
  document.addEventListener("click", e => {
    const chevron = e.target.closest(".card-vial-chevron, .card-vial-badge");
    if (chevron) {
      e.stopPropagation();
      openVialModal(chevron.dataset.memoryId);
    }
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      closeModal();
      closeGoalsModal();
      closeVialModal();
      closeAchievementsModal();
      closeAiModal();
      closeAccounts();
      closeCapture();
      closeAgentRequests();
    }
  });
}

// ----- Recap page (Phase 3: Connect recap) -----

function switchPage(page) {
  const known = ["recap", "graph", "docs"];
  const next = known.includes(page) ? page : "board";
  if (next === STATE.page) return;  // re-clicking the active tab is a no-op
  STATE.page = next;
  document.documentElement.setAttribute("data-page", STATE.page);
  $$(".page-tab").forEach(btn => {
    const on = btn.dataset.page === STATE.page;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  if (STATE.page === "graph") loadGraph();
  else stopGraphAnim();
  if (STATE.page === "docs") loadDocs();
  if (STATE.page === "board") {
    // The board skipped renders and polls while hidden; catch up now.
    if (STATE.boardDirty) renderBoard();
    refreshMemoriesIfSafe();
  }
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    return false;
  }
}

function blockToText(b) {
  const lines = [];
  if (b.heading) lines.push(b.heading);
  if (b.narrative) lines.push(b.narrative);
  if (b.impact) lines.push(`Impact: ${b.impact}`);
  return lines.join("\n\n");
}

function recapToText(recap) {
  const out = [];
  if (recap.period_label) out.push(`Reflection Period: ${recap.period_label}\n`);
  if (Array.isArray(recap.list_names_applied) && recap.list_names_applied.length) {
    out.push(`Included lists: ${recap.list_names_applied.join(", ")}\n`);
  }
  (recap.sections || []).forEach(s => {
    out.push(`=== ${s.short_name || s.name} ===`);
    (s.accomplishments || []).forEach(b => out.push(blockToText(b)));
    out.push("");
  });
  return out.join("\n\n").trim();
}

async function generateRecap() {
  const btn = $("#recap-generate");
  const status = $("#recap-status");
  const output = $("#recap-output");
  if (!STATE.apiConnected) {
    toast("Recap needs the Pensieve API. Start `pensieve serve` and refresh.");
    return;
  }
  const scope = $("#recap-scope").value || "all";
  const period = $("#recap-period").value.trim();
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = "Drafting...";
  if (status) status.textContent = "Calling the model, this can take a moment...";
  try {
    const res = await fetch(`${API_BASE}/api/recap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, period_label: period }),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    const data = await res.json();
    STATE.lastRecap = data.recap;
    STATE.lastScope = scope;
    renderRecap(data.recap);
    const r = data.recap || {};
    if (status) {
      const lists = Array.isArray(r.list_names_applied) && r.list_names_applied.length
        ? ` Lists: ${r.list_names_applied.join(", ")}.`
        : "";
      status.textContent =
        `${r.section_count || 0} goal section(s) from ${r.memories_considered || 0} task(s).${lists} ` +
        `${r.tokens_used || 0} tokens.`;
    }
    refreshRecapHistory();
  } catch (e) {
    if (status) status.textContent = "";
    output.innerHTML = `<p class="recap-empty">Recap failed: ${e.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = original;
  }
}

function recapBlocksHtml(s) {
  return (s.accomplishments || [])
    .map((b, i) => `
      <article class="recap-block" data-block="${i}">
        <div class="recap-block-head">
          <h3>${escapeHtml(b.heading || "Accomplishment")}</h3>
          <button class="ghost-button recap-copy" data-block="${i}" title="Copy this block">Copy</button>
        </div>
        <p class="recap-narrative">${escapeHtml(b.narrative || "")}</p>
        ${b.impact ? `<p class="recap-impact"><strong>Impact:</strong> ${escapeHtml(b.impact)}</p>` : ""}
      </article>`)
    .join("") || '<p class="recap-impact">No accomplishment drafted.</p>';
}

function wireRecapSectionCopies(section, s) {
  section.querySelectorAll(".recap-copy").forEach(btn => {
    btn.addEventListener("click", async () => {
      const idx = parseInt(btn.dataset.block, 10);
      const block = (s.accomplishments || [])[idx];
      if (!block) return;
      const ok = await copyToClipboard(blockToText(block));
      toast(ok ? "Block copied" : "Copy failed");
    });
  });
}

async function reviseSection(section, s) {
  const fb = section.querySelector(".recap-revise-input");
  const btn = section.querySelector(".recap-revise-send");
  const feedback = (fb.value || "").trim();
  if (!feedback) { toast("Type what should change first."); return; }
  const orig = btn.textContent;
  btn.disabled = true; btn.textContent = "Rewriting...";
  try {
    const res = await fetch(`${API_BASE}/api/recap/revise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal_id: s.goal_id, feedback, scope: STATE.lastScope || "all" }),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    const data = await res.json();
    const newSection = data.section;
    // update in-memory recap + re-render this section's blocks
    s.accomplishments = newSection.accomplishments || [];
    if (STATE.lastRecap && STATE.lastRecap.sections) {
      const idx = STATE.lastRecap.sections.findIndex(x => x.goal_id === s.goal_id);
      if (idx >= 0) STATE.lastRecap.sections[idx] = s;
    }
    section.querySelector(".recap-blocks").innerHTML = recapBlocksHtml(s);
    wireRecapSectionCopies(section, s);
    section.querySelector(".recap-revise").hidden = true;
    fb.value = "";
    toast("Section rewritten");
  } catch (e) {
    toast(`Revise failed: ${e.message}`);
  } finally {
    btn.disabled = false; btn.textContent = orig;
  }
}

function renderRecap(recap) {
  const output = $("#recap-output");
  const copyAll = $("#recap-copy-all");
  const exportBtn = $("#recap-export");
  STATE.lastRecap = recap;
  output.innerHTML = "";
  const sections = (recap && recap.sections) || [];
  if (sections.length === 0) {
    output.innerHTML =
      `<p class="recap-empty">No tasks matched this scope. Try "All tasks", or sync more from To-Do.</p>`;
    if (copyAll) copyAll.hidden = true;
    if (exportBtn) exportBtn.hidden = true;
    return;
  }

  sections.forEach(s => {
    const section = document.createElement("section");
    section.className = "recap-section";
    if (s.lane) section.dataset.lane = s.lane;

    const sourcesHtml = (s.task_titles && s.task_titles.length)
      ? `<details class="recap-sources">
           <summary>Source tasks (${s.task_titles.length})</summary>
           <ul>${s.task_titles.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>
         </details>`
      : "";

    section.innerHTML = `
      <div class="recap-section-head">
        <h2>${escapeHtml(s.short_name || s.name || "Goal")}</h2>
        <span class="recap-goal-name">${escapeHtml(s.name || "")}</span>
        <span class="recap-task-count">${s.task_count || 0} task(s)</span>
        <button class="ghost-button recap-revise-toggle" title="Tell the agent it misread something and rewrite">Revise</button>
      </div>
      <div class="recap-blocks">${recapBlocksHtml(s)}</div>
      <div class="recap-revise" hidden>
        <textarea class="recap-revise-input" rows="2" placeholder="e.g. 'That task was about NIS2 testing for a peer team, not a status report' - then Rewrite."></textarea>
        <button class="primary-button recap-revise-send">Rewrite this section</button>
      </div>
      ${sourcesHtml}`;

    wireRecapSectionCopies(section, s);

    const toggle = section.querySelector(".recap-revise-toggle");
    const reviseBox = section.querySelector(".recap-revise");
    const openRevise = () => {
      reviseBox.hidden = !reviseBox.hidden;
      if (!reviseBox.hidden) section.querySelector(".recap-revise-input").focus();
    };
    toggle.addEventListener("click", openRevise);
    section.addEventListener("dblclick", e => {
      if (e.target.closest("button, textarea, a, details")) return;
      reviseBox.hidden = false;
      section.querySelector(".recap-revise-input").focus();
    });
    section.querySelector(".recap-revise-send").addEventListener("click", () => reviseSection(section, s));

    output.appendChild(section);
  });

  if (copyAll) {
    copyAll.hidden = false;
    copyAll.onclick = async () => {
      const ok = await copyToClipboard(recapToText(recap));
      toast(ok ? "Full recap copied" : "Copy failed");
    };
  }
  if (exportBtn) exportBtn.hidden = false;
}

async function exportRecapDocx() {
  if (!STATE.lastRecap || !(STATE.lastRecap.sections || []).length) {
    toast("Generate a recap first."); return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/recap/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recap: STATE.lastRecap }),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "connect-recap.docx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast("DOCX downloaded");
  } catch (e) {
    toast(`Export failed: ${e.message}`);
  }
}

async function refreshRecapHistory() {
  const panel = $("#recap-history");
  if (!panel || panel.hidden) return;  // only refresh when visible
  await renderRecapHistory();
}

async function renderRecapHistory() {
  const panel = $("#recap-history");
  if (!panel) return;
  try {
    const data = await fetchJson("/api/recap/history");
    const runs = data.runs || [];
    if (!runs.length) {
      panel.innerHTML = `<p class="recap-empty" style="padding:12px">No saved recaps yet.</p>`;
      return;
    }
    panel.innerHTML = `<div class="recap-history-list">` + runs.map(r => `
      <button class="recap-history-item" data-id="${r.id}">
        <span class="rh-date">${escapeHtml((r.created_at || "").replace("T", " ").slice(0, 16))}</span>
        <span class="rh-meta">${escapeHtml(r.scope || "all")} &middot; ${r.section_count || 0} sections &middot; ${r.memories_considered || 0} tasks</span>
        ${r.period_label ? `<span class="rh-period">${escapeHtml(r.period_label)}</span>` : ""}
      </button>`).join("") + `</div>`;
    panel.querySelectorAll(".recap-history-item").forEach(btn => {
      btn.addEventListener("click", () => loadHistoryRun(btn.dataset.id));
    });
  } catch (e) {
    panel.innerHTML = `<p class="recap-empty" style="padding:12px">History failed: ${escapeHtml(e.message)}</p>`;
  }
}

async function loadHistoryRun(id) {
  try {
    const data = await fetchJson(`/api/recap/history/${encodeURIComponent(id)}`);
    const recap = data.record && data.record.recap;
    if (!recap) { toast("Could not load that run."); return; }
    STATE.lastScope = recap.scope || "all";
    renderRecap(recap);
    const status = $("#recap-status");
    if (status) status.textContent = `Loaded saved recap from ${(data.record.created_at || "").replace("T", " ").slice(0, 16)}.`;
    $("#recap-history").hidden = true;
  } catch (e) {
    toast(`Load failed: ${e.message}`);
  }
}

function toggleRecapHistory() {
  const panel = $("#recap-history");
  if (!panel) return;
  panel.hidden = !panel.hidden;
  if (!panel.hidden) renderRecapHistory();
}

// ----- Constellation graph page -----

const GRAPH = {
  nodes: [], edges: [], byId: {},
  raf: null, dragging: null, hover: null, downAt: null, moved: false,
  width: 1200, height: 620, dpr: 1,
  ticksLeft: 0, calmFrames: 0,
  pal: null,  // cached theme palette; applyTheme clears it
};

// The simulation stops early once every node moves less than ~0.1px a frame
// for a few frames in a row, instead of always burning the full tick budget.
const GRAPH_CALM_ENERGY = 0.01;  // mean squared speed per node, px^2 / frame^2
const GRAPH_CALM_FRAMES = 12;

function stopGraphAnim() {
  if (GRAPH.raf) { cancelAnimationFrame(GRAPH.raf); GRAPH.raf = null; }
}

async function loadGraph() {
  const canvas = $("#graph-canvas");
  const empty = $("#graph-empty");
  if (!canvas) return;
  // If the user opens Graph before the initial API load finished, try once.
  if (!STATE.apiConnected) await loadMemoriesFromApi();
  if (!STATE.apiConnected) {
    empty.hidden = false;
    empty.textContent = "Graph needs the Pensieve API. Start `pensieve serve` and refresh.";
    return;
  }
  const threshold = parseFloat(($("#graph-threshold") || {}).value || "0.6");
  const signal = supersede("graph");
  try {
    const data = await fetchJson(`/api/graph?threshold=${threshold}`, { signal });
    if (STATE.page !== "graph") return;  // left the tab while it loaded
    const g = data.graph || { nodes: [], edges: [], stats: {} };
    renderGraphStats(g.stats || {});
    if (!g.nodes.length) {
      empty.hidden = false;
      empty.textContent = "No tasks to plot yet. Pull from To-Do on the Board first.";
      stopGraphAnim();
      return;
    }
    empty.hidden = true;
    initGraphLayout(g);
    startGraph();
  } catch (e) {
    if (isAbortError(e)) return;
    empty.hidden = false;
    empty.textContent = `Graph failed: ${e.message}`;
  }
}

function sizeGraphCanvas() {
  const canvas = $("#graph-canvas");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  GRAPH.width = Math.max(320, Math.floor(rect.width));
  GRAPH.height = 620;
  GRAPH.dpr = dpr;
  canvas.width = GRAPH.width * dpr;
  canvas.height = GRAPH.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function initGraphLayout(g) {
  sizeGraphCanvas();
  const cx = GRAPH.width / 2, cy = GRAPH.height / 2;
  const goals = g.nodes.filter(n => n.type === "goal");
  const ringR = Math.min(GRAPH.width, GRAPH.height) * 0.32;
  // Nodes that were already on screen keep their position, so coming back to
  // the tab (or Rebuild) settles in place instead of re-exploding the layout.
  const prev = GRAPH.byId || {};
  let known = 0;
  const placed = {};
  goals.forEach((n, i) => {
    const a = (i / Math.max(1, goals.length)) * Math.PI * 2 - Math.PI / 2;
    n.ax = cx + ringR * Math.cos(a);
    n.ay = cy + ringR * Math.sin(a);
    const old = prev[n.id];
    if (old) { n.x = old.x; n.y = old.y; known++; } else { n.x = n.ax; n.y = n.ay; }
    n.vx = 0; n.vy = 0;
    placed[n.id] = n;
  });
  // tasks: start near their first goal (or center), with jitter
  g.nodes.filter(n => n.type === "task").forEach((n, i) => {
    const old = prev[n.id];
    if (old) {
      n.x = old.x; n.y = old.y; known++;
    } else {
      const home = (n.goal_ids || []).map(id => placed[id]).find(Boolean);
      const jx = (Math.sin(i * 12.9898) * 43758.5453) % 1;
      const jy = (Math.sin(i * 78.233) * 12345.6789) % 1;
      n.x = (home ? home.x : cx) + (jx - 0.5) * 120;
      n.y = (home ? home.y : cy) + (jy - 0.5) * 120;
    }
    n.vx = 0; n.vy = 0;
    placed[n.id] = n;
  });
  GRAPH.nodes = g.nodes;
  GRAPH.edges = g.edges;
  GRAPH.byId = placed;
  GRAPH.warm = known === g.nodes.length;  // nothing new: a short settle is enough
}

function tickGraph() {
  const nodes = GRAPH.nodes, edges = GRAPH.edges;
  const cx = GRAPH.width / 2, cy = GRAPH.height / 2;
  const REP = 1400, DAMP = 0.84;
  // repulsion (O(n^2); fine for the dozens of nodes we have)
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j++) {
      const b = nodes[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let d2 = dx * dx + dy * dy;
      if (d2 < 1) { d2 = 1; dx = (i - j) || 1; }
      const dist = Math.sqrt(d2);
      const f = REP / d2;
      const ux = dx / dist, uy = dy / dist;
      a.vx += ux * f; a.vy += uy * f;
      b.vx -= ux * f; b.vy -= uy * f;
    }
  }
  // springs along edges
  for (const e of edges) {
    const a = GRAPH.byId[e.source], b = GRAPH.byId[e.target];
    if (!a || !b) continue;
    const isAlign = e.kind === "alignment";
    const target = isAlign ? 95 : 165;
    const k = isAlign ? 0.018 : 0.006 * (e.weight || 0.5);
    let dx = b.x - a.x, dy = b.y - a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const f = (dist - target) * k;
    const ux = dx / dist, uy = dy / dist;
    a.vx += ux * f; a.vy += uy * f;
    b.vx -= ux * f; b.vy -= uy * f;
  }
  // gravity + goal anchors + integrate; returns mean squared speed per node
  let energy = 0;
  for (const n of nodes) {
    if (n === GRAPH.dragging) { n.vx = 0; n.vy = 0; continue; }
    n.vx += (cx - n.x) * 0.0016;
    n.vy += (cy - n.y) * 0.0016;
    if (n.type === "goal" && n.ax != null) {
      n.vx += (n.ax - n.x) * 0.06;
      n.vy += (n.ay - n.y) * 0.06;
    }
    n.vx *= DAMP; n.vy *= DAMP;
    n.x += n.vx; n.y += n.vy;
    n.x = Math.max(20, Math.min(GRAPH.width - 20, n.x));
    n.y = Math.max(20, Math.min(GRAPH.height - 20, n.y));
    energy += n.vx * n.vx + n.vy * n.vy;
  }
  return nodes.length ? energy / nodes.length : 0;
}

function nodeRadius(n) {
  if (n.type === "goal") return 15;
  return 6 + (n.completed ? 2 : 0);
}

// Theme-aware canvas palette, read from the CSS tokens on <html> so the
// Constellation matches day / night / marauder. Cached between frames (it
// used to be re-read with getComputedStyle on every animation frame);
// applyTheme clears the cache so a theme switch repaints correctly.
function graphPalette() {
  if (GRAPH.pal) return GRAPH.pal;
  GRAPH.pal = readGraphPalette();
  return GRAPH.pal;
}

function readGraphPalette() {
  const cs = getComputedStyle(document.documentElement);
  const v = (name, fb) => (cs.getPropertyValue(name).trim() || fb);
  const houses = {};
  Object.keys(LANE_HOUSE).forEach(lane => { houses[lane] = v(`--house-${lane}`, ""); });
  return {
    houses,
    fallback: v("--ink-faded", "#6b5032"),
    align: v("--graph-align", "rgba(91,67,39,0.42)"),
    semanticRgb: v("--graph-semantic-rgb", "75, 46, 87"),
    label: v("--graph-label", "#2a1d10"),
    halo: v("--graph-halo", "rgba(243,232,204,0.94)"),
    ring: v("--graph-ring", "#715210"),
    stroke: v("--graph-stroke", "rgba(42,29,16,0.55)"),
    glow: parseFloat(v("--graph-glow", "0")) > 0,
    shadow: v("--graph-shadow", "rgba(40,18,4,0.35)"),
    displayFont: v("--font-display", "Georgia, serif"),
    bodyFont: v("--font-body", "Georgia, serif"),
  };
}

// House color for a node: the theme's House token for its lane, else the
// goal's stored color_primary from the API.
function graphNodeColor(n, pal) {
  return (n.lane && pal.houses[n.lane]) || n.color || pal.fallback;
}

function drawGraph() {
  const canvas = $("#graph-canvas");
  const ctx = canvas.getContext("2d");
  const pal = graphPalette();
  ctx.clearRect(0, 0, GRAPH.width, GRAPH.height);
  // edges
  for (const e of GRAPH.edges) {
    const a = GRAPH.byId[e.source], b = GRAPH.byId[e.target];
    if (!a || !b) continue;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    if (e.kind === "alignment") {
      ctx.setLineDash([]);
      ctx.strokeStyle = pal.align;
      ctx.lineWidth = 1.2;
    } else {
      const w = Math.max(0.4, (e.weight || 0.5));
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = `rgba(${pal.semanticRgb},${0.18 + w * 0.4})`;
      ctx.lineWidth = 0.6 + w;
    }
    ctx.stroke();
  }
  ctx.setLineDash([]);
  // nodes
  for (const n of GRAPH.nodes) {
    const r = nodeRadius(n);
    const color = graphNodeColor(n, pal);
    const isHover = n === GRAPH.hover;
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    // Night: House-colored glow (stars). Day / marauder: a soft ink shadow.
    ctx.shadowColor = pal.glow ? color : pal.shadow;
    ctx.shadowBlur = isHover ? 16 : (n.type === "goal" ? (pal.glow ? 14 : 6) : (pal.glow ? 7 : 3));
    ctx.shadowOffsetY = pal.glow ? 0 : 1;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;
    // Thin ink outline so pale House colors still read on parchment
    ctx.strokeStyle = pal.stroke;
    ctx.lineWidth = 0.8;
    ctx.stroke();
    if (n.type === "goal" || isHover) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 2.5, 0, Math.PI * 2);
      ctx.strokeStyle = pal.ring;
      ctx.lineWidth = n.type === "goal" ? 2 : 1.4;
      ctx.stroke();
    }
    // goal labels always; task labels on hover. A halo keeps text legible over edges.
    if (n.type === "goal" || isHover) {
      ctx.font = n.type === "goal" ? `700 13px ${pal.displayFont}` : `italic 13px ${pal.bodyFont}`;
      ctx.textAlign = "center";
      const label = n.label.length > 34 ? n.label.slice(0, 33) + "…" : n.label;
      const ty = n.y - r - 8;
      ctx.lineJoin = "round";
      ctx.lineWidth = 4;
      ctx.strokeStyle = pal.halo;
      ctx.strokeText(label, n.x, ty);
      ctx.fillStyle = pal.label;
      ctx.fillText(label, n.x, ty);
    }
  }
}

// One simulation step; true once the layout has been calm for a few frames.
function stepGraph() {
  const energy = tickGraph();
  GRAPH.calmFrames = energy < GRAPH_CALM_ENERGY ? GRAPH.calmFrames + 1 : 0;
  return GRAPH.calmFrames >= GRAPH_CALM_FRAMES;
}

function graphLoop() {
  const calm = stepGraph();
  drawGraph();
  GRAPH.ticksLeft--;
  if (GRAPH.dragging || (GRAPH.ticksLeft > 0 && !calm)) {
    GRAPH.raf = requestAnimationFrame(graphLoop);
  } else {
    GRAPH.raf = null;  // settled; stop burning frames until reheated
  }
}

function startGraph() {
  stopGraphAnim();
  GRAPH.ticksLeft = GRAPH.warm ? 150 : 600;
  GRAPH.calmFrames = 0;
  if (prefersReducedMotion()) {
    for (let i = 0; i < 400; i++) if (stepGraph()) break;
    drawGraph();
    return;
  }
  GRAPH.raf = requestAnimationFrame(graphLoop);
}

function reheatGraph(ticks = 180) {
  GRAPH.ticksLeft = Math.max(GRAPH.ticksLeft || 0, ticks);
  GRAPH.calmFrames = 0;
  if (!GRAPH.raf) GRAPH.raf = requestAnimationFrame(graphLoop);
}

function graphNodeAt(mx, my) {
  // topmost (last drawn) first
  for (let i = GRAPH.nodes.length - 1; i >= 0; i--) {
    const n = GRAPH.nodes[i];
    const r = nodeRadius(n) + 4;
    if ((mx - n.x) ** 2 + (my - n.y) ** 2 <= r * r) return n;
  }
  return null;
}

function graphMousePos(evt) {
  const canvas = $("#graph-canvas");
  const rect = canvas.getBoundingClientRect();
  return { x: evt.clientX - rect.left, y: evt.clientY - rect.top };
}

function renderGraphStats(stats) {
  const root = $("#graph-stats");
  if (!root) return;
  const col = stats.by_column || {};
  const tiles = [
    { label: "Tasks", value: stats.total_tasks || 0 },
    { label: "Completed", value: stats.completed || 0 },
    { label: "Goals", value: stats.goal_count || 0 },
    { label: "Unaligned", value: stats.unaligned || 0 },
    { label: "Semantic links", value: stats.semantic_edges || 0 },
    { label: "Memory", value: col.memory || 0 },
    { label: "Dive", value: col.dive || 0 },
    { label: "Review", value: col.review || 0 },
    { label: "Closed", value: col.closed || 0 },
  ];
  root.innerHTML = tiles.map(t =>
    `<div class="stat-tile"><div class="stat-value">${t.value}</div><div class="stat-label">${t.label}</div></div>`
  ).join("");
}

function openNodeModal(node) {
  if (!node || node.type !== "task") return;
  const m = STATE.memories.find(x =>
    x.id === `mem_${node.id}` || x.id === node.id || x.source_task_id === node.id);
  if (m) openModal(m);
}

function wireGraphInteraction() {
  const canvas = $("#graph-canvas");
  const tip = $("#graph-tooltip");
  if (!canvas) return;
  canvas.addEventListener("mousedown", e => {
    const p = graphMousePos(e);
    GRAPH.dragging = graphNodeAt(p.x, p.y);
    GRAPH.downAt = p; GRAPH.moved = false;
    if (GRAPH.dragging) reheatGraph();
  });
  window.addEventListener("mouseup", () => {
    if (GRAPH.dragging && !GRAPH.moved) openNodeModal(GRAPH.dragging);
    GRAPH.dragging = null;
  });
  canvas.addEventListener("mousemove", e => {
    const p = graphMousePos(e);
    if (GRAPH.dragging) {
      GRAPH.dragging.x = p.x; GRAPH.dragging.y = p.y;
      if (GRAPH.downAt && ((p.x - GRAPH.downAt.x) ** 2 + (p.y - GRAPH.downAt.y) ** 2) > 16) GRAPH.moved = true;
      return;
    }
    const n = graphNodeAt(p.x, p.y);
    const changed = n !== GRAPH.hover;
    GRAPH.hover = n;
    canvas.style.cursor = n ? "pointer" : "grab";
    if (changed && !GRAPH.raf) drawGraph();  // reflect hover when sim is settled
    if (n && tip) {
      tip.style.display = "block";
      tip.style.left = `${p.x + 14}px`;
      tip.style.top = `${p.y + 14}px`;
      const meta = n.type === "goal" ? `Connect goal, House ${houseName(n.lane)}` :
        `${n.column || ""}${n.completed ? " / done" : ""}`;
      tip.innerHTML = `<strong>${escapeHtml(n.label)}</strong><br><span style="color:var(--ink-faded);font-style:italic">${escapeHtml(meta)}</span>`;
    } else if (tip) {
      tip.style.display = "none";
    }
  });
  canvas.addEventListener("mouseleave", () => {
    if (tip) tip.style.display = "none";
    GRAPH.hover = null;
    if (!GRAPH.raf) drawGraph();
  });
  // Resize events fire in bursts; resize the canvas at most once per frame.
  let resizeQueued = false;
  window.addEventListener("resize", () => {
    if (resizeQueued || STATE.page !== "graph" || !GRAPH.nodes.length) return;
    resizeQueued = true;
    requestAnimationFrame(() => {
      resizeQueued = false;
      sizeGraphCanvas();
      reheatGraph(60);
    });
  });
}

// ----- Documents page (SOPs + tool docs) -----

const DOCS = { current: null, list: [] };

// Tiny, safe markdown renderer (escapes first, then applies a subset).
function renderMarkdown(md) {
  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const lines = (md || "").replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let inUl = false, inOl = false, inCode = false;
  const closeLists = () => {
    if (inUl) { html += "</ul>"; inUl = false; }
    if (inOl) { html += "</ol>"; inOl = false; }
  };
  const inline = s => esc(s)
    .replace(/`([^`]+)`/g, (m, c) => `<code>${c}</code>`)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  for (const raw of lines) {
    if (/^```/.test(raw)) {
      if (inCode) { html += "</code></pre>"; inCode = false; }
      else { closeLists(); html += "<pre><code>"; inCode = true; }
      continue;
    }
    if (inCode) { html += esc(raw) + "\n"; continue; }
    const h = raw.match(/^(#{1,3})\s+(.+)$/);
    if (h) { closeLists(); html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; continue; }
    const ul = raw.match(/^\s*[-*]\s+(.+)$/);
    if (ul) { if (!inUl) { closeLists(); html += "<ul>"; inUl = true; } html += `<li>${inline(ul[1])}</li>`; continue; }
    const ol = raw.match(/^\s*\d+\.\s+(.+)$/);
    if (ol) { if (!inOl) { closeLists(); html += "<ol>"; inOl = true; } html += `<li>${inline(ol[1])}</li>`; continue; }
    if (raw.trim() === "") { closeLists(); continue; }
    closeLists();
    html += `<p>${inline(raw)}</p>`;
  }
  if (inCode) html += "</code></pre>";
  closeLists();
  return html;
}

async function loadDocs() {
  const listEl = $("#docs-list");
  if (!STATE.apiConnected) await loadMemoriesFromApi();
  if (!STATE.apiConnected) {
    if (listEl) listEl.innerHTML = `<p class="docs-empty">Docs need the Pensieve API.</p>`;
    return;
  }
  try {
    const data = await fetchJson("/api/docs");
    DOCS.list = data.docs || [];
    renderDocsList();
    if (DOCS.list.length && !DOCS.current) openDoc(DOCS.list[0].id);
  } catch (e) {
    if (listEl) listEl.innerHTML = `<p class="docs-empty">Docs failed: ${escapeHtml(e.message)}</p>`;
  }
}

function renderDocsList() {
  const listEl = $("#docs-list");
  if (!listEl) return;
  if (!DOCS.list.length) {
    listEl.innerHTML = `<p class="docs-empty">No documents yet.</p>`;
    return;
  }
  listEl.innerHTML = DOCS.list.map(d =>
    `<button class="docs-list-item${DOCS.current === d.id ? " active" : ""}" data-id="${escapeHtml(d.id)}">${escapeHtml(d.title)}</button>`
  ).join("");
  listEl.querySelectorAll(".docs-list-item").forEach(btn => {
    btn.addEventListener("click", () => openDoc(btn.dataset.id));
  });
}

function setDocsMode(editing) {
  $("#docs-view").hidden = editing;
  $("#docs-editor").hidden = !editing;
  $("#docs-edit").hidden = editing || !DOCS.current;
  $("#docs-save").hidden = !editing;
  $("#docs-cancel").hidden = !editing;
  $("#docs-delete").hidden = editing || !DOCS.current;
}

async function openDoc(id) {
  // Clicking quickly through the list must show the last doc clicked, not
  // whichever response happens to arrive last.
  const signal = supersede("doc");
  try {
    const data = await fetchJson(`/api/docs/${encodeURIComponent(id)}`, { signal });
    DOCS.current = data.doc.id;
    $("#docs-current-title").textContent = data.doc.title;
    $("#docs-view").innerHTML = renderMarkdown(data.doc.content);
    $("#docs-editor").value = data.doc.content;
    setDocsMode(false);
    renderDocsList();
  } catch (e) {
    if (!isAbortError(e)) toast(`Open failed: ${e.message}`);
  }
}

async function saveDoc() {
  if (!DOCS.current) return;
  const content = $("#docs-editor").value;
  try {
    const res = await fetch(`${API_BASE}/api/docs/${encodeURIComponent(DOCS.current)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    await loadDocs();
    await openDoc(DOCS.current);
    toast("Document saved");
  } catch (e) {
    toast(`Save failed: ${e.message}`);
  }
}

async function newDoc() {
  const title = prompt("New document title:");
  if (!title || !title.trim()) return;
  try {
    const res = await fetch(`${API_BASE}/api/docs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim() }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    DOCS.current = data.doc.id;
    await loadDocs();
    await openDoc(data.doc.id);
    setDocsMode(true);
    $("#docs-editor").focus();
  } catch (e) {
    toast(`Create failed: ${e.message}`);
  }
}

async function deleteDoc() {
  if (!DOCS.current) return;
  if (!confirm("Delete this document? This cannot be undone.")) return;
  const id = DOCS.current;
  try {
    const res = await fetch(`${API_BASE}/api/docs/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`API ${res.status}`);
    DOCS.current = null;
    $("#docs-current-title").textContent = "Select a document";
    $("#docs-view").innerHTML = "";
    setDocsMode(false);
    await loadDocs();
    toast("Document deleted");
  } catch (e) {
    toast(`Delete failed: ${e.message}`);
  }
}

// ----- Masthead popovers (Filter + overflow) + filter badge -----

function initHeaderPopovers() {
  const pops = [
    { btn: $("#filter-pop-btn"), panel: $("#filter-pop-panel"), wrap: $("#filter-pop-wrap") },
    { btn: $("#more-pop-btn"), panel: $("#more-pop-panel"), wrap: $("#more-pop-wrap") },
  ].filter(p => p.btn && p.panel && p.wrap);
  if (!pops.length) return;

  const close = p => { p.panel.hidden = true; p.btn.setAttribute("aria-expanded", "false"); };
  const open = p => {
    pops.forEach(o => { if (o !== p) close(o); });
    p.panel.hidden = false;
    p.btn.setAttribute("aria-expanded", "true");
  };
  const closeAll = () => pops.forEach(close);

  pops.forEach(p => {
    p.btn.addEventListener("click", e => {
      e.stopPropagation();
      p.panel.hidden ? open(p) : close(p);
    });
  });
  // Click outside any popover closes them; clicks inside a panel keep it open.
  document.addEventListener("click", e => {
    if (!pops.some(p => p.wrap.contains(e.target))) closeAll();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && pops.some(p => !p.panel.hidden)) {
      closeAll();
      (pops.find(p => p.btn) || {}).btn?.focus();
    }
  });
}

function updateFilterBadge() {
  const badge = $("#filter-active-badge");
  if (!badge) return;
  let n = 0;
  if (STATE.filter && STATE.filter.strand) n++;
  if (STATE.weeklyFilter) n++;
  badge.textContent = String(n);
  badge.hidden = n === 0;
}

// Card density: "comfortable" (default, clamped description) | "compact" (no description).
function initDensityToggle() {
  const KEY = "pensieve-density";
  const btn = $("#density-toggle");
  let mode = (() => { try { return localStorage.getItem(KEY) === "comfortable" ? "comfortable" : "compact"; } catch (e) { return "compact"; } })();
  const apply = m => {
    document.documentElement.setAttribute("data-density", m);
    if (btn) {
      const compact = m === "compact";
      btn.setAttribute("aria-pressed", String(compact));
      btn.textContent = compact ? "Density: Compact" : "Density: Comfortable";
    }
  };
  apply(mode);
  if (btn) {
    btn.addEventListener("click", () => {
      mode = mode === "compact" ? "comfortable" : "compact";
      try { localStorage.setItem(KEY, mode); } catch (e) { /* ignore */ }
      apply(mode);
    });
  }
}

document.addEventListener("DOMContentLoaded", init);
