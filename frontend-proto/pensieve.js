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
  { id: "memory", title: "Memory", subtitle: "Backlog, awaiting depth" },
  { id: "dive", title: "Dive", subtitle: "Active work" },
  { id: "review", title: "Review", subtitle: "Needs another look" },
  { id: "closed", title: "Closed", subtitle: "Done, complete in your source list" },
];

// Mirror of pensieve/enrichment/goals_importer.py HOUSE_PALETTE so the
// frontend can auto-assign a house when the user adds a goal manually.
const HOUSE_PALETTE = [
  { house: "gryffindor", house_glyph: "\u26a1", color_primary: "#7a2018", color_accent: "#c9a655" },
  { house: "hufflepuff", house_glyph: "\u2698", color_primary: "#b08a26", color_accent: "#2a1d10" },
  { house: "slytherin",  house_glyph: "\u269c", color_primary: "#2e5a3a", color_accent: "#a8a8a8" },
  { house: "ravenclaw",  house_glyph: "\u269b", color_primary: "#2c4670", color_accent: "#c9a655" },
  { house: "internal",   house_glyph: "\u2697", color_primary: "#5a5a5a", color_accent: "#c9a655" },
  { house: "muggleborn", house_glyph: "\u270e", color_primary: "#8a4b1f", color_accent: "#e0c690" },
  { house: "centaur",    house_glyph: "\u2618", color_primary: "#3c5e2c", color_accent: "#c9a655" },
  { house: "phoenix",    house_glyph: "\u2741", color_primary: "#a83a1f", color_accent: "#f5d77b" },
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
  view: "lifecycle",      // "lifecycle" | "houses"
  theme: "hud",           // single theme; legacy state field kept for compatibility
  filter: { strand: null, search: "" },
  semanticResultIds: null, // null = no semantic filter; Set<string> = restrict to these ids
  semanticQuery: "",
  apiConnected: false,
  apiSourceLabel: "seed",
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
    return true;
  } catch (e) {
    STATE.apiConnected = false;
    STATE.apiSourceLabel = "offline (seed data)";
    console.warn(`Pensieve API not reachable at ${API_BASE}: ${e.message}. Using seed data.`);
    return false;
  }
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
    <h3 class="card-title">${escapeHtml(m.title)}</h3>
    ${review ? `<div class="card-status" title="Flagged for review">&gt; STATUS // REVIEW</div>` : ""}
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
  const block = $(".hedwig-block");
  if (text) {
    text.textContent = reviewing === 0 ? "CLEAR" : String(reviewing).padStart(2, "0");
  }
  if (block) block.classList.toggle("has-review", reviewing > 0);
}

// ----- 7. Modal -----

const LIFECYCLE_OPTIONS = [
  { id: "memory", label: "Memory" },
  { id: "dive", label: "Dive" },
  { id: "review", label: "Review" },
  { id: "closed", label: "Closed" },
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
      <button class="goal-delete" data-idx="${idx}" title="Remove this goal" aria-label="Remove goal">&times;</button>
      <div class="goal-card-header">
        <span class="goal-house-pill" data-house="${g.house}" style="--goal-color:${g.color_primary}">${escapeHtml(g.house || "house")}</span>
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
  const palette = HOUSE_PALETTE[(number - 1) % HOUSE_PALETTE.length];
  const stamp = Date.now().toString(36);
  STATE.goals.push({
    id: `goal-${number}-new-${stamp}`,
    number,
    short_name: "",
    name: "",
    summary: "",
    house: palette.house,
    house_glyph: palette.house_glyph,
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
  // Re-number so the editor + saved JSON stay in order. House assignments
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
