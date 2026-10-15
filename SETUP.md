# Setting up Pensieve

> A copy-paste guide from clone to first sync in about ten minutes. Pensieve
> runs entirely on your Windows PC; the only accounts it needs are a GitHub
> account with Copilot and wherever your tasks live (Microsoft To Do or
> classic Outlook).
>
> Got a `PensieveSetup-<version>.exe` from someone? Just run it; this guide is
> for running Pensieve from the repo. Building that installer is covered in
> [desktop/SHARING.md](desktop/SHARING.md).

---

## Who this is for

You:

- capture most of your work in **Microsoft To Do** (any number of lists)
- want a kanban view of those tasks, enriched with *why*, *impact*, and which
  of your annual goals they advance
- want it all to run **locally**: no shared backend, no IT ticket

If your tasks live in Planner or ADO, Pensieve won't help you yet, but the
source layer is pluggable (subclass `pensieve.sources.base.TaskSource`).

---

## Prerequisites

| You need | Notes |
|---|---|
| **Windows 10/11** | Outlook COM and the DPAPI token cache are Windows-only. |
| **Python 3.11 or 3.12** | `python --version` to check. |
| **Git** | For cloning the repo. |
| **GitHub Copilot** | Any plan (Free, Pro, Business). For work tasks, use the account whose Copilot license may process that data, typically your company-managed one. |
| **Where your tasks live** | Either a **personal Microsoft account** with Microsoft To Do (works with the new Outlook and outlook.com), or **classic Outlook desktop** on this PC (work accounts). |
| **Copilot CLI** | `winget install GitHub.Copilot` or `npm install -g @github/copilot`. Pensieve finds either, or set `COPILOT_CLI_PATH`. |

Reading personal Microsoft To Do needs the public client id of a Pensieve app
registration in a **personal** Entra directory (`PERSONAL_GRAPH_CLIENT_ID`).
One registration serves everyone you share with; the one-time steps are in
[desktop/SHARING.md](desktop/SHARING.md). Classic Outlook needs no
registration at all.

---

## Install

```powershell
# 1. Clone
git clone https://github.com/andy-herman/pensieve.git
cd pensieve

# 2. Virtual env + editable install (dev extras add pytest and ruff)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 3. Env file
Copy-Item .env.example .env
notepad .env
```

In `.env`, check these (everything else has sensible defaults):

```ini
LLM_PROVIDER=github_copilot
# Optional: pin the GitHub login whose Copilot license pays for the calls.
# Blank = whoever signs in through the Accounts screen.
COPILOT_GITHUB_USER=
# Only if you read personal Microsoft To Do:
PERSONAL_GRAPH_CLIENT_ID=<application (client) id>
```

**Do not commit your `.env`**; it is already in `.gitignore`.

```powershell
# 4. Sanity check
pensieve init      # prints data dir, provider, model, task source, goals file
pytest -q          # everything should pass
```

---

## First run

```powershell
pensieve serve     # http://localhost:8765/
```

Or build the desktop app once and use that from then on:

```powershell
.\desktop\build.ps1   # desktop\dist\Pensieve.exe + Desktop and Start menu shortcuts
```

`Pensieve.exe` starts the backend hidden, opens Pensieve in its own window,
and stops the backend when you close it. It also gives each launch a private
session key, so only that window can use the API; `pensieve serve` run by
hand skips the key, which is handy for development. See
[desktop/README.md](desktop/README.md).

On first open, the **Connect your accounts** screen walks you through:

1. **Sign in with Microsoft** (only for Microsoft To Do): a short device code
   you enter on Microsoft's sign-in page. The token is cached in
   `data/ms-token-cache.bin`, encrypted with Windows DPAPI.
2. **Sign in with GitHub** for Copilot: the same device-code pattern, through
   the Copilot CLI's own login.
3. **Read tasks from**: Microsoft To Do, or Outlook desktop on this PC
   (classic Outlook only).
4. **Start using Pensieve** runs the first sync.

You can reopen it any time under **More > Accounts**. **More > AI models**
picks the Copilot model per job (sync enrichment, recaps, goals import, voice
capture) and can test that a model answers.

---

## Importing your Connect goals

Pensieve aligns every task to your annual goals. Bring them in from your
Connect PDF:

1. Open **More > Set goals**.
2. Upload your Connect PDF and click **Parse with AI**.
3. Review the proposed goals, tweak anything that looks off, and save.

Goals are saved to `data/connect-goals.json` and used by every future
enrichment. You can also add or remove goals by hand in the same editor.

---

## Syncing

The **Pull from To-Do** button (or `pensieve sync` in a terminal) reads every
task from the chosen source, read-only, and sends each new or changed task to
Copilot for enrichment. Results are stored in `data/chroma/`.

- Tasks you completed in To Do move to **Closed** without an LLM call.
- Tasks you deleted in To Do disappear, scoped to the lists that sync read.
- The backend also auto-syncs every two minutes
  (`PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS`).

From a terminal you can narrow a sync:

```powershell
pensieve sync --source outlook_com --list "Work"
pensieve sync --source personal_graph --dry-run   # no LLM calls
```

---

## Day-to-day

| Action | How |
|---|---|
| Pull new tasks | **Pull from To-Do**, or wait for auto-sync. |
| Add a task by voice | **Speak a task**: dictate, review the draft, click Add. Nothing is created until you do. |
| Edit a card | Click it, edit title / why / impact / strand / goals / due date, Save. |
| Regenerate with AI | **Regenerate** in the card modal re-runs enrichment for that card. |
| Move a card | Drag it. Your placement survives re-syncs. |
| Search | Type to filter; press Enter for semantic search. |
| Switch view | **Lifecycle** (Memory, Dive, Review, Closed) or **Houses** (one column per goal). |
| Draft a recap | **Recap** tab: pick scope and period, Generate, export to DOCX. |

---

## Troubleshooting

**Copilot sign-in or model errors** → open **More > Accounts** and reconnect
GitHub, then **More > AI models > Test**. If `COPILOT_GITHUB_USER` is set,
run `gh auth login` as that user. If the CLI is not found, install it with
winget or npm, or set `COPILOT_CLI_PATH`.

**"Open Pensieve from its desktop app to use it"** → the backend was started
by `Pensieve.exe` with a session key, and this browser tab does not have it.
Open Pensieve from its shortcut instead of typing the URL.

**"Connect your Microsoft account" or "sign-in has expired"** → reconnect
Microsoft in **More > Accounts**. Sync never prompts on its own.

**"Outlook COM unavailable"** → classic Outlook must be installed and signed
in. If you use the new Outlook day to day, Pensieve still drives classic
Outlook in the background; open it once so its profile exists.

**Port 8765 already in use** → set `PENSIEVE_BACKEND_PORT` in `.env`.

**Windows on ARM** → if pip tries to build `grpcio`, `chroma-hnswlib`, or
`cryptography` from source, install prebuilt wheels first (for example
`pip install --only-binary=cryptography cryptography`) or use an x64 Python.

**Tests fail with "module not found"** → run `pip install -e ".[dev]"` again
from inside the venv.

Desktop app logs live in `%LOCALAPPDATA%\Pensieve\logs\`.

---

## Privacy and data flow

| Data | Where it goes |
|---|---|
| Your tasks | Read on this PC (Graph for personal To Do, COM for Outlook). Sent only to your LLM provider for enrichment. |
| Enrichments, Vials, goals, recaps | `data/` on this PC. Never leave. |
| Microsoft sign-in | `data/ms-token-cache.bin`, DPAPI-encrypted. |
| Copilot sign-in | Windows Credential Manager, written by the Copilot CLI. |
| Spoken tasks | Recognized by the browser's speech service, drafted by Copilot. |

Pensieve does not edit your existing tasks unless you turn on the opt-in
column mirror or close writeback; voice capture only creates new tasks you
confirm. See [What Pensieve writes](README.md#what-pensieve-writes-and-when).

---

## Customizing

- **Lane colors**: `pensieve/enrichment/goals_importer.py::LANE_PALETTE` and
  the matching House map in `frontend-proto/pensieve.js`.
- **Column names**: `LIFECYCLE_COLUMNS` in `frontend-proto/pensieve.js`, the
  valid-column checks in `pensieve/api/server.py` and `pensieve/cli.py`, and
  the migration map in `pensieve/store/chroma.py::_reconstruct`.
- **A different source**: subclass `pensieve.sources.base.TaskSource` (two
  methods, no writes).

Other providers: [SETUP-personal-device.md](SETUP-personal-device.md) covers
GitHub Models and keeping work and personal data apart.

---

## What's next

- Use the dashboard for a few days and file issues at
  https://github.com/andy-herman/pensieve/issues.
- Phase 2.5 (Reverie focus blocks) and Phase 3 (reflection) are on the
  roadmap; see [PHASES.md](PHASES.md).
