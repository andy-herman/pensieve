# Pensieve Frontend Prototype

A static, HP-themed kanban dashboard for visualising enriched Pensieve memories. This is a **single-page prototype**, not the production frontend — it exists to lock the look-and-feel for Phase 2 before the React + Vite build starts.

## How to run

Just open `index.html` in any modern browser. There is no build step, no server, no install. The Google Fonts (`Cinzel`, `IM Fell English`, `IM Fell English SC`) are loaded from a CDN at runtime; the page still renders without them.

```powershell
# from Pensieve repo root
Start-Process "frontend-proto\index.html"
```

If you want clean URLs and the ability to fetch the real audit log later, you can serve it instead:

```powershell
# Python 3
python -m http.server 8080 -d frontend-proto
# Then open http://localhost:8080
```

## The five columns

| Glyph | Column | What it represents |
|---|---|---|
| 📜 | **Memory** | Freshly enriched from To-Do, not yet acted on |
| 🔥 | **Dive** | Actively being worked on (focus session in progress) |
| 🌙 | **Reverie** | Calendar block proposed or scheduled (Phase 2.5) |
| ✨ | **Reflection** | Done, awaiting post-Reverie debrief |
| 🧪 | **Vial** | Distilled into Synapse Promo Coach evidence (Phase 3) |

Drag any card across columns to move it. Click any card to open the detail view with full `why`, `impact_hypothesis`, confidence bars, and Reverie/Dive/Reflection/Vial actions.

## The data

`pensieve.js` ships with the 12 strands from `data/samples.json` plus the 10 enriched memories from the Phase 0 smoke test on 2026-05-28 (sourced from `data/audit-log.jsonl`) and 2 extra cards for visual fullness.

**To wire real data later:**

1. Replace the `MEMORIES` constant with `await fetch('/api/memories').then(r => r.json())` once the Pensieve backend exists.
2. Replace the `STRANDS` constant similarly.
3. POST status changes back to the API in the `drop` and modal-action handlers.

## Design language

- **Background**: aged parchment cream with subtle SVG noise + radial candle-glow and emerald/midnight tints
- **Headers**: Cinzel display serif with gold-glow text shadow
- **Body**: IM Fell English (and SC for tiny caps) - same family as the Hogwarts acceptance letter aesthetic
- **Cards**: parchment slips with a strand-coloured top border and candle-glow on hover
- **Snitch**: drifts in the lower-right corner as a tasteful idle animation
- **Wax-red badges** mark memories that need human review (low strand confidence or no strand fit)

The whole palette and typography live in CSS custom properties at the top of `pensieve.css` - change two values to re-theme the entire board.

## Status

| Item | Status |
|---|---|
| Single-page prototype with 5 Pensieve columns | ✅ landed 2026-05-28 |
| Drag-and-drop between columns | ✅ |
| Card detail modal with strand/why/impact/confidence | ✅ |
| Strand filter chips + text search | ✅ |
| Snitch idle animation | ✅ |
| Wire to live `/api/memories` | ⏳ Phase 1 backend |
| Reverie scheduling action surface | ⏳ Phase 2.5 |
| React + Vite migration | ⏳ Phase 2 |
| `data/audit-log.jsonl` -> `pensieve.js` regenerator script | ⏳ |
