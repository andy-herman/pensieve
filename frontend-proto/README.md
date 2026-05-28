# Pensieve dashboard (frontend-proto)

A single static HTML page that renders Pensieve memories as a Harry Potter-themed kanban board.

No build step. No framework. No transpilation. Open `index.html` in a browser (or open `http://localhost:8765/` while the Pensieve API is running) and it works.

This folder is the entire frontend. Three files plus assets:

```
frontend-proto/
|-- index.html        Markup + masthead + modal scaffolding + Hedwig SVG
|-- pensieve.css      Themes, columns, House palettes, candle flicker, etc.
|-- pensieve.js       State, rendering, drag-drop, easter eggs, API client
|-- README.md         You are here
```

## What it shows

Memories laid out as kanban cards. Each card surfaces:

- The task title
- Strand assignment + Strand kind badge (deep, tactical, learning, writing)
- One-line `why` and `impact` (from the enrichment LLM)
- Confidence dots (strand + impact + Connect alignment)
- House colored band for each Connect Goal the memory is aligned to
- A "needs review" wax-seal badge when confidence is below threshold or the LLM explicitly flagged it

## Two views

**Lifecycle view** (default)

Four columns walking a memory through its life:

| Column | What goes here |
| ------ | -------------- |
| Memory | Captured, awaiting depth |
| Dive | Surfaced for active work this week |
| Review | Flagged for a second look — needs another pass before closing |
| Closed | Done. Tasks marked complete in To-Do auto-route here on the next sync (no LLM tokens spent). |

Drag a card from one column to another to move it. The change is persisted to the local ChromaDB via `PATCH /api/memories/{id}/column`.

**Houses view**

One column per Connect Goal, themed as a Hogwarts house, plus an "Unhoused" column for memories the LLM declined to align (operational chores, personal admin, etc.). Columns auto-fit, so any number of goals lays out cleanly (the dashboard ships with 4 canonical Houses plus 4 extended slots — Internal / Muggleborn / Centaur / Phoenix — and goals beyond eight cycle through the palette).

Drag a card into a House to mark that Memory as aligned to that goal. The change updates in-memory state immediately and (in a future iteration) will be persisted to Chroma.

## Three themes

| Theme | How to switch |
| ----- | -------------- |
| Day (parchment + ink) | Default; click the sun/moon icon to toggle |
| Night (candle-lit) | Click the sun/moon icon to toggle |
| Marauder | Type `i solemnly swear that i am up to no good` (anywhere on the page, outside an input). Revert with `mischief managed`. |

Theme preference is stored in `localStorage` and survives reloads.

## Search

The search input in the masthead supports two modes:

1. **Text filter** (default, as you type): filters the currently loaded memories by title, why, and impact substring match. Fast, local, no API call.
2. **Semantic search** (press Enter or click the magnifier): sends the query to `/api/search` which runs a ChromaDB vector similarity query. The board is restricted to the semantic top-K (default 20).

Click "Clear filters" to drop both the text filter and the semantic restriction.

## Goals editor

The **Set Goals** button opens a modal where you can:

- **Upload your Connect PDF** and click ✨ Parse with AI — the backend extracts each goal and deterministically assigns a House. Review the proposal in the editor, tweak as needed, click Save.
- **Hand-edit** any goal's short name, full name, or summary.
- **+ Add goal** for a blank goal you fill in by hand.
- **× delete** any goal you don't want.

Saves round-trip through `POST /api/goals` and persist to `data/connect-goals.json`. If the API server is unreachable, edits fall back to localStorage so you don't lose them.

## Hedwig

Top-right of the masthead, Hedwig carries a letter showing the count of memories currently in the review queue (low confidence or LLM-flagged). She flutters when the count is nonzero.

## Footprint trail

While dragging a card, faint footprints appear under your cursor and fade out after about 1.7 seconds. Pure cosmetics; no functional purpose.

## API client behavior

On load, the dashboard tries `GET /api/healthz` to discover whether a local Pensieve API is running. Behavior:

- **API reachable**: pulls memories from `/api/memories`, pulls goals from `/api/goals`, persists column changes via PATCH, supports semantic search via `/api/search`.
- **API unreachable**: falls back to the bundled `SEED_MEMORIES` array (10 demo memories from Phase 0), shows "offline (seed data)" in the footer, and disables semantic search with a toast message.

`API_BASE` is determined in this order:

1. `localStorage.pensieve-api-base` if set
2. `window.location.origin` if the page is served over HTTP(S) (this is the normal case when opened via `http://localhost:8765/`)
3. Default `http://127.0.0.1:8765` (this is the fallback when opened directly as `file://`)

## Easter eggs

- `i solemnly swear that i am up to no good` -> Marauder theme
- `mischief managed` -> revert to day theme (only undoes Marauder; leaves day/night alone if you were on night when you triggered it)
- A snitch occasionally flits across the bottom-right (CSS animation, just for vibes)

## Browser support

Tested in current Edge and Chrome on Windows. Uses standard ES2020 features and HTML drag-and-drop. No polyfills. Should work in any modern Chromium-based browser; Safari and Firefox are untested but expected to work.

## Refresh

The circular arrow button in the masthead re-fetches memories from the API. Use it after running `pensieve sync` in a separate terminal to pick up newly enriched tasks without reloading the page.

## When to edit which file

| You want to | Edit |
| ----------- | ---- |
| Change colors, fonts, theme palettes, House accents | `pensieve.css` |
| Add a column, change Lifecycle labels, tweak strand badges | `pensieve.js` (look for `LIFECYCLE_COLUMNS` and `STRANDS`) |
| Add a new toolbar button or footer element | `index.html` (markup) + `pensieve.js` (handler) |
| Change how a card renders | `pensieve.js` `renderCard` |
| Change how the dashboard talks to the API | `pensieve.js` section 5b ("API client + remote sync") |

## Constraints

The dashboard intentionally:

- Has no build step
- Has no framework dependency
- Loads zero JavaScript modules from any CDN
- Loads two webfonts from Google Fonts (Cinzel + IM Fell English); replace those with self-hosted fonts if you want a fully offline build
- Reads only from the local Pensieve API; it never directly talks to Microsoft, Azure, or any third party
- Never writes to your Outlook tasks
