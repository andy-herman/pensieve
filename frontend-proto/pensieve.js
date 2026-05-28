/* ============================================================
   The Pensieve - kanban prototype logic
   Data is hardcoded below to match the 10 enriched memories
   from the Phase 0 smoke test on 2026-05-28 (audit-log.jsonl).
   Replace with a fetch() to /api/memories once Phase 1 lands.
   ============================================================ */

const STRANDS = [
  { id: 'dora-rfi',            name: 'DORA RFI',            color: '#2e5a3a', kind: 'deep' },
  { id: 'nis2-mapping',        name: 'NIS2 Mapping',        color: '#3a6a4a', kind: 'deep' },
  { id: '1on1-prep',           name: '1on1 Prep',           color: '#b08a26', kind: 'tactical' },
  { id: 'pensieve-build',      name: 'Pensieve Build',      color: '#5a2a72', kind: 'deep' },
  { id: 'learning',            name: 'Learning',            color: '#2c4670', kind: 'learning' },
  { id: 'ops-chores',          name: 'Ops Chores',          color: '#6b5a48', kind: 'tactical' },
  { id: 'ic5-promo-evidence',  name: 'IC5 Promo Evidence',  color: '#a8862c', kind: 'writing' },
  { id: 'argus-build',         name: 'Argus Build',         color: '#3b6a8a', kind: 'deep' },
  { id: 'team-mgmt',           name: 'Team Mgmt',           color: '#a8541f', kind: 'tactical' },
  { id: 'inbox-copilot-build', name: 'Inbox Copilot Build', color: '#4a2d6f', kind: 'deep' },
  { id: 'synapse-build',       name: 'Synapse Build',       color: '#2c5a78', kind: 'deep' },
  { id: 'ciso-grc-strategy',   name: 'CISO GRC Strategy',   color: '#7a2018', kind: 'deep' },
];

const STRAND_BY_ID = Object.fromEntries(STRANDS.map(s => [s.id, s]));

const STATUSES = [
  { id: 'memory',     name: 'Memory',     subtitle: 'Freshly stirred from To-Do' },
  { id: 'dive',       name: 'Dive',       subtitle: 'In active focus' },
  { id: 'reverie',    name: 'Reverie',    subtitle: 'Calendar block proposed' },
  { id: 'reflection', name: 'Reflection', subtitle: 'Done; awaiting debrief' },
  { id: 'vial',       name: 'Vial',       subtitle: 'Distilled for the Promo Coach' },
];

const ICON = {
  memory:     '\u{1F4DC}',
  dive:       '\u{1F525}',
  reverie:    '\u{1F319}',
  reflection: '\u2728',
  vial:       '\u{1F9EA}',
};

const MEMORIES = [
  {
    id: 'todo_sample_01', status: 'dive',
    title: 'Draft DORA Article 6 risk taxonomy',
    list: 'Work', strand: 'dora-rfi',
    why: 'EU Reg lead needs a first cut of the DORA Article 6 risk taxonomy by Friday so it can inform the Tuesday regulator briefing.',
    impact: 'Unblocks the DORA RFI writeup and gives the EU Reg lead a usable draft ahead of the regulator briefing.',
    strand_confidence: 0.97, impact_confidence: 0.82, needs_review: false, notes: null,
  },
  {
    id: 'todo_sample_02', status: 'memory',
    title: 'Cross-walk NIS2 controls to DORA Article 6',
    list: 'Work', strand: 'nis2-mapping',
    why: 'Mike flagged separate treatment as risky, so this task is meant to reuse the UK CTP table and align NIS2 controls with DORA Article 6 consistently.',
    impact: 'Unblocks a reusable control mapping and reduces inconsistency risk between NIS2, DORA, and prior UK CTP work.',
    strand_confidence: 0.68, impact_confidence: 0.77, needs_review: false,
    notes: 'Could also fit dora-rfi given the recent DORA context, but the title centers on cross-walking NIS2 controls, so nis2-mapping seems slightly stronger.',
  },
  {
    id: 'todo_sample_03', status: 'memory',
    title: 'Prep 1:1 talking points for Mike',
    list: 'Work', strand: '1on1-prep',
    why: 'No explicit why captured; this task appears to be preparing discussion points for a scheduled 1:1 with Mike.',
    impact: 'Sets up a focused 1:1 with Mike and reduces the chance of missing key updates or decisions.',
    strand_confidence: 0.97, impact_confidence: 0.82, needs_review: false, notes: null,
  },
  {
    id: 'todo_sample_04', status: 'dive',
    title: 'Write Pensieve Phase 0 enrichment prompt',
    list: 'Pensieve', strand: 'pensieve-build',
    why: 'This prompt needs to be strong enough in Phase 0 that Pensieve enrichment output is trustworthy before being used on real user tasks.',
    impact: 'Sets up reliable task-to-memory enrichment quality before rollout to live Microsoft To-Do tasks.',
    strand_confidence: 0.98, impact_confidence: 0.88, needs_review: false, notes: null,
  },
  {
    id: 'todo_sample_05', status: 'reverie',
    title: 'Watch the Azure AI Foundry deep-dive video',
    list: 'Personal', strand: 'learning',
    why: 'Tim recommended a 45 minute Azure AI Foundry deep-dive so you can focus on the eval frameworks chapter and build relevant capability.',
    impact: 'Builds understanding of eval frameworks that can improve how you design and assess AI copilot work.',
    strand_confidence: 0.88, impact_confidence: 0.72, needs_review: false, notes: null,
  },
  {
    id: 'todo_sample_06', status: 'reflection',
    title: 'Approve Q2 vendor invoices in MyOrder',
    list: 'Work', strand: 'ops-chores',
    why: 'Four vendor invoices are waiting and need approval before the end of month deadline to keep routine operational billing on track.',
    impact: 'Closes out month-end invoice approvals and avoids delays in vendor payment processing.',
    strand_confidence: 0.98, impact_confidence: 0.92, needs_review: false, notes: null,
  },
  {
    id: 'todo_sample_07', status: 'dive',
    title: 'Write H1 self-reflection narrative draft',
    list: 'Promo', strand: 'ic5-promo-evidence',
    why: 'This draft is meant to frame H1 accomplishments around DORA RFI delivery, Argus shipping, and Inbox Copilot scope as evidence for an IC5-targeted self-reflection.',
    impact: 'Adds evidence for the H1 review narrative and strengthens the case for IC5 promotion readiness.',
    strand_confidence: 0.98, impact_confidence: 0.89, needs_review: false, notes: null,
  },
  {
    id: 'todo_sample_08', status: 'reflection',
    title: 'Argus: fix the empty-state crash in the timeline view',
    list: 'Argus', strand: 'argus-build',
    why: 'The timeline view crashes when opened with no events, and the stack trace in the Argus channel provides evidence needed to diagnose and fix the defect.',
    impact: 'Unblocks reliable use of the timeline view and reduces user-facing crashes in Argus for empty-state scenarios.',
    strand_confidence: 0.98, impact_confidence: 0.90, needs_review: false, notes: null,
  },
  {
    id: 'todo_sample_09', status: 'memory',
    title: 'Renew passport',
    list: 'Personal', strand: null,
    why: 'No explicit why captured; this task appears to be a routine reminder, possibly personal.',
    impact: 'Closes out a personal admin item; no work-context impact identified.',
    strand_confidence: 0.08, impact_confidence: 0.25, needs_review: true,
    notes: "Consider creating a 'personal-admin' strand if you want to keep these in Pensieve, or move this task out of the Tasks list.",
  },
  {
    id: 'todo_sample_10', status: 'memory',
    title: "Review Sara's growth plan draft",
    list: 'Work', strand: 'team-mgmt',
    why: "Sara sent her growth plan draft on Monday and wants concrete examples, especially around the technical-leadership pillar, so you can give specific developmental feedback.",
    impact: "Improves the quality of Sara's growth plan and gives her clearer guidance on technical-leadership expectations and examples.",
    strand_confidence: 0.90, impact_confidence: 0.82, needs_review: false, notes: null,
  },
  {
    id: 'extra_01', status: 'vial',
    title: 'Pensieve project: spun out of CISO GRC pillar 1',
    list: 'Promo', strand: 'ic5-promo-evidence',
    why: 'Phase 0 of Pensieve shipped end-to-end on 2026-05-28 with 10/10 trustworthy enrichments and a working dry-run harness.',
    impact: 'Demonstrates platform thinking and prompt-engineering rigor as IC5-level evidence for promo.',
    strand_confidence: 0.95, impact_confidence: 0.85, needs_review: false, notes: null,
  },
  {
    id: 'extra_02', status: 'reverie',
    title: 'Deep work block: Pensieve Phase 1 design',
    list: 'Pensieve', strand: 'pensieve-build',
    why: 'Phase 1 needs the Graph integration design (token caching, throttling, delta sync) thought through before code lands.',
    impact: 'Reduces rework risk in Phase 1 and locks the contract between the enrichment layer and the To-Do data layer.',
    strand_confidence: 0.92, impact_confidence: 0.80, needs_review: false, notes: null,
  },
];

/* ============================================================
   State + filters
   ============================================================ */

const state = {
  memories: MEMORIES.map(m => ({ ...m })),
  activeStrands: new Set(),
  search: '',
};

/* ============================================================
   Rendering
   ============================================================ */

function strandColor(strandId) {
  return STRAND_BY_ID[strandId]?.color || 'var(--ink-faint)';
}
function strandName(strandId) {
  return STRAND_BY_ID[strandId]?.name || 'Unstranded';
}

function confidenceDots(conf) {
  const lit = Math.round((conf || 0) * 5);
  let html = '<span class="confidence-dots" aria-label="Confidence ' + Math.round((conf||0)*100) + '%">';
  for (let i = 1; i <= 5; i++) {
    html += `<span class="dot-pip${i <= lit ? ' lit' : ''}"></span>`;
  }
  html += '</span>';
  return html;
}

function renderCard(m) {
  const stColor = strandColor(m.strand);
  const stName  = strandName(m.strand);
  const stClass = m.strand ? '' : 'unstranded';
  const review  = m.needs_review ? '<span class="review-badge">Review</span>' : '';
  const reviewCls = m.needs_review ? ' review-flag' : '';
  return `
    <article class="card${reviewCls}"
             draggable="true"
             data-id="${m.id}"
             style="--strand-color: ${stColor}">
      <div class="card-meta">
        <span class="strand-pill ${stClass}">${stName}</span>
        ${review}
      </div>
      <h3 class="card-title">${escapeHtml(m.title)}</h3>
      <p class="card-why">${escapeHtml(m.why)}</p>
      <div class="card-footer">
        <span class="card-list-label">${escapeHtml(m.list)}</span>
        ${confidenceDots(m.strand_confidence)}
      </div>
    </article>
  `;
}

function renderBoard() {
  const filtered = state.memories.filter(matchesFilter);
  const board = document.getElementById('board');
  board.innerHTML = STATUSES.map(s => {
    const cards = filtered.filter(m => m.status === s.id);
    return `
      <section class="column" data-status="${s.id}">
        <header class="column-header">
          <h2 class="column-title">
            <span class="column-glyph">${ICON[s.id]}</span>
            ${s.name}
            <span class="column-count">${cards.length}</span>
          </h2>
          <p class="column-subtitle">${s.subtitle}</p>
        </header>
        <div class="column-body" data-status="${s.id}">
          ${cards.map(renderCard).join('') || '<div style="opacity:0.5;font-style:italic;font-size:13px;padding:8px;text-align:center;">empty</div>'}
        </div>
      </section>
    `;
  }).join('');

  document.getElementById('memory-count').textContent =
    `${state.memories.length} memories \u00B7 ${state.memories.filter(m => m.needs_review).length} need review`;

  wireDragAndDrop();
  wireCardClicks();
}

function renderStrandFilter() {
  const wrap = document.getElementById('strand-filter');
  const present = new Set(state.memories.map(m => m.strand).filter(Boolean));
  wrap.innerHTML = STRANDS
    .filter(s => present.has(s.id))
    .map(s => `<button class="strand-chip${state.activeStrands.has(s.id) ? ' active' : ''}" data-strand="${s.id}" style="--strand-color:${s.color}">${s.name}</button>`)
    .join('');
  wrap.querySelectorAll('.strand-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const sid = chip.dataset.strand;
      if (state.activeStrands.has(sid)) state.activeStrands.delete(sid);
      else state.activeStrands.add(sid);
      renderStrandFilter();
      renderBoard();
    });
  });
}

function matchesFilter(m) {
  if (state.activeStrands.size > 0 && (!m.strand || !state.activeStrands.has(m.strand))) return false;
  if (state.search) {
    const q = state.search.toLowerCase();
    const hay = (m.title + ' ' + (m.why || '') + ' ' + (m.impact || '')).toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

/* ============================================================
   Drag and drop
   ============================================================ */

let dragId = null;

function wireDragAndDrop() {
  document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('dragstart', e => {
      dragId = card.dataset.id;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      document.querySelectorAll('.column-body.drop-active').forEach(b => b.classList.remove('drop-active'));
      dragId = null;
    });
  });
  document.querySelectorAll('.column-body').forEach(body => {
    body.addEventListener('dragover', e => {
      e.preventDefault();
      body.classList.add('drop-active');
      e.dataTransfer.dropEffect = 'move';
    });
    body.addEventListener('dragleave', () => body.classList.remove('drop-active'));
    body.addEventListener('drop', e => {
      e.preventDefault();
      body.classList.remove('drop-active');
      if (!dragId) return;
      const newStatus = body.dataset.status;
      const m = state.memories.find(x => x.id === dragId);
      if (m && m.status !== newStatus) {
        m.status = newStatus;
        renderBoard();
      }
    });
  });
}

/* ============================================================
   Card detail modal
   ============================================================ */

function wireCardClicks() {
  document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('click', e => {
      if (e.target.closest('button')) return;
      const m = state.memories.find(x => x.id === card.dataset.id);
      if (m) openModal(m);
    });
  });
}

function openModal(m) {
  const body = document.getElementById('modal-body');
  const stName = strandName(m.strand);
  const stColor = strandColor(m.strand);
  body.innerHTML = `
    <div style="border-top:6px solid ${stColor}; margin: -32px -36px 20px; padding-top: 0;"></div>
    <h2 id="modal-title" style="font-family:var(--font-display); font-size:24px; margin:0 0 6px; letter-spacing:0.04em;">${escapeHtml(m.title)}</h2>
    <div class="card-meta" style="margin-bottom:18px;">
      <span class="strand-pill ${m.strand ? '' : 'unstranded'}" style="--strand-color:${stColor}; background:${stColor};">${stName}</span>
      <span class="card-list-label" style="font-size:12px; color:var(--ink-faint);">${escapeHtml(m.list)} list</span>
      ${m.needs_review ? '<span class="review-badge">Needs Review</span>' : ''}
    </div>
    <div class="modal-section">
      <h3>Why this matters</h3>
      <p>${escapeHtml(m.why)}</p>
    </div>
    <div class="modal-section">
      <h3>Impact hypothesis</h3>
      <p>${escapeHtml(m.impact)}</p>
    </div>
    <div class="modal-section">
      <h3>Confidence</h3>
      <p style="font-size:13px; color:var(--ink-soft);">
        Strand <strong style="color:var(--ink);">${Math.round(m.strand_confidence*100)}%</strong> ${confidenceDots(m.strand_confidence)}
        <br/>
        Impact <strong style="color:var(--ink);">${Math.round(m.impact_confidence*100)}%</strong> ${confidenceDots(m.impact_confidence)}
      </p>
    </div>
    ${m.notes ? `<div class="modal-section"><h3>Note for you</h3><p class="note">${escapeHtml(m.notes)}</p></div>` : ''}
    <div class="modal-actions">
      <button data-action="dive">Start Dive</button>
      <button data-action="reverie">Schedule Reverie</button>
      <button data-action="reflection">Mark Reflection</button>
      <button data-action="vial">Save to Vial</button>
    </div>
  `;
  body.querySelectorAll('.modal-actions button').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.action;
      const memory = state.memories.find(x => x.id === m.id);
      if (memory) {
        memory.status = target;
        closeModal();
        renderBoard();
      }
    });
  });
  document.getElementById('card-modal').hidden = false;
}

function closeModal() { document.getElementById('card-modal').hidden = true; }

document.getElementById('card-modal').addEventListener('click', e => {
  if (e.target.dataset.close === '1') closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

/* ============================================================
   Search + clear filters
   ============================================================ */

document.getElementById('search').addEventListener('input', e => {
  state.search = e.target.value;
  renderBoard();
});
document.getElementById('clear-filters').addEventListener('click', () => {
  state.activeStrands.clear();
  state.search = '';
  document.getElementById('search').value = '';
  renderStrandFilter();
  renderBoard();
});

/* ============================================================
   Utilities
   ============================================================ */

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ============================================================
   Boot
   ============================================================ */

renderStrandFilter();
renderBoard();
