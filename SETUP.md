# Setting up Pensieve

> A practical, copy-paste guide for getting Pensieve running on your laptop in
> about ten minutes. If you only have Microsoft To-Do, Outlook for Windows, and
> a Microsoft AI Cortex hub, you can run this end-to-end.

---

## Who this is for

You're an IC who:

- captures most of your work in **Microsoft To-Do** (any number of lists)
- wants a kanban view of those tasks, enriched with *why* + *impact* + which
  of your Connect goals they advance
- wants all of this to run **locally on your laptop** (no shared backend, no
  Graph permissions to request, no IT ticket)
- has access to an Azure OpenAI deployment (see Prereqs)

If that's you, keep reading. If your tasks live in Planner or ADO, Pensieve
won't help you yet — but the source layer is pluggable, so file an issue.

---

## Prerequisites

| You need | Notes |
|---|---|
| **Windows 10/11** | Pensieve uses the Outlook COM API; macOS/Linux are not supported today. |
| **Microsoft Outlook (desktop)** | Must be installed and signed in. To-Do tasks sync into Outlook automatically — that's what Pensieve reads. |
| **Python 3.11 or 3.12** | `python --version` to check. Install from python.org if missing. |
| **Git** | For cloning the repo. |
| **An Azure OpenAI deployment** | Pensieve uses `DefaultAzureCredential` (keyless). At Microsoft, this means access to a Cortex hub like `https://agents-wus3-02.services.ai.azure.com/`. Your model deployment name (e.g. `gpt-5.4-2`) goes in the env file below. |
| **`az login`** (Microsoft devs) | Run once so `DefaultAzureCredential` can mint tokens. `az account show` should return your work identity. |

You do **not** need: admin rights, an Entra app registration, a shared
database, a Graph permission grant, or anything from IT.

---

## 5-minute install

```powershell
# 1. Clone
cd "$HOME\Coding Projects (Local)"   # or wherever you keep code
git clone https://github.com/andy-herman/pensieve.git
cd pensieve

# 2. Create a virtual env
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install Pensieve in editable mode (with dev extras for pytest)
pip install -e ".[dev]"

# 4. Copy the env template
copy .env.example .env
notepad .env
```

In `.env`, set at minimum:

```
AZURE_OPENAI_ENDPOINT=https://your-cortex-hub.services.ai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.4-2
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_TOKEN_SCOPE=https://cognitiveservices.azure.com/.default
```

Save and close. **Do not commit your `.env`** — it's already in `.gitignore`.

```powershell
# 5. Sanity-check
pensieve --help
pytest -q          # should show 29 passed
```

If all green, you're ready.

---

## First boot

```powershell
# Initialise local Chroma store (one-time)
pensieve init

# Start the FastAPI server on http://127.0.0.1:8765
pensieve serve --port 8765
```

In a second terminal (or browser tab), open
`frontend-proto/index.html` directly in your browser — it's a static page that
talks to `:8765`. You should see an empty kanban with four columns:

| Memory | Dive | Review | Closed |
|---|---|---|---|
| Backlog | Working on | Needs another look | Done |

Stop the server with Ctrl+C when you're done.

> 💡 **Optional but recommended:** run `tools\Install-PensieveAutoStart.ps1`
> once. It drops a Startup-folder shortcut so the backend launches (minimized)
> at every Windows logon — no more manual `pensieve serve`. See
> [tools/README.md](tools/README.md) for details. Disable any time with
> `Uninstall-PensieveAutoStart.ps1`.

---

## Importing your Connect goals (the magic step)

Pensieve aligns every task to one of your annual goals. You bring the goals
in by uploading your Connect PDF.

1. Export your Connect goals from the Connect tool as a PDF.
2. Open the dashboard, click **Set Goals** (top-right).
3. Click **Upload your Connect PDF** → pick the file.
4. Click **✨ Parse with AI**. After a few seconds you'll see your goals
   rendered as House cards. The AI assigns each goal a Harry Potter House
   colour (Gryffindor, Slytherin, Hufflepuff, Ravenclaw, plus four extras for
   teams with more than four goals).
5. Review the short names, tweak anything that looks off, click **Save goals**.

That's it. Your goals are saved to `data/connect-goals.json` (local to your
machine) and are now used by every future enrichment.

You can also click **+ Add goal** to add one by hand, or the **×** on any
goal card to remove it.

---

## First sync from Microsoft To-Do

```powershell
pensieve sync --source outlook_com
```

This:

1. Reads every uncompleted task from every To-Do list (via Outlook COM —
   read-only, no writes).
2. Sends each new task to your Azure OpenAI deployment for enrichment
   (suggested strand, why, impact, Connect-goal alignment).
3. Stores the enriched memories in a local ChromaDB at `data/chroma/`.

Already-completed tasks land directly in the **Closed** column.

Subsequent syncs only re-enrich tasks whose title or notes changed,
quietly auto-close tasks you completed in To-Do without burning AI tokens,
and **remove cards for tasks you deleted in To-Do** (scoped to the lists
you actually pulled from, so a narrow sync never erases work in other lists).

You can also trigger a sync from the dashboard with the **Pull from To-Do**
button — same result, no terminal needed.

---

## Day-to-day

| Action | How |
|---|---|
| Pull new tasks | Click **Pull from To-Do** on the dashboard, or `pensieve sync` in a terminal. |
| Edit a card | Click any card → modal → edit title / why / impact / strand / goal alignment → Save. |
| Regenerate with AI | Click ✨ **Regenerate** in the edit modal — re-runs the enrichment on demand. |
| Move a card | Drag to another column, or set it in the edit modal. Your placement survives re-syncs. |
| Filter by goal | Click a House chip in the goal sidebar. |
| Search | Use the search box (semantic — powered by Chroma). |
| Switch view | Toggle between **Lifecycle** (Memory → Dive → Review → Closed) and **Houses** (one column per goal). |

---

## Troubleshooting

**"DefaultAzureCredential failed"** → run `az login` and confirm
`az account show` returns your work identity.

**"Outlook COM error"** → Outlook desktop must be installed and signed in. Try
opening Outlook manually, waiting for To-Do tasks to appear under Tasks, then
re-run `pensieve sync`.

**Dashboard shows OLD column names (Reverie, Reflection, Vial)** → hard-refresh
your browser (Ctrl+Shift+R). The four-column model went live on 2026-05-28.

**"Pull from To-Do" doesn't pick up a title edit** → confirm you've restarted
the server since pulling latest. The content-diff detection landed 2026-05-28.

**API server won't start on `:8765`** → another process is using the port.
`pensieve serve --port 8766` and update the dashboard's API base in
`frontend-proto/pensieve.js` (`API_BASE`).

**Tests fail with "module not found"** → run `pip install -e ".[dev]"` again
from inside the venv.

---

## Privacy and data flow

| Data | Where it goes |
|---|---|
| Your To-Do tasks | Read locally from Outlook COM. Never sent anywhere except your Azure OpenAI deployment for enrichment. |
| Enrichment text (why, impact, etc.) | Stored in `data/chroma/` on your laptop. Never leaves. |
| Connect goals | Stored in `data/connect-goals.json` on your laptop. Never leaves. |
| LLM calls | Go to the Azure OpenAI endpoint you put in `.env` — typically a Microsoft-internal Cortex hub. |

Pensieve never writes back to Microsoft To-Do or to your Outlook. Phase 2 will
add an opt-in writeback path; until then, your tasks are untouched.

---

## Customising

- **Want different House names / colours?** Edit
  `pensieve/enrichment/goals_importer.py::HOUSE_PALETTE` and mirror it in
  `frontend-proto/pensieve.js`. Eight slots; goals beyond eight cycle.
- **Want different column names?** Edit `frontend-proto/pensieve.js`
  `LIFECYCLE_COLUMNS`, the four valid-column tuples in
  `pensieve/api/server.py` and `pensieve/cli.py`, and the migration map in
  `pensieve/store/chroma.py::_reconstruct`.
- **Want a different source?** Subclass `pensieve.sources.base.TaskSource`
  (Planner / ADO / Jira / etc.) — three methods to implement, no writes.

---

## What's next

- Run a sync, use the dashboard for a couple of days, and let us know what
  doesn't work.
- File issues at https://github.com/andy-herman/pensieve/issues.
- Phase 2 (opt-in writeback to To-Do Notes) and Phase 2.5 (Reverie — auto
  focus-block proposals) are on the roadmap; see `PHASES.md`.
