# Setting up Pensieve on a personal device

> Companion to `SETUP.md`. Use this when you do **not** have a corporate
> Azure OpenAI Cortex hub or work Outlook account, and want to run Pensieve
> on a personal laptop against your personal Microsoft account and a
> personal-tier LLM.

This swaps two pieces of the default install:

| Default (corp install) | Personal-device install |
|---|---|
| Azure OpenAI Cortex hub (`DefaultAzureCredential`) | **GitHub Models** (PAT) |
| Outlook desktop COM (read-only) | **Personal Microsoft Graph** (`/me/todo`) |

Everything else — ChromaDB, FastAPI, the HP dashboard, the 4-column
lifecycle, regenerate, the Connect PDF importer — works identically.

---

## Prerequisites

| You need | How to get it |
|---|---|
| **Python 3.11 or 3.12** | https://www.python.org/downloads/ |
| **Git** | https://git-scm.com/downloads |
| **A personal Microsoft account** | outlook.com / hotmail.com / live.com / @outlook.* — anything that signs in to https://to-do.office.com |
| **A GitHub account** | https://github.com (free plan is fine) |
| **Your tasks already in Microsoft To-Do** | If you only use the Tasks pane in Outlook on the web, those are already there |

You do **not** need: admin rights, a corporate Entra app registration,
Azure credits, a paid OpenAI key, or classic Outlook installed.

---

## Step 1 — Clone and install

```powershell
cd "$HOME\Coding Projects (Local)"
git clone https://github.com/andy-herman/pensieve.git
cd pensieve

python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Personal install adds the msal dependency for Graph auth.
pip install -e .[dev,personal]
```

On macOS / Linux the same commands work with `source .venv/bin/activate`.
The `pywin32` dependency is gated to Windows and will be skipped.

---

## Step 2 — Set up the LLM provider (GitHub Models)

Generate a PAT with the `models:read` scope:

1. Go to https://github.com/settings/personal-access-tokens/new
2. **Token name:** `pensieve-personal`
3. **Expiration:** whatever you're comfortable with (90 days is fine; you'll get email reminders)
4. **Repository access:** `Public Repositories (read-only)` is enough
5. **Permissions → Account permissions → Models:** `Read-only`
6. Click **Generate token** and copy the `ghp_…` value

Pick a model from https://github.com/marketplace/models — `openai/gpt-4o-mini`
is a sensible default (fast, cheap, plenty good for enrichment). You can
swap later by changing one env var.

> **Rate limits.** GitHub Models has free-tier rate limits (per-minute and
> per-day token caps that vary by model class). For personal enrichment
> volumes (a few dozen tasks per sync) you'll stay inside them. If you hit
> a 429 during a big initial sync, wait a few minutes and rerun — the
> orchestrator's drift-detection means you only re-enrich what's left.

---

## Step 3 — Set up the task source (personal Microsoft Graph)

You need an app registration in your personal MS account. This is free
and self-service — no admin consent involved.

1. Go to https://entra.microsoft.com → **Identity → Applications → App registrations → New registration**
   (If Entra refuses your personal account, use https://aka.ms/AppRegistrations directly.)
2. **Name:** `Pensieve personal`
3. **Supported account types:** **Personal Microsoft accounts only**
   (or "Accounts in any organizational directory and personal Microsoft accounts" if you want both)
4. **Redirect URI:** leave blank
5. Click **Register**
6. On the new app page → **Authentication** → **Allow public client flows** → **Yes** → Save
7. **API permissions → Add a permission → Microsoft Graph → Delegated permissions → Tasks.Read** → Add
8. Copy the **Application (client) ID** — you'll need it in the env file

That's it. Total time: under three minutes.

---

## Step 4 — Configure the env file

```powershell
Copy-Item .env.example .env
notepad .env
```

Set these four blocks:

```ini
# Use GitHub Models instead of Azure OpenAI
LLM_PROVIDER=github_models
GITHUB_TOKEN=ghp_your_pat_here
GITHUB_MODELS_MODEL=openai/gpt-4o-mini

# Use personal Graph instead of Outlook COM
PENSIEVE_DEFAULT_SOURCE=personal_graph
PERSONAL_GRAPH_CLIENT_ID=00000000-0000-0000-0000-000000000000   # your Application (client) ID
```

You can leave the `AZURE_OPENAI_*` lines as-is — they're ignored when
`LLM_PROVIDER=github_models`.

---

## Step 5 — First boot

```powershell
pensieve init
```

You should see your data dir, Chroma path, and zero memories.

```powershell
pensieve sync --source personal_graph --dry-run
```

The first time you run this, MSAL will print a device-code prompt:

```
To sign in, use a web browser to open the page https://microsoft.com/devicelogin
and enter the code ABCD-EFGH to authenticate.
```

Open that URL in any browser, sign in with your personal MS account,
paste the code, and approve the `Tasks.Read` request. MSAL caches the
refresh token under `data/personal-graph-token-cache.bin` — you won't
have to do this again unless you delete that file.

Once authenticated, you should see your To-Do lists and task counts
print. Drop `--dry-run` to actually enrich them.

```powershell
pensieve serve
```

Open `http://localhost:8765` for the HP-themed dashboard. The 🦉
**Pull from To-Do** button hits the same `personal_graph` source.

---

## Day-to-day

Same as the corp install. The only differences live in the env file.

- `pensieve sync --source personal_graph` — pull + enrich
- `pensieve sync --source personal_graph --list "Personal" --list "Side projects"` — narrow to specific lists
- `pensieve status` — Chroma + config snapshot
- `pensieve serve` — dashboard at `:8765`

---

## Switching between corp and personal

The provider abstraction is fully runtime-configurable. To switch:

```powershell
# Corp/work day
LLM_PROVIDER=azure_openai
PENSIEVE_DEFAULT_SOURCE=outlook_com

# Personal evening / weekend
LLM_PROVIDER=github_models
PENSIEVE_DEFAULT_SOURCE=personal_graph
```

Keep the Chroma store under a different `PENSIEVE_DATA_DIR` per profile
if you want a clean separation between work and personal memories.

---

## Troubleshooting

**"msal is not installed"** — you skipped the `[personal]` extra. Run
`pip install msal` or `pip install -e .[dev,personal]`.

**"PERSONAL_GRAPH_CLIENT_ID is not set"** — you didn't paste the
Application (client) ID into `.env`, or you spelled the env var wrong.

**Graph returns 401 / 403** — your PAT for GitHub Models is fine, but
the Graph token is rejected. Most common: you registered the app with
"Accounts in this organizational directory only" instead of "Personal
Microsoft accounts". Re-register with the personal-account option.

**429 from GitHub Models** — you hit the per-minute rate cap. Wait a
minute. For initial sync of a big To-Do, run with `--list` to narrow.

**`pensieve sync` re-prompts every time** — your token cache isn't being
written. Check `data/personal-graph-token-cache.bin` exists and is
writable; check `PENSIEVE_DATA_DIR` points to a writable location.

**You want to revoke the device-flow token** — delete
`data/personal-graph-token-cache.bin` and re-run sync.

---

## Privacy and data flow

```
Microsoft To-Do (your personal lists)
        |
        | HTTPS, Graph /me/todo, Tasks.Read only
        v
PersonalGraphSource (read-only, never writes back)
        |
        v
GitHub Models (your PAT, your task content goes to OpenAI/Anthropic via GitHub's gateway)
        |
        v
ChromaDB on disk (your machine only)
        |
        v
HP dashboard at localhost:8765 (no outbound calls)
```

What leaves your machine:

- **Task title + notes → GitHub Models** (one chat completion per
  enriched task). Subject to GitHub Models' data handling — see
  https://docs.github.com/en/github-models/about-the-api-features#data
- **Token requests → Microsoft Graph** (your PAT-equivalent OAuth token)
- **Nothing else.** No telemetry, no analytics, no shared backend.

If you want to swap GitHub Models for a local model (Ollama, LM Studio),
the provider abstraction makes that a future-additional client of the
same `.chat()` shape — file an issue and PRs welcome.
