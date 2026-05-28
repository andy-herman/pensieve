/* ============================================================
   The Pensieve - Phase 2 prototype JS (v2)
   - Two views: Lifecycle (5 columns) + Houses (Connect goals)
   - Connect goals editable via in-app modal (persisted in localStorage)
   - Themes: day / night (toggle) + marauder (easter egg)
   - Hedwig review counter, footprint trail on drag, snitch
   ============================================================ */

// ----- 1. Connect goals (canonical defaults; mirrors data/connect-goals.json) -----

const DEFAULT_GOALS = [
  {
    id: "goal-1-dora-deep-dive",
    number: 1,
    short_name: "DORA Deep Dive",
    name: "DORA Deep Dive Compliance",
    house: "gryffindor",
    glyph: "\u26A1",
    color_primary: "#7a2018",
    color_accent: "#c9a655",
    summary: "Lead CISO GRC role on DORA Core Team through deep dive examination. Deliver accurate JET responses, co-develop regulatory readiness playbook.",
  },
  {
    id: "goal-2-uk-ctp",
    number: 2,
    short_name: "UK CTP",
    name: "UK CTP Year 1 Complete + Year 2 Launch",
    house: "hufflepuff",
    glyph: "\u2698",
    color_primary: "#b08a26",
    color_accent: "#2a1d10",
    summary: "Deliver Year 1 obligations post-designation, submit Self-Assessment in 3-month window. Launch Year 2 roadmap (scenario testing, incident mgmt playbook).",
  },
  {
    id: "goal-3-nis2-foundation",
    number: 3,
    short_name: "NIS2",
    name: "NIS2 Readiness Foundation",
    house: "slytherin",
    glyph: "\u269C",
    color_primary: "#2e5a3a",
    color_accent: "#a8a8a8",
    summary: "Build NIS2 foundational posture during H1. Lead scoping + gap analysis, apply communication-first model day one, identify core team partners.",
  },
  {
    id: "goal-4-ai-transformation",
    number: 4,
    short_name: "AI Program + Argus",
    name: "AI Strategy, Innovation, and Transformation Program for CISO GRC",
    house: "ravenclaw",
    glyph: "\u269B",
    color_primary: "#2c4670",
    color_accent: "#c9a655",
    summary: "Operationalize AI transformation program. Scale Argus from MVP to wider-used regulatory compliance platform. Four capability areas, biweekly triage, quarterly pilots.",
  },
];

// ----- 2. Lifecycle columns + strands -----

const LIFECYCLE_COLUMNS = [
  { id: "memory", title: "Memory", subtitle: "Captured, awaiting depth" },
  { id: "dive", title: "Dive", subtitle: "Surfaced for active work" },
  { id: "reverie", title: "Reverie", subtitle: "Focus block scheduled" },
  { id: "reflection", title: "Reflection", subtitle: "Closed, debriefing" },
  { id: "vial", title: "Vial", subtitle: "Stored for review-time evidence" },
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
    title: "1:1 prep with Mike",
    suggested_strand: "1on1-prep",
    needs_human_strand_review: false,
    why: "Standing 1:1 with Mike, need to cover this week's program risks and decisions that need his air cover.",
    impact: "Keeps Mike informed on weekly program state and ensures escalations are surfaced before they become blockers.",
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
    column: "reverie",
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
    why: "Standard monthly Azure spend for the Argus production VM. Goes to Steph for cost-center confirmation if over $400.",
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
    why: "Pulling from session notes, decisions log, and Living Our Culture callouts to stack-rank the strongest contributions since October 2025 for promo case and Connect refresh.",
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
    why: "Hunter from CELA hit a render crash on the Argus regulator detail page for BaFin. Page should fall back to short_name instead of crashing.",
    impact: "Restores a working regulator persona experience in Argus and removes a visible bug that would undermine confidence in demos.",
    strand_kind: "deep",
    confidence_strand: 0.97, confidence_impact: 0.84,
    connect_goal_ids: ["goal-4-ai-transformation"],
    connect_alignment_confidence: 0.96,
    connect_alignment_note: "Direct Argus product work, clearly advances Goal #4.",
    column: "reflection",
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
    title: "Review Sara's H2 growth plan draft",
    suggested_strand: "1on1-prep",
    needs_human_strand_review: false,
    why: "Sara sent her self-authored growth plan covering 3 stretch goals plus a cross-team rotation interest. Need feedback before Friday's 1:1.",
    impact: "Gives Sara clear development feedback and makes the 1:1 concrete rather than reactive.",
    strand_kind: "tactical",
    confidence_strand: 0.96, confidence_impact: 0.84,
    connect_goal_ids: [],
    connect_alignment_confidence: 0.94,
    connect_alignment_note: "Direct-report management with no specific Connect goal alignment.",
    column: "memory",
  },
  // Two extras to populate Reflection + Vial columns
  {
    id: "mem_seed_11",
    title: "Friday update to Steph: AI program status",
    suggested_strand: "leadership-update",
    needs_human_strand_review: false,
    why: "Weekly Friday update to Steph timed for her Monday sync with Molly and Oliver. Covers AI program governance progress, Argus pilot demos, and Pensieve internal use.",
    impact: "Maintains the structured leadership visibility cadence Steph asked for, and ensures the AI program shows up in Molly+Oliver's view of CISO GRC.",
    strand_kind: "writing",
    confidence_strand: 0.97, confidence_impact: 0.86,
    connect_goal_ids: ["goal-4-ai-transformation", "goal-2-uk-ctp"],
    connect_alignment_confidence: 0.88,
    connect_alignment_note: "Cross-program leadership update; weights to Goal #4 (program theme this week) and Goal #2 (UK CTP cadence anchor).",
    column: "reflection",
  },
  {
    id: "mem_seed_12",
    title: "UK CTP Domain 9 self-assessment write-up: shipped",
    suggested_strand: "uk-ctp-domain",
    needs_human_strand_review: false,
    why: "Closed the final UK CTP Year 1 self-assessment domain (Domain 9) with sign-off from CELA and the domain SME. All 9 of 9 domains now in submission-ready state.",
    impact: "Completes the Year 1 Self-Assessment evidence base ahead of designation, making the 3-month post-designation submission window comfortable rather than tight.",
    strand_kind: "writing",
    confidence_strand: 0.98, confidence_impact: 0.94,
    connect_goal_ids: ["goal-2-uk-ctp"],
    connect_alignment_confidence: 0.99,
    connect_alignment_note: "Direct Year 1 deliverable for Goal #2.",
    column: "vial",
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
  memories: SEED_MEMORIES.map(m => ({ ...m })),
  view: "lifecycle",      // "lifecycle" | "houses"
  theme: loadTheme(),     // "day" | "night" | "marauder"
  filter: { strand: null, search: "" },
  semanticResultIds: null, // null = no semantic filter; Set<string> = restrict to these ids
  semanticQuery: "",
  apiConnected: false,
  apiSourceLabel: "seed",
  easterBuffer: "",
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
  const saved = localStorage.getItem("pensieve-theme");
  if (saved === "night" || saved === "day" || saved === "marauder") return saved;
  return "day";
}

function saveTheme() {
  localStorage.setItem("pensieve-theme", STATE.theme);
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
  if (STATE.filter.strand && m.suggested_strand !== STATE.filter.strand) return false;
  if (STATE.filter.search) {
    const hay = `${m.title} ${m.why} ${m.impact}`.toLowerCase();
    if (!hay.includes(STATE.filter.search.toLowerCase())) return false;
  }
  return true;
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
      STATE.apiSourceLabel = "API connected (0 memories — run `pensieve sync`)";
    }
    // Try to load Connect goals from the API too; fall back to localStorage defaults.
    try {
      const goalsResp = await fetchJson("/api/goals");
      if (Array.isArray(goalsResp.goals) && goalsResp.goals.length > 0) {
        STATE.goals = goalsResp.goals.map(g => ({ ...g }));
      }
    } catch (e) { /* keep local */ }
    return true;
  } catch (e) {
    STATE.apiConnected = false;
    STATE.apiSourceLabel = "offline (seed data)";
    console.warn(`Pensieve API not reachable at ${API_BASE}: ${e.message}. Using seed data.`);
    return false;
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
      toast(`Pulled from Microsoft To-Do — ${parts.join(", ") || "complete"}`);
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
  if (!STATE.apiConnected) return;
  try {
    // memoryId in dashboard is "mem_<source_id>"; API expects bare source id.
    const apiId = memoryId.replace(/^mem_/, "");
    await fetch(`${API_BASE}/api/memories/${encodeURIComponent(apiId)}/column`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ column }),
    });
  } catch (e) {
    toast(`Could not save column change: ${e.message}`);
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
  document.documentElement.setAttribute("data-theme", STATE.theme);
  const label = $("#theme-label");
  if (label) label.textContent = `${STATE.theme} mode`;
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
}

function renderBoard() {
  const board = $("#board");
  board.innerHTML = "";

  if (STATE.view === "lifecycle") {
    LIFECYCLE_COLUMNS.forEach(col => board.appendChild(renderLifecycleColumn(col)));
  } else {
    STATE.goals.forEach(g => board.appendChild(renderHouseColumn(g)));
    board.appendChild(renderUnhousedColumn());
  }

  updateMemoryCount();
  updateHedwig();
  attachDragHandlers();
}

function renderLifecycleColumn(col) {
  const wrap = document.createElement("section");
  wrap.className = "column";
  wrap.dataset.column = col.id;
  wrap.dataset.view = "lifecycle";

  const memos = STATE.memories.filter(m => m.column === col.id && memoryMatchesFilter(m));

  wrap.innerHTML = `
    <div class="column-header">
      <h2 class="column-title">${col.title}</h2>
      <p class="column-subtitle">${col.subtitle}</p>
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

function renderHouseColumn(goal) {
  const wrap = document.createElement("section");
  wrap.className = "column";
  wrap.dataset.column = goal.id;
  wrap.dataset.house = goal.house;
  wrap.dataset.view = "houses";

  const memos = STATE.memories.filter(m =>
    Array.isArray(m.connect_goal_ids) &&
    m.connect_goal_ids.includes(goal.id) &&
    memoryMatchesFilter(m)
  );

  wrap.innerHTML = `
    <div class="column-header">
      <h2 class="column-title">#${goal.number} ${goal.short_name}</h2>
      <p class="column-subtitle">${goal.house}</p>
      <span class="column-count">${memos.length} aligned</span>
    </div>
    <div class="column-cards"></div>
  `;

  const cards = $(".column-cards", wrap);
  if (memos.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-column";
    empty.textContent = "No memories yet for this House.";
    cards.appendChild(empty);
  } else {
    memos.forEach((m, idx) => cards.appendChild(renderCard(m, idx)));
  }
  return wrap;
}

function renderUnhousedColumn() {
  const wrap = document.createElement("section");
  wrap.className = "column";
  wrap.dataset.column = "unhoused";
  wrap.dataset.house = "unhoused";
  wrap.dataset.view = "houses";

  const memos = STATE.memories.filter(m =>
    (!Array.isArray(m.connect_goal_ids) || m.connect_goal_ids.length === 0) &&
    memoryMatchesFilter(m)
  );

  wrap.innerHTML = `
    <div class="column-header">
      <h2 class="column-title">Unhoused</h2>
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

function renderCard(m, idx) {
  const el = document.createElement("article");
  el.className = "card";
  el.draggable = true;
  el.dataset.memoryId = m.id;
  el.style.setProperty("--ink-delay", `${idx * 60}ms`);

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
    return `<span class="goal-chip" data-house="${g.house}" title="${g.name}"><span class="goal-chip-glyph">${g.glyph}</span>#${g.number} ${g.short_name}</span>`;
  }).join("");

  el.innerHTML = `
    ${review ? `<div class="wax-seal" title="Needs review">R</div>` : ""}
    <h3 class="card-title">${escapeHtml(m.title)}</h3>
    <div class="card-meta">
      <span class="card-strand" data-kind="${strandKind || ""}">${escapeHtml(strandDisplay(m.suggested_strand))}</span>
    </div>
    <p class="card-why">${escapeHtml(m.why)}</p>
    ${goalsHtml ? `<div class="card-goals">${goalsHtml}</div>` : ""}
  `;

  el.addEventListener("click", e => {
    if (el.classList.contains("dragging")) return;
    openModal(m);
  });
  return el;
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

function updateHedwig() {
  const reviewing = STATE.memories.filter(isReviewNeeded).length;
  const text = $("#hedwig-count");
  const label = $("#hedwig-label");
  const block = $(".hedwig-block");
  if (text) text.textContent = reviewing;
  if (block) block.classList.toggle("has-review", reviewing > 0);
  if (label) label.textContent = reviewing === 0 ? "All clear" : `${reviewing} need review`;
}

// ----- 7. Modal -----

const LIFECYCLE_OPTIONS = [
  { id: "memory", label: "Memory" },
  { id: "dive", label: "Dive" },
  { id: "reverie", label: "Reverie" },
  { id: "reflection", label: "Reflection" },
  { id: "vial", label: "Vial" },
];

function openModal(m) {
  const body = $("#modal-body");
  const review = isReviewNeeded(m);

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
      <label class="goal-check" data-house="${g.house}">
        <input type="checkbox" data-goal-id="${escapeHtml(g.id)}" ${checked ? "checked" : ""} />
        <span class="goal-chip" data-house="${g.house}" title="${escapeHtml(g.name)}">
          <span class="goal-chip-glyph">${g.glyph}</span>#${g.number} ${escapeHtml(g.short_name)}
        </span>
      </label>`;
  }).join("");

  body.innerHTML = `
    <input id="edit-title" class="modal-title-edit" value="${escapeHtml(m.title)}" />

    <div class="modal-meta">
      <label class="inline-label">Strand
        <select id="edit-strand" class="inline-select">${strandOptions}</select>
      </label>
      <label class="inline-label">Column
        <select id="edit-column" class="inline-select">${colOptions}</select>
      </label>
      <label class="inline-label review-toggle">
        <input type="checkbox" id="edit-review" ${m.needs_human_strand_review ? "checked" : ""} />
        Flag for review
      </label>
      ${review ? `<span class="review-pill">Needs review</span>` : ""}
    </div>

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
        <button id="edit-cancel" class="ghost-button" type="button">Cancel</button>
        <button id="edit-save" class="primary-button" type="button" data-memory-id="${escapeHtml(m.id)}">Save</button>
      </span>
    </div>
  `;
  $("#card-modal").hidden = false;

  $("#edit-save").addEventListener("click", () => saveMemoryEdit(m.id));
  $("#edit-cancel").addEventListener("click", closeModal);
}

function readEditedFields() {
  const selectedGoalIds = $$("#modal-body .goal-check input[type=checkbox]")
    .filter(cb => cb.checked)
    .map(cb => cb.dataset.goalId);
  return {
    title: $("#edit-title").value.trim(),
    suggested_strand: $("#edit-strand").value || null,
    column: $("#edit-column").value,
    needs_human_strand_review: $("#edit-review").checked,
    why: $("#edit-why").value,
    impact: $("#edit-impact").value,
    connect_goal_ids: selectedGoalIds,
    connect_alignment_note: $("#edit-align-note").value,
    notes_for_user: $("#edit-notes-user").value,
  };
}

async function saveMemoryEdit(memoryId) {
  const patch = readEditedFields();
  if (!patch.title) {
    toast("Title cannot be empty");
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
    toast("Saved");
  } catch (e) {
    toast(`Save failed: ${e.message}`);
  }
}

function closeModal() { $("#card-modal").hidden = true; }

// ----- 8. Goals editor -----

function openGoalsEditor() {
  const root = $("#goals-editor");
  root.innerHTML = "";
  STATE.goals.forEach((g, idx) => {
    const card = document.createElement("div");
    card.className = "goal-card";
    card.style.setProperty("--goal-color", g.color_primary);
    card.innerHTML = `
      <div class="goal-card-header">
        <span class="goal-house-pill" data-house="${g.house}" style="--goal-color:${g.color_primary}">${g.house}</span>
        <strong style="font-family:var(--font-display);font-size:13px">Goal #${g.number}</strong>
      </div>
      <label class="goal-input-label">Short name</label>
      <input class="goal-input" data-field="short_name" data-idx="${idx}" value="${escapeHtml(g.short_name)}" />
      <label class="goal-input-label">Full name</label>
      <input class="goal-input" data-field="name" data-idx="${idx}" value="${escapeHtml(g.name)}" />
      <label class="goal-input-label">Summary</label>
      <textarea class="goal-textarea" data-field="summary" data-idx="${idx}">${escapeHtml(g.summary)}</textarea>
    `;
    root.appendChild(card);
  });
  $("#goals-modal").hidden = false;
}

function saveGoalsFromEditor() {
  $$(".goal-input, .goal-textarea", $("#goals-editor")).forEach(input => {
    const idx = parseInt(input.dataset.idx, 10);
    const field = input.dataset.field;
    if (STATE.goals[idx]) STATE.goals[idx][field] = input.value.trim();
  });
  saveGoals();
  $("#goals-modal").hidden = true;
  renderStrandFilter();
  renderBoard();
  toast("Goals saved");
}

function resetGoals() {
  STATE.goals = DEFAULT_GOALS.map(g => ({ ...g }));
  saveGoals();
  openGoalsEditor();
  toast("Goals reset to vault defaults");
}

// ----- 9. Drag + drop + footprints -----

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
        if (targetGoalId === "unhoused") {
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

// Footprint trail (mousemove during drag; only stamps every N moves to avoid spam)
let footprintTick = 0;
document.addEventListener("dragover", e => {
  if (!DRAG.id) return;
  if (++footprintTick % 5 !== 0) return;
  const layer = $("#footprint-layer");
  if (!layer) return;
  const fp = document.createElement("div");
  fp.className = "footprint";
  fp.style.left = `${e.clientX}px`;
  fp.style.top = `${e.clientY}px`;
  fp.style.setProperty("--rot", `${Math.floor(Math.random() * 60 - 30)}deg`);
  layer.appendChild(fp);
  setTimeout(() => fp.remove(), 1700);
});

// ----- 10. Easter egg ----- 

const SWEAR = "i solemnly swear that i am up to no good";
const MANAGED = "mischief managed";

document.addEventListener("keydown", e => {
  if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
  if (e.key.length !== 1) {
    if (e.key === "Backspace") STATE.easterBuffer = STATE.easterBuffer.slice(0, -1);
    return;
  }
  STATE.easterBuffer = (STATE.easterBuffer + e.key.toLowerCase()).slice(-60);
  if (STATE.easterBuffer.endsWith(SWEAR)) {
    STATE.theme = "marauder";
    saveTheme();
    applyTheme();
    toast("I solemnly swear I am up to no good");
    STATE.easterBuffer = "";
  } else if (STATE.easterBuffer.endsWith(MANAGED)) {
    STATE.theme = STATE.theme === "marauder" ? "day" : STATE.theme;
    saveTheme();
    applyTheme();
    toast("Mischief managed");
    STATE.easterBuffer = "";
  }
});

// ----- 11. Toast -----

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

  // Load from API (falls back to seed data on failure), then re-render
  loadMemoriesFromApi().then(ok => {
    renderStrandFilter();
    renderBoard();
    const footerSource = $("#api-source-label");
    if (footerSource) footerSource.textContent = STATE.apiSourceLabel;
    if (!ok) {
      toast(`API offline — using seed data. Start with: pensieve serve`);
    }
  });

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

  // Clear filters
  $("#clear-filters").addEventListener("click", () => {
    STATE.filter = { strand: null, search: "" };
    STATE.semanticResultIds = null;
    STATE.semanticQuery = "";
    $("#search").value = "";
    renderStrandFilter();
    renderBoard();
  });

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

  // Theme toggle (day <-> night; marauder is easter-egg only)
  $("#theme-toggle").addEventListener("click", () => {
    if (STATE.theme === "marauder") {
      STATE.theme = "day";
    } else {
      STATE.theme = STATE.theme === "day" ? "night" : "day";
    }
    saveTheme();
    applyTheme();
    toast(`${STATE.theme} mode`);
  });

  // Goals editor
  $("#open-goals").addEventListener("click", openGoalsEditor);
  $("#goals-save").addEventListener("click", saveGoalsFromEditor);
  $("#goals-reset").addEventListener("click", resetGoals);

  // Modal close
  $("#card-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "1") closeModal();
  });
  $("#goals-modal").addEventListener("click", e => {
    if (e.target.dataset.close === "goals") $("#goals-modal").hidden = true;
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      closeModal();
      $("#goals-modal").hidden = true;
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
