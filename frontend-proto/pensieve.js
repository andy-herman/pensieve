/* ============================================================
   Pensieve HUD theme JS (v3)
   - Two views: Lifecycle (4 columns: Memory / Dive / Review / Closed) + Lanes (Connect goals)
   - Connect goals editable via in-app modal (persisted in localStorage)
   - Single HUD theme. No theme toggle. No easter eggs.
   - Drag-and-drop kanban, semantic search, PDF goals import.
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
  memories: SEED_MEMORIES.map(m => ({ ...m })),
  view: "lifecycle",      // "lifecycle" | "lanes"
  page: "board",          // "board" | "recap" | "graph"
  weeklyFilter: (() => { try { return localStorage.getItem("pensieve-weekly") === "1"; } catch (e) { return false; } })(),
  theme: "hud",           // single theme; legacy state field kept for compatibility
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

function loadTheme() {
  return "hud";
}

function saveTheme() {
  // No-op. HUD is the only theme.
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

async function loadMemoriesFromApi() {
  try {
    const health = await fetchJson("/api/healthz");
    STATE.apiConnected = true;
    const data = await fetchJson("/api/memories");
    if (Array.isArray(data.memories) && data.memories.length > 0) {
      STATE.memories = data.memories.map(m => ({ ...m, column: m.column || "memory" }));
      STATE.apiSourceLabel = `${health.default_source || "live"} (${data.count} memories)`;
    } else {
      STATE.memories = [];
      STATE.apiSourceLabel = "API connected (0 memories, run `pensieve sync`)";
    }
    // Try to load Connect goals from the API too; fall back to localStorage defaults.
    try {
      const goalsResp = await fetchJson("/api/goals");
      if (Array.isArray(goalsResp.goals) && goalsResp.goals.length > 0) {
        STATE.goals = goalsResp.goals.map(g => ({ ...g }));
      }
      if (goalsResp && goalsResp._meta) {
        STATE.goalsMeta = goalsResp._meta;
      }
    } catch (e) { /* keep local */ }
    // Garden v1: refresh the board-health pill alongside the memories so
    // Garden v1: refresh the board-health pill alongside the memories so
    // the score reflects the same snapshot the user is looking at.
    await loadBoardHealth();
    // Garden v2: refresh today's quest panel + completion state.
    await loadQuests();
    // Garden v3: re-evaluate achievements; surfaces confetti on new unlocks.
    await loadAchievements();
    return true;
  } catch (e) {
    STATE.apiConnected = false;
    STATE.apiSourceLabel = "offline (seed data)";
    console.warn(`Pensieve API not reachable at ${API_BASE}: ${e.message}. Using seed data.`);
    return false;
  }
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
      // and is not already complete — completed quests just show status).
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
    const safeName = _escape(def.name);
    const safeDesc = _escape(def.description || "");
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

function _escape(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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
  const colors = ["#7cffff", "#ffe07c", "#7cff9d", "#ff8da1", "#c9a0ff"];
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
//   - a PATCH from the dashboard is in flight (patchInFlight > 0)
//   - the document is hidden (Page Visibility API) — saves API calls when the tab is in the background
// `pollInFlight` prevents stacked refreshes if the network call takes longer than the interval.
const AUTO_REFRESH_MS = 30000;
let pollInFlight = false;
window.__pensievePatchInFlight = 0;

function _isModalOpen(id) {
  const el = document.getElementById(id);
  return !!(el && !el.hidden);
}

async function refreshMemoriesIfSafe() {
  if (document.hidden) return;
  if (pollInFlight) return;
  if (window.__pensievePatchInFlight > 0) return;
  if (typeof DRAG !== "undefined" && DRAG && DRAG.id) return;
  if (
    _isModalOpen("card-modal") ||
    _isModalOpen("goals-modal") ||
    _isModalOpen("vial-modal") ||
    _isModalOpen("achievements-modal")
  ) return;
  pollInFlight = true;
  try {
    const ok = await loadMemoriesFromApi();
    if (ok) {
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
    btn.innerHTML = "&#x2728; Working...";
  }
  try {
    const apiId = memoryId.replace(/^mem_/, "");
    const res = await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiId)}/regenerate`, {
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
    const idx = STATE.memories.findIndex(x => x.id === memoryId);
    if (idx >= 0) STATE.memories[idx] = { ...STATE.memories[idx], ...fresh };
    renderStrandFilter();
    renderBoard();
    // Garden v1+v2+v3: regenerate is a tend — refresh pill, quests, and achievements.
    loadBoardHealth();
    loadQuests();
    loadAchievements();
    // Re-open the modal with the regenerated memory so the user sees the new text live.
    const refreshed = STATE.memories[idx] || fresh;
    openModal(refreshed);
    toast(`Regenerated (+${body.tokens_used || 0} tokens)`);
  } catch (e) {
    toast(`Regenerate failed: ${e.message}`);
    if (btn) {
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

async function persistColumnChange(memoryId, column) {
  // Always attempt the PATCH. Gating this on `apiConnected` caused silent data
  // loss when the dashboard first loaded against a down server (apiConnected
  // stuck on false), the user later dragged cards, and then Pull-from-To-Do
  // succeeded and triggered loadMemoriesFromApi which overwrote the un-saved
  // local drags with Chroma's columns.
  window.__pensievePatchInFlight++;
  try {
    // memoryId in dashboard is "mem_<source_id>"; API expects bare source id.
    const apiId = memoryId.replace(/^mem_/, "");
    const res = await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiId)}/column`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ column }),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status}: ${text.slice(0, 120)}`);
    }
    // Surface the completion-mirror outcome so the user knows whether the
    // close also propagated to Microsoft To-Do (only fires when dragging to
    // 'closed' AND PENSIEVE_MIRROR_COMPLETION=true).
    try {
      const payload = await res.json();
      const cm = payload && payload.completion_mirror;
      if (cm && cm.reason === "ok") {
        toast("Marked complete in To-Do");
      } else if (cm && cm.reason && cm.reason.startsWith("sink-error")) {
        toast(`Closed locally but To-Do writeback failed: ${cm.reason}`);
      } else if (cm && cm.reason === "task-not-found-at-source") {
        toast("Closed locally - upstream task not found in To-Do");
      }
      // Garden v1: the API returns the enriched memory so we can update
      // freshness in place (the dot must refresh, not just the score pill).
      if (payload && payload.memory) {
        const idx = STATE.memories.findIndex(x => x.id === payload.memory.id);
        if (idx >= 0) {
          STATE.memories[idx] = { ...STATE.memories[idx], ...payload.memory };
        }
      }
    } catch (_) { /* response body parsing is best-effort */ }
    // Garden v1+v2+v3: refresh pill, quest panel, achievements so they all
    // reflect this tend (and a potential confetti burst on new unlocks).
    loadBoardHealth().then(() => renderBoard());
    loadQuests();
    loadAchievements();
    // If we got here, the API is up. Flip the flag so the next render of UI
    // affordances that gate on apiConnected (e.g. semantic search) starts
    // working without forcing a page reload.
    if (!STATE.apiConnected) {
      STATE.apiConnected = true;
      const footerSource = $("#api-source-label");
      if (footerSource && STATE.apiSourceLabel === "offline (seed data)") {
        STATE.apiSourceLabel = "live (reconnected)";
        footerSource.textContent = STATE.apiSourceLabel;
      }
    }
  } catch (e) {
    // Loud toast so the user knows the drag did NOT persist and the next
    // Pull-from-To-Do or Refresh will revert this card.
    toast(`Move not saved (${e.message}) - card will revert on next refresh`);
  } finally {
    window.__pensievePatchInFlight = Math.max(0, window.__pensievePatchInFlight - 1);
  }
}

async function runSemanticSearch(q) {
  if (!q || !q.trim()) {
    STATE.semanticResultIds = null;
    STATE.semanticQuery = "";
    renderBoard();
    return;
  }
  if (!STATE.apiConnected) {
    toast("Semantic search needs the API server (run `pensieve serve`)");
    return;
  }
  try {
    const data = await fetchJson(`/api/search?q=${encodeURIComponent(q)}&top_k=20`);
    STATE.semanticResultIds = new Set((data.memories || []).map(m => m.id));
    STATE.semanticQuery = q;
    if (STATE.semanticResultIds.size === 0) {
      toast(`No semantic matches for "${q}"`);
    }
    renderBoard();
  } catch (e) {
    toast(`Search failed: ${e.message}`);
  }
}

// ----- 6. Rendering -----

function applyTheme() {
  document.documentElement.setAttribute("data-theme", "hud");
  const label = $("#theme-label");
  if (label) label.textContent = "hud theme";
}

function applyView() {
  document.documentElement.setAttribute("data-view", STATE.view);
  $$(".view-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.view === STATE.view));
  renderBoard();
}

function renderStrandFilter() {
  const root = $("#strand-filter");
  root.innerHTML = "";
  const usedStrandIds = new Set();
  STATE.memories.forEach(m => { if (m.suggested_strand) usedStrandIds.add(m.suggested_strand); });
  STRANDS.filter(s => usedStrandIds.has(s.id)).forEach(s => {
    const btn = document.createElement("button");
    btn.className = "strand-pill";
    btn.dataset.strand = s.id;
    btn.textContent = s.display_name;
    if (STATE.filter.strand === s.id) btn.classList.add("active");
    btn.addEventListener("click", () => {
      STATE.filter.strand = STATE.filter.strand === s.id ? null : s.id;
      renderStrandFilter();
      renderBoard();
    });
    root.appendChild(btn);
  });
  updateFilterBadge();
}

function renderBoard() {
  const board = $("#board");
  board.innerHTML = "";

  if (STATE.view === "lifecycle") {
    LIFECYCLE_COLUMNS.forEach(col => board.appendChild(renderLifecycleColumn(col)));
  } else {
    STATE.goals.forEach(g => board.appendChild(renderLaneColumn(g)));
    board.appendChild(renderUnassignedColumn());
    board.appendChild(renderAddLaneTile());
  }

  updateMemoryCount();
  updateReviewIndicator();
  attachDragHandlers();
}

function renderLifecycleColumn(col) {
  const wrap = document.createElement("section");
  wrap.className = "column";
  wrap.dataset.column = col.id;
  wrap.dataset.view = "lifecycle";

  const inColumn = STATE.memories.filter(m => m.column === col.id && memoryMatchesFilter(m));
  const memos = inColumn.filter(m => passesWeeklyFilter(m, col.id));
  const hidden = inColumn.length - memos.length;
  const subtitle = (hidden > 0)
    ? `${col.subtitle} &middot; ${hidden} earlier hidden`
    : col.subtitle;

  wrap.innerHTML = `
    <div class="column-header">
      <h2 class="column-title">${col.title}</h2>
      <p class="column-subtitle">${subtitle}</p>
      <span class="column-count">${memos.length} ${memos.length === 1 ? "memory" : "memories"}</span>
    </div>
    <div class="column-cards"></div>
  `;

  const cards = $(".column-cards", wrap);
  if (memos.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-column";
    empty.textContent = "The surface is still.";
    cards.appendChild(empty);
  } else {
    memos.forEach((m, idx) => cards.appendChild(renderCard(m, idx)));
  }
  return wrap;
}

function renderLaneColumn(goal) {
  const wrap = document.createElement("section");
  wrap.className = "column";
  wrap.dataset.column = goal.id;
  wrap.dataset.lane = goal.lane;
  wrap.dataset.view = "lanes";

  const memos = STATE.memories.filter(m =>
    Array.isArray(m.connect_goal_ids) &&
    m.connect_goal_ids.includes(goal.id) &&
    memoryMatchesFilter(m)
  );

  wrap.innerHTML = `
    <div class="column-header">
      <h2 class="column-title">#${goal.number} ${goal.short_name}</h2>
      <span class="column-count">${memos.length} aligned</span>
    </div>
    <div class="column-cards"></div>
  `;

  const cards = $(".column-cards", wrap);
  if (memos.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-column";
    empty.textContent = "No memories yet for this lane.";
    cards.appendChild(empty);
  } else {
    memos.forEach((m, idx) => cards.appendChild(renderCard(m, idx)));
  }
  return wrap;
}

function renderUnassignedColumn() {
  const wrap = document.createElement("section");
  wrap.className = "column";
  wrap.dataset.column = "unassigned";
  wrap.dataset.lane = "unassigned";
  wrap.dataset.view = "lanes";

  const memos = STATE.memories.filter(m =>
    (!Array.isArray(m.connect_goal_ids) || m.connect_goal_ids.length === 0) &&
    memoryMatchesFilter(m)
  );

  wrap.innerHTML = `
    <div class="column-header">
      <h2 class="column-title">Unassigned</h2>
      <p class="column-subtitle">Work not yet tied to a Connect goal</p>
      <span class="column-count">${memos.length} drifting</span>
    </div>
    <div class="column-cards"></div>
  `;

  const cards = $(".column-cards", wrap);
  if (memos.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-column";
    empty.textContent = "Everything aligns. Rare and excellent.";
    cards.appendChild(empty);
  } else {
    memos.forEach((m, idx) => cards.appendChild(renderCard(m, idx)));
  }
  return wrap;
}

// A lightweight "+ Add lane" tile shown at the end of the Lanes view. Opens
// the goals editor (which adds/edits/deletes lanes), so unclear work can get
// its own lane when a Connect goal doesn't fit.
function renderAddLaneTile() {
  const wrap = document.createElement("section");
  wrap.className = "column add-lane-tile";
  wrap.dataset.view = "lanes";
  wrap.innerHTML = `
    <button class="add-lane-btn" title="Add or edit your lanes">
      <span class="add-lane-plus">+</span>
      <span>Add lane</span>
      <span class="add-lane-hint">Edit lanes too</span>
    </button>
  `;
  wrap.querySelector(".add-lane-btn").addEventListener("click", openGoalsEditor);
  return wrap;
}

function renderCard(m, idx) {
  const el = document.createElement("article");
  el.className = "card";
  el.draggable = true;
  el.dataset.memoryId = m.id;
  el.style.setProperty("--ink-delay", `${idx * 60}ms`);

  // Garden v1: per-card freshness dot via [data-freshness] CSS hook.
  // Only set when truthy so generic selectors aren't accidentally matched.
  if (m.freshness) {
    el.dataset.freshness = m.freshness;
  }
  if (m.is_overdue) {
    el.classList.add("is-overdue");
  }

  // Primary goal color for the left rail
  const primaryGoal = (m.connect_goal_ids && m.connect_goal_ids.length > 0) ? getGoal(m.connect_goal_ids[0]) : null;
  if (primaryGoal) {
    el.dataset.goalColor = "1";
    el.style.setProperty("--goal-color", primaryGoal.color_primary);
  }

  const strand = getStrand(m.suggested_strand);
  const strandKind = m.strand_kind || (strand ? strand.kind : "");

  const review = isReviewNeeded(m);

  const goalsHtml = (m.connect_goal_ids || []).map(gid => {
    const g = getGoal(gid);
    if (!g) return "";
    return `<span class="goal-chip" data-lane="${g.lane}" title="${g.name}">#${g.number} ${g.short_name}</span>`;
  }).join("");

  const due = formatDueDate(m.due_date);
  const dueHtml = due
    ? `<span class="card-due" data-urgency="${due.urgency}" title="Due ${escapeHtml(m.due_date)}">DUE ${escapeHtml(due.text)}</span>`
    : "";

  const fullTitle = m.display_title || m.title || "";
  el.innerHTML = `
    <h3 class="card-title" title="${escapeHtml(fullTitle)}">${escapeHtml(fullTitle)}</h3>
    ${review ? `<div class="card-status" title="Flagged for review">&gt; STATUS // REVIEW</div>` : ""}
    <div class="card-meta">
      <span class="card-strand" data-kind="${strandKind || ""}">${escapeHtml(strandDisplay(m.suggested_strand))}</span>
      ${dueHtml}
    </div>
    <p class="card-why">${escapeHtml(m.why)}</p>
    ${goalsHtml ? `<div class="card-goals">${goalsHtml}</div>` : ""}
    ${renderVialAffordance(m)}
  `;

  el.addEventListener("click", e => {
    if (el.classList.contains("dragging")) return;
    // Chevron / badge clicks handle themselves — don't open the card modal
    if (e.target.closest(".card-vial-chevron, .card-vial-badge")) return;
    openModal(m);
  });
  return el;
}

function renderVialAffordance(m) {
  if (m.pending_closure_capture) {
    return `<button class="card-vial-chevron" type="button" data-memory-id="${escapeHtml(m.id)}" title="Capture what changed when this closed">&#x1F4DC; CAPTURE</button>`;
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
  const visible = STATE.memories.filter(memoryMatchesFilter).length;
  const total = STATE.memories.length;
  $("#memory-count").textContent = visible === total ? `${total} memories` : `${visible} of ${total} memories`;
}

function updateReviewIndicator() {
  const reviewing = STATE.memories.filter(isReviewNeeded).length;
  const text = $("#review-count");
  const block = $(".review-block");
  if (text) {
    text.textContent = reviewing === 0 ? "CLEAR" : String(reviewing).padStart(2, "0");
  }
  if (block) {
    block.classList.toggle("has-review", reviewing > 0);
    block.classList.toggle("filter-active", !!STATE.filter.reviewOnly);
    block.style.cursor = reviewing > 0 || STATE.filter.reviewOnly ? "pointer" : "default";
  }
}

// Click handler for the masthead REVIEW indicator: toggles a board-wide
// "show only review-flagged cards" filter. Bound once during init().
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

function openModal(m) {
  const body = $("#modal-body");
  const review = isReviewNeeded(m);
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
      <label class="goal-check" data-lane="${g.lane}">
        <input type="checkbox" data-goal-id="${escapeHtml(g.id)}" ${checked ? "checked" : ""} />
        <span class="goal-chip" data-lane="${g.lane}" title="${escapeHtml(g.name)}">
          #${g.number} ${escapeHtml(g.short_name)}
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
    ${review ? `<div class="review-status-line"><span class="review-status-rule"></span><span class="review-status-label">REVIEW FLAG ACTIVE</span><span class="review-status-rule"></span></div>` : ""}

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
    window.__pensievePatchInFlight++;
    const apiId = memoryId.replace(/^mem_/, "");
    const res = await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    const data = await res.json();
    // Re-sync local state from the server-authoritative copy
    if (data.memory && mem) {
      Object.assign(mem, data.memory, { id: data.memory.id });
    }
    renderStrandFilter();
    renderBoard();
    // Garden v1+v2+v3: editing tends the card — refresh pill, quests, achievements.
    loadBoardHealth();
    loadQuests();
    loadAchievements();
    toast("Saved");
  } catch (e) {
    toast(`Save failed: ${e.message}`);
  } finally {
    window.__pensievePatchInFlight = Math.max(0, window.__pensievePatchInFlight - 1);
  }
}

function closeModal() { $("#card-modal").hidden = true; }

// ----- 7b. Vial modal (closure capture) -----

const VIAL = { memoryId: null };

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
  const apiId = memoryId.replace(/^mem_/, "");
  window.__pensievePatchInFlight = (window.__pensievePatchInFlight || 0) + 1;
  try {
    const res = await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiId)}/vials`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ captured_text: kind === "captured" ? text : "", capture_kind: kind }),
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`${res.status}: ${detail}`);
    }
    closeVialModal();
    toast(kind === "skipped" ? "Closure skipped" : "Vial saved");
    await loadMemoriesFromApi();
    renderBoard();
  } catch (e) {
    toast(`Vial save failed: ${e.message}`);
  } finally {
    window.__pensievePatchInFlight = Math.max(0, window.__pensievePatchInFlight - 1);
  }
}

// ----- 8. Goals editor -----

function openGoalsEditor() {
  const root = $("#goals-editor");
  root.innerHTML = "";
  STATE.goals.forEach((g, idx) => {
    const card = document.createElement("div");
    card.className = "goal-card";
    card.style.setProperty("--goal-color", g.color_primary);
    card.innerHTML = `
      <button class="goal-delete" data-idx="${idx}" title="Remove this goal" aria-label="Remove goal">&times;</button>
      <div class="goal-card-header">
        <span class="goal-lane-pill" data-lane="${g.lane}" style="--goal-color:${g.color_primary}">${escapeHtml(g.lane || "lane")}</span>
        <strong style="font-family:var(--font-display);font-size:13px">Goal #${g.number || idx + 1}</strong>
      </div>
      <label class="goal-input-label">Short name</label>
      <input class="goal-input" data-field="short_name" data-idx="${idx}" value="${escapeHtml(g.short_name || "")}" />
      <label class="goal-input-label">Full name</label>
      <input class="goal-input" data-field="name" data-idx="${idx}" value="${escapeHtml(g.name || "")}" />
      <label class="goal-input-label">Summary</label>
      <textarea class="goal-textarea" data-field="summary" data-idx="${idx}">${escapeHtml(g.summary || "")}</textarea>
    `;
    root.appendChild(card);
  });
  // Wire delete buttons (delegated would also work, but inline keeps things local).
  $$(".goal-delete", root).forEach(btn => {
    btn.addEventListener("click", e => {
      e.preventDefault();
      const idx = parseInt(btn.dataset.idx, 10);
      deleteGoalAt(idx);
    });
  });
  $("#goals-modal").hidden = false;
}

function collectEditorIntoState() {
  $$(".goal-input, .goal-textarea", $("#goals-editor")).forEach(input => {
    const idx = parseInt(input.dataset.idx, 10);
    const field = input.dataset.field;
    if (STATE.goals[idx]) STATE.goals[idx][field] = input.value.trim();
  });
}

async function saveGoalsFromEditor() {
  collectEditorIntoState();
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

  $("#goals-modal").hidden = true;
  renderStrandFilter();
  renderBoard();
}

function resetGoals() {
  STATE.goals = DEFAULT_GOALS.map(g => ({ ...g }));
  saveGoals();
  openGoalsEditor();
  toast("Goals reset to defaults");
}

function addGoalToState() {
  const number = (STATE.goals.length || 0) + 1;
  const palette = LANE_PALETTE[(number - 1) % LANE_PALETTE.length];
  const stamp = Date.now().toString(36);
  STATE.goals.push({
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
  openGoalsEditor();
}

function deleteGoalAt(idx) {
  collectEditorIntoState();
  if (idx < 0 || idx >= STATE.goals.length) return;
  STATE.goals.splice(idx, 1);
  // Re-number so the editor + saved JSON stay in order. Lane assignments
  // are left as-is so existing memories aligned to a goal id keep their color.
  STATE.goals.forEach((g, i) => { g.number = i + 1; });
  openGoalsEditor();
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
    STATE.goals = goals.map(g => ({ ...g }));
    STATE.goalsMeta = proposal._meta || {};
    openGoalsEditor();
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

let DRAG = { id: null, fromCol: null };

function attachDragHandlers() {
  $$(".card").forEach(card => {
    card.addEventListener("dragstart", e => {
      DRAG.id = card.dataset.memoryId;
      DRAG.fromCol = card.closest(".column")?.dataset.column;
      card.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", DRAG.id); } catch (_) { /* ignore */ }
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
      DRAG = { id: null, fromCol: null };
      $$(".column.drop-target").forEach(c => c.classList.remove("drop-target"));
    });
  });

  $$(".column").forEach(col => {
    col.addEventListener("dragover", e => {
      e.preventDefault();
      col.classList.add("drop-target");
    });
    col.addEventListener("dragleave", e => {
      if (!col.contains(e.relatedTarget)) col.classList.remove("drop-target");
    });
    col.addEventListener("drop", e => {
      e.preventDefault();
      col.classList.remove("drop-target");
      const memId = DRAG.id || e.dataTransfer.getData("text/plain");
      if (!memId) return;
      const m = STATE.memories.find(x => x.id === memId);
      if (!m) return;

      if (STATE.view === "lifecycle") {
        m.column = col.dataset.column;
        persistColumnChange(m.id, m.column);
      } else {
        const targetGoalId = col.dataset.column;
        if (targetGoalId === "unassigned") {
          m.connect_goal_ids = [];
        } else {
          if (!Array.isArray(m.connect_goal_ids)) m.connect_goal_ids = [];
          if (!m.connect_goal_ids.includes(targetGoalId)) {
            m.connect_goal_ids = [targetGoalId, ...m.connect_goal_ids.filter(id => id !== targetGoalId)];
          }
        }
      }
      renderBoard();
    });
  });
}

// ----- 10. Toast -----

let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  if (!t) return;
  t.textContent = msg;
  t.hidden = false;
  requestAnimationFrame(() => t.classList.add("show"));
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => { t.hidden = true; }, 350);
  }, 2200);
}

// ----- 12. Wire up -----

function init() {
  applyTheme();
  renderStrandFilter();
  applyView();
  applyWeeklyFilterState();
  initHeaderPopovers();
  initDensityToggle();
  updateFilterBadge();

  // Load from API (falls back to seed data on failure), then re-render
  loadMemoriesFromApi().then(ok => {
    renderStrandFilter();
    renderBoard();
    const footerSource = $("#api-source-label");
    if (footerSource) footerSource.textContent = STATE.apiSourceLabel;
    if (!ok) {
      toast(`API offline, using seed data. Start with: pensieve serve`);
    }
  });

  // Begin the auto-refresh loop (see refreshMemoriesIfSafe for guards).
  startAutoRefreshLoop();

  // Text filter (fast in-memory match)
  $("#search").addEventListener("input", e => {
    STATE.filter.search = e.target.value;
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
    STATE.semanticResultIds = null;
    STATE.semanticQuery = "";
    $("#search").value = "";
    renderStrandFilter();
    renderBoardHealth();
    renderQuestPanel();
    renderBoard();
  });

  // Click the masthead REVIEW indicator to filter board to review-flagged cards.
  const reviewBlock = document.querySelector(".review-block");
  if (reviewBlock) reviewBlock.addEventListener("click", toggleReviewOnlyFilter);

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
      const footerSource = $("#api-source-label");
      if (footerSource) footerSource.textContent = STATE.apiSourceLabel;
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
      pullTodoBtn.innerHTML = "Pulling from To-Do...";
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
        const footerSource = $("#api-source-label");
        if (footerSource) footerSource.textContent = STATE.apiSourceLabel;
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
      STATE.view = btn.dataset.view;
      applyView();
    });
  });

  // Theme toggle removed: HUD is the only theme.

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
    if (e.target.dataset.close === "goals") $("#goals-modal").hidden = true;
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
      $("#goals-modal").hidden = true;
      closeVialModal();
      closeAchievementsModal();
    }
  });
}

// ----- Recap page (Phase 3: Connect recap) -----

function switchPage(page) {
  const known = ["recap", "graph", "docs"];
  STATE.page = known.includes(page) ? page : "board";
  document.documentElement.setAttribute("data-page", STATE.page);
  $$(".page-tab").forEach(btn => {
    const on = btn.dataset.page === STATE.page;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
  if (STATE.page === "graph") loadGraph();
  else stopGraphAnim();
  if (STATE.page === "docs") loadDocs();
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
        <textarea class="recap-revise-input" rows="2" placeholder="e.g. 'The Touchstone task was about NIS2 testing for Rob, not a status report' - then Rewrite."></textarea>
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
};

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
  try {
    const data = await fetchJson(`/api/graph?threshold=${threshold}`);
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
  const placed = {};
  goals.forEach((n, i) => {
    const a = (i / Math.max(1, goals.length)) * Math.PI * 2 - Math.PI / 2;
    n.ax = cx + ringR * Math.cos(a);
    n.ay = cy + ringR * Math.sin(a);
    n.x = n.ax; n.y = n.ay; n.vx = 0; n.vy = 0;
    placed[n.id] = n;
  });
  // tasks: start near their first goal (or center), with jitter
  g.nodes.filter(n => n.type === "task").forEach((n, i) => {
    const home = (n.goal_ids || []).map(id => placed[id]).find(Boolean);
    const jx = (Math.sin(i * 12.9898) * 43758.5453) % 1;
    const jy = (Math.sin(i * 78.233) * 12345.6789) % 1;
    n.x = (home ? home.x : cx) + (jx - 0.5) * 120;
    n.y = (home ? home.y : cy) + (jy - 0.5) * 120;
    n.vx = 0; n.vy = 0;
    placed[n.id] = n;
  });
  GRAPH.nodes = g.nodes;
  GRAPH.edges = g.edges;
  GRAPH.byId = placed;
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
  // gravity + goal anchors + integrate
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
  }
}

function nodeRadius(n) {
  if (n.type === "goal") return 15;
  return 6 + (n.completed ? 2 : 0);
}

function drawGraph() {
  const canvas = $("#graph-canvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, GRAPH.width, GRAPH.height);
  // edges
  for (const e of GRAPH.edges) {
    const a = GRAPH.byId[e.source], b = GRAPH.byId[e.target];
    if (!a || !b) continue;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    if (e.kind === "alignment") {
      ctx.strokeStyle = "rgba(66,200,245,0.28)";
      ctx.lineWidth = 1.2;
    } else {
      const w = Math.max(0.4, (e.weight || 0.5));
      ctx.strokeStyle = `rgba(184,120,255,${0.12 + w * 0.35})`;
      ctx.lineWidth = 0.8 + w;
    }
    ctx.stroke();
  }
  // nodes
  for (const n of GRAPH.nodes) {
    const r = nodeRadius(n);
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = n.color || "#42c8f5";
    ctx.shadowColor = n.color || "#42c8f5";
    ctx.shadowBlur = n === GRAPH.hover ? 18 : (n.type === "goal" ? 12 : 6);
    ctx.fill();
    ctx.shadowBlur = 0;
    if (n.type === "goal" || n === GRAPH.hover) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(230,243,255,0.85)";
      ctx.lineWidth = 1.4;
      ctx.stroke();
    }
    // goal labels always; task labels on hover
    if (n.type === "goal" || n === GRAPH.hover) {
      ctx.font = n.type === "goal" ? "600 12px 'Rajdhani', sans-serif" : "500 11px 'Rajdhani', sans-serif";
      ctx.fillStyle = "#e6f3ff";
      ctx.textAlign = "center";
      const label = n.label.length > 34 ? n.label.slice(0, 33) + "…" : n.label;
      ctx.fillText(label, n.x, n.y - r - 6);
    }
  }
}

function graphLoop() {
  tickGraph();
  drawGraph();
  GRAPH.ticksLeft--;
  if (GRAPH.ticksLeft > 0 || GRAPH.dragging) {
    GRAPH.raf = requestAnimationFrame(graphLoop);
  } else {
    GRAPH.raf = null;  // settled; stop burning frames until reheated
  }
}

function startGraph() {
  stopGraphAnim();
  GRAPH.ticksLeft = 600;
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) {
    for (let i = 0; i < 400; i++) tickGraph();
    drawGraph();
    return;
  }
  GRAPH.raf = requestAnimationFrame(graphLoop);
}

function reheatGraph(ticks = 180) {
  GRAPH.ticksLeft = Math.max(GRAPH.ticksLeft || 0, ticks);
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
      const meta = n.type === "goal" ? "Connect goal" :
        `${n.column || ""}${n.completed ? " / done" : ""}`;
      tip.innerHTML = `<strong>${escapeHtml(n.label)}</strong><br><span style="color:var(--muted)">${escapeHtml(meta)}</span>`;
    } else if (tip) {
      tip.style.display = "none";
    }
  });
  canvas.addEventListener("mouseleave", () => {
    if (tip) tip.style.display = "none";
    GRAPH.hover = null;
    if (!GRAPH.raf) drawGraph();
  });
  window.addEventListener("resize", () => {
    if (STATE.page === "graph" && GRAPH.nodes.length) {
      sizeGraphCanvas();
      reheatGraph(60);
    }
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
  try {
    const data = await fetchJson(`/api/docs/${encodeURIComponent(id)}`);
    DOCS.current = data.doc.id;
    $("#docs-current-title").textContent = data.doc.title;
    $("#docs-view").innerHTML = renderMarkdown(data.doc.content);
    $("#docs-editor").value = data.doc.content;
    setDocsMode(false);
    renderDocsList();
  } catch (e) {
    toast(`Open failed: ${e.message}`);
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
  let mode = (() => { try { return localStorage.getItem(KEY) === "compact" ? "compact" : "comfortable"; } catch (e) { return "comfortable"; } })();
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
