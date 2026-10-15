# Sharing Pensieve with a friend

Each person runs their own copy of Pensieve on their own PC and connects
their own accounts in the app. Nothing is hosted: tasks, memories, and
sign-ins stay on that person's machine.

## What your friend sees

On first launch, a **Connect your accounts** screen opens (later it lives
under More > Accounts):

1. **Sign in with Microsoft** (Microsoft To Do). Pensieve shows a short code;
   they click "Open sign-in page", enter the code, and approve Pensieve's
   read-only access to their To Do lists. This is how tasks from the new
   Outlook and outlook.com reach Pensieve.
2. **Sign in with GitHub** (GitHub Copilot). Same pattern: a code from
   GitHub's own Copilot sign-in. Their Copilot plan (Free, Pro, or Business)
   powers the AI. Models can be changed later under More > AI models.
3. **Read tasks from**: Microsoft To Do (new Outlook, outlook.com) or Outlook
   desktop on this PC (classic Outlook only).
4. **Start using Pensieve** runs the first sync.

## One-time setup by you: the Microsoft app id

Microsoft sign-in needs a public client id from an app registration. It is
not a secret, one registration serves everyone you share with, and it must
live in a personal Microsoft Entra directory, never Microsoft's corporate
tenant (corporate app registrations are locked down, and this repo's rules
forbid them).

1. Sign in to https://entra.microsoft.com with a **personal** Microsoft
   account. If you have no directory yet, Entra creates a free one.
2. **App registrations > New registration**. Name: `Pensieve`. Supported
   account types: **Personal Microsoft accounts only**. Leave Redirect URI
   empty. Register.
3. **Authentication > Advanced settings > Allow public client flows: Yes**.
   Save. (Pensieve signs in with device codes, which need this.)
4. **API permissions > Add a permission > Microsoft Graph > Delegated >
   `Tasks.Read`**. Personal accounts approve it themselves; no admin consent.
5. Copy the **Application (client) ID** into the shared copy's `.env`:
   `PERSONAL_GRAPH_CLIENT_ID=<id>`.

## Where things are stored on their PC

| What | Where |
| --- | --- |
| Microsoft sign-in (refresh token) | `data/ms-token-cache.bin`, encrypted with Windows DPAPI (only that Windows user can read it) |
| GitHub Copilot sign-in | Windows Credential Manager, written by the Copilot CLI |
| Which source to sync, setup seen | `data/connections.json` |
| Model choices | `data/ai-models.json` |
| Tasks and memories | `data/chroma/` |

Disconnect buttons in More > Accounts remove the Microsoft token and sign
the Copilot CLI out.

## Not done yet: the installer

Today a copy still needs this repo plus a Python environment and the
Copilot CLI (`npm install -g @github/copilot`). The plan for a one-click
installer: bundle Python and the backend (PyInstaller), ship x64 and ARM64
builds, let the Copilot SDK fetch its own CLI, and replace `.env` with the
app id baked in at build time. The Harry Potter theme is fine for a friend,
but strip it before any wider distribution (trademarks).
