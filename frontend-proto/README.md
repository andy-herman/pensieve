# Pensieve dashboard (frontend-proto)

A single static HTML page that renders Pensieve memories as a Harry Potter-themed kanban board.

No build step. No framework. No transpilation. Open `index.html` in a browser (or open `http://localhost:8765/` while the Pensieve API is running) and it works.

This folder is the entire frontend. Three files plus this README:

```
frontend-proto/
|-- index.html        Markup + masthead + Hedwig and Snitch SVGs + modal scaffolding
|-- pensieve.css      Theme tokens (day / night / marauder), House palette, candle flicker, etc.
|-- pensieve.js       State, rendering, drag-drop, easter eggs, API client, Recap, Constellation, Docs
|-- README.md         You are here
```

## What it shows

Memories laid out as kanban cards on parchment. Each card surfaces:

- The task title (AI-curated display title when available)
- Strand assignment, inked in its kind's color (deep, tactical, learning, writing)
- Due date, with an "Overdue" pill when it has passed
- One-line `why` (Comfortable density only; Compact hides it)
- A House glyph and name for each Connect Goal the memory is aligned to, plus a House-colored left rail
- A wax-seal "R" when confidence is below threshold or the LLM explicitly flagged it for review
- A freshness dot (Garden) and, on closed cards, a Vial capture prompt or captured-count badge

## Pages

The tabs under the masthead switch between four pages:

| Page | What it does |
| ---- | ------------ |
| Board | The kanban board (Lifecycle or Houses view) |
| Recap | Drafts a Connect "Reflect on the past" recap per goal, with history, per-section revise, copy, and DOCX export |
| Graph | The Constellation: goals and tasks as a force-directed graph, House-colored, with semantic links |
| Docs | In-app markdown SOPs and tool docs |

## Two board views

**Lifecycle view** (default)

Four columns walking a memory through its life:

| Column | What goes here |
| ------ | -------------- |
| Memory | Captured, awaiting depth |
| Dive | Surfaced for active work this week |
| Review | Flagged for a second look, needs another pass before closing |
| Closed | Done. Tasks marked complete in To-Do auto-route here on the next sync (no LLM tokens spent). |

Drag a card from one column to another to move it. The change is persisted to the local ChromaDB via `PATCH /api/memories/{id}/column`. Dropping a card back on its own column does nothing (no save, no writeback). While you drag, faint footprints trail behind the cursor.

**Houses view**

One column per Connect Goal, each wearing a Hogwarts House color, plus an "Unhoused" column for memories the LLM declined to align (operational chores, personal admin, etc.) and an "Add a House" tile that opens the goals editor. Columns auto-fit, so any number of goals lays out cleanly.

Drag a card onto a House to move it there: the target becomes its primary House, the House it was dragged from is dropped, and any other alignments stay. Dropping on Unhoused clears every alignment. The change is saved with `PATCH /api/memories/{id}` (`connect_goal_ids`). The "Add a House" tile is not a drop target.

Under the hood each goal carries a neutral `lane` slug (the API and `data-lane` attributes never change). The dashboard maps slugs to Houses for presentation only:

| Lane slug | House | Glyph |
| --------- | ----- | ----- |
| crimson | Gryffindor | lightning |
| gold | Hufflepuff | flower |
| emerald | Slytherin | fleur-de-lis |
| azure | Ravenclaw | atom |
| slate | Internal | alembic |
| ember | Muggleborn | quill |
| sage | Centaur | shamrock |
| rose | Phoenix | blossom |

Goals beyond eight cycle through the palette. House colors are theme tokens (`--house-crimson` and friends in `pensieve.css`), so each theme gets readable versions.

## Three themes

| Theme | How to switch |
| ----- | -------------- |
| Day (parchment + ink) | Default; click the sun/moon button at the top right |
| Night (candle-lit navy, starfield) | Click the sun/moon button |
| Marauder | Type `i solemnly swear that i am up to no good` (anywhere on the page, outside a text field). Revert with `mischief managed`, or click the sun/moon button. |

Theme preference is stored in `localStorage` (`pensieve-theme`) and applied before first paint, so a night or marauder page never flashes parchment on reload. Every color on the page, including the Constellation canvas and the achievement confetti, reads from the theme tokens.

## Masthead

- **Hedwig** (top right) carries a letter showing how many memories are in the review queue (low confidence or LLM-flagged). Her label reads "All clear" when the queue is empty; she bobs when there is work. Click her (or press Enter) to show only review-flagged cards.
- **Health** is the Garden board-health score. Hover for the breakdown, click to filter to stale, ghost, or overdue cards.
- **Trophy** opens the achievements grid.
- **Today's quests** appear under the controls when the Garden has quests for you; click a quest to filter the board to its cards.
- **Pull from To-Do** sends Hedwig to fetch new tasks from Microsoft To-Do (she is "flying" while the sync runs).
- **Filter** holds the strand pills, the "This week" Closed filter, and Clear filters. **More** holds Refresh, Set goals, and the Compact / Comfortable density toggle.

## Search

The search input in the masthead supports two modes:

1. **Text filter** (default, as you type): filters the currently loaded memories by title, why, and impact substring match. Fast, local, no API call.
2. **Semantic search** (press Enter or click the magnifier): sends the query to `/api/search` which runs a ChromaDB vector similarity query. The board is restricted to the semantic top-K (default 20).

Click "Clear filters" to drop both the text filter and the semantic restriction.

## Goals (Houses) editor

The **Set goals** item (More menu) or the **Add a House** tile opens a modal where you can:

- **Upload your Connect PDF** and click Parse with AI. The backend extracts each goal and deterministically assigns a lane (and so a House). Review the proposal in the editor, tweak as needed, click Save.
- **Hand-edit** any goal's short name, full name, or summary.
- **+ Add goal** for a blank goal you fill in by hand.
- **x delete** any goal you don't want.

Saves round-trip through `POST /api/goals` and persist to `data/connect-goals.json`. If the API server is unreachable, edits fall back to localStorage so you don't lose them.

## API client behavior

On load, the dashboard requests `/api/healthz`, `/api/memories`, and `/api/goals` in parallel. Until they answer, the board shows its empty column shells ("Stirring the memories..."), never sample cards. Behavior:

- **API reachable**: renders the live memories and goals, then loads the Garden (`/api/board/health`, `/api/quests`, `/api/achievements`) in parallel in the background. Persists column and House changes via PATCH and supports semantic search via `/api/search`.
- **API unreachable**: falls back to the bundled `SEED_MEMORIES` array (demo memories from Phase 0), shows "offline (seed data)" in the footer, and disables semantic search with a toast message.

Auto-refresh: every 30 seconds the dashboard re-reads `/api/memories` and `/api/goals` to pick up auto-sync results. The poll is skipped while a modal is open, a card is mid-drag, a save is in flight, the window is hidden, or another page (Recap, Graph, Docs) is showing; it runs right away when you come back. An unchanged snapshot does nothing at all. A changed one updates only the cards whose content changed (cards are keyed by memory id), so scroll position, keyboard focus, hover, and open menus survive. The Garden refetches when the board changed, or at least every 5 minutes. A refresh that started before you moved or edited a card is discarded rather than reverting your change.

`API_BASE` is determined in this order:

1. `localStorage.pensieve-api-base` if set
2. `window.location.origin` if the page is served over HTTP(S) (this is the normal case when opened via `http://localhost:8765/`)
3. Default `http://127.0.0.1:8765` (this is the fallback when opened directly as `file://`)

## Easter eggs

- `i solemnly swear that i am up to no good` -> Marauder theme (Hedwig hides and the map's "MM" takes her place)
- `mischief managed` -> back to day theme (only undoes Marauder; leaves day/night alone)
- The golden Snitch occasionally flits across the page (one 28-second pass, then a rest of 15 to 45 seconds; just for vibes; hidden in Marauder mode)

## Accessibility

- Text tokens are tuned for WCAG AA contrast on parchment, navy, and the Marauder's Map.
- Every interactive element gets a candle-gold keyboard focus ring.
- Cards are keyboard reachable: Tab to a card, then Enter or Space opens it. Closing the card modal returns focus to the card.
- `prefers-reduced-motion` turns off the candle flicker, ink-in, Snitch, footprints, the theme crossfade, and other animation.

## Performance notes

- The parchment background is a fixed, composited layer (`body::after`), not `background-attachment: fixed`, so scrolling never repaints it.
- Theme switches crossfade the whole page with the View Transitions API (Edge and Chrome), with CSS transitions paused for the swap so no surface is caught half-switched.
- Long-running decorative animations avoid main-thread work: the Snitch's wings and Hedwig's blink only animate while visible, the starfield twinkles only at night, and the Vial chevron pulses via opacity.
- The Constellation stops simulating once the layout is calm, keeps node positions when you return to the tab, and caches its theme palette.
- Search typing is coalesced (80ms), and semantic search, graph, and doc requests abort the previous one when superseded.

## Browser support

Tested in current Edge and Chrome on Windows. Uses standard ES2020 features, HTML drag-and-drop, and CSS `color-mix()` / `:has()`. No polyfills. Should work in any modern Chromium-based browser; Safari and Firefox are untested but expected to work.

## When to edit which file

| You want to | Edit |
| ----------- | ---- |
| Change colors, fonts, theme palettes, House accents | `pensieve.css` (section 1, tokens) |
| Rename a House or change its glyph | `pensieve.js` (`LANE_HOUSE`) |
| Add a column, change Lifecycle labels, tweak strand badges | `pensieve.js` (look for `LIFECYCLE_COLUMNS` and `STRANDS`) |
| Add a new toolbar button or footer element | `index.html` (markup) + `pensieve.js` (handler) |
| Change how a card renders | `pensieve.js` `cardParts` (markup) and `buildCard` (element) |
| Change how the dashboard talks to the API | `pensieve.js` section 5b ("API client + remote sync") |

## Constraints

The dashboard intentionally:

- Has no build step
- Has no framework dependency
- Loads zero JavaScript modules from any CDN
- Bundles its two typefaces (Cinzel + IM Fell English, SIL OFL 1.1) in `assets/fonts/` via `fonts.css`, so the dashboard works offline and contacts no font service. Until they load, size-adjusted local Georgia faces stand in, so the swap barely shifts the layout
- Reads only from the local Pensieve API; it never directly talks to Microsoft, Azure, or any third party
- Never writes to your Outlook tasks directly (any writeback goes through the backend's opt-in TaskSink)
