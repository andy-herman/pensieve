# Sharing Pensieve with a friend

Each person runs their own copy of Pensieve on their own PC and connects
their own accounts in the app. Nothing is hosted: tasks, memories, and
sign-ins stay on that person's machine.

## What your friend sees

On first launch, a **Connect your accounts** screen opens (later it lives
under More > Accounts):

1. **Sign in with Microsoft** (Microsoft To Do). Pensieve shows a short code;
   they click "Open sign-in page", enter the code, and approve Pensieve's
   access to their To Do lists (read, plus adding tasks they dictate). This is how tasks from the new
   Outlook and outlook.com reach Pensieve.
2. **Sign in with GitHub** (GitHub Copilot). Same pattern: a code from
   GitHub's own Copilot sign-in. Their Copilot plan (Free, Pro, or Business)
   powers the AI. Models can be changed later under More > AI models.
3. **Read tasks from**: Microsoft To Do (new Outlook, outlook.com) or Outlook
   desktop on this PC (classic Outlook only).
4. **Start using Pensieve** runs the first sync.

After that, **Speak a task** (toolbar) lets them dictate a task. Edge asks
once for microphone access; the words are recognized by Edge's built-in
speech service, Copilot drafts the task, and nothing is added until they
click Add.

## One-time setup by you: the Microsoft app id

Microsoft sign-in needs a public client id from an app registration. It is
not a secret, one registration serves everyone you share with, and it must
live in a personal Microsoft Entra directory, never Microsoft's corporate
tenant (corporate app registrations are locked down, and this repo's rules
forbid them).

1. Sign in to https://entra.microsoft.com with a **personal** Microsoft
   account. If it says you have no directory, create a free one first (a
   free Azure account sets one up); never use a work tenant.
2. **App registrations > New registration**. Name: `Pensieve`. Supported
   account types: **Personal Microsoft accounts only**. Leave Redirect URI
   empty. Register.
3. **Authentication > Advanced settings > Allow public client flows: Yes**.
   Save. (Pensieve signs in with device codes, which need this.)
4. **API permissions > Add a permission > Microsoft Graph > Delegated >
   `Tasks.ReadWrite`**. Personal accounts approve it themselves; no admin
   consent. Pensieve only reads, plus adds a new task when someone confirms
   one in Speak a task; it never edits or deletes their tasks.
5. Copy the **Application (client) ID** and build the installer with it
   (below). It is baked into the installed app's `pensieve.env`. Someone who
   already installed a build without it can instead add
   `PERSONAL_GRAPH_CLIENT_ID=<id>` to `%LOCALAPPDATA%\Pensieve\pensieve.env`.

## Building the installer

On this PC (Windows ARM64 or x64), from the repo:

```powershell
.\desktop\installeruild-installer.ps1 -Version 1.0.0 -MicrosoftClientId <application-client-id>
```

The first run downloads an x64 Python and Inno Setup into
`..\pensieve-build` and takes a while; later runs reuse them. It bundles the
backend with PyInstaller, smoke-tests it, and writes
`..\pensieve-build\output\PensieveSetup-<version>.exe` (about 130 MB). The x64
build runs natively on x64 PCs and under emulation on ARM64 PCs.

## Sending it

Send the `.exe` through OneDrive, Google Drive, or a USB stick (most mail
services block executables). Tell your friend:

1. **Windows protected your PC** appears because the installer is not code
   signed. Click **More info > Run anyway**.
2. The installer needs no admin rights. It installs for their Windows user
   only, shows the license and privacy terms, and offers to install the
   GitHub Copilot CLI with Windows Package Manager (leave it ticked).
3. Pensieve opens in its own window and shows **Connect your accounts**.
4. More > About & legal has the privacy notice, AI notice, license and
   third-party notices.

## Where things are stored on their PC

Installed copies keep everything under `%LOCALAPPDATA%\Pensieve` (paths
below are relative to its `data` folder). A copy run from this repo uses the
repo's `data` folder instead.

| What | Where |
| --- | --- |
| Microsoft sign-in (refresh token) | `ms-token-cache.bin`, encrypted with Windows DPAPI (only that Windows user can read it) |
| GitHub Copilot sign-in | Windows Credential Manager, written by the Copilot CLI |
| Which source to sync, setup seen | `connections.json` |
| Model choices | `ai-models.json` |
| Tasks and memories | `chroma/` |
| Personal overrides | `%LOCALAPPDATA%\Pensieve\pensieve.env` (wins over the installed defaults) |

Disconnect buttons in More > Accounts remove the Microsoft token and sign
the Copilot CLI out. Uninstalling (Settings > Apps) asks whether to delete
`%LOCALAPPDATA%\Pensieve` too.

## Security model

The backend listens only on `127.0.0.1`. Each launch of `Pensieve.exe`
creates a random session key; the backend refuses API calls without it and
answers only to `127.0.0.1` and `localhost`, so web pages and other Windows
users on the same PC cannot reach someone's board. The dashboard runs under
a Content-Security-Policy that only allows the app's own scripts.

The Harry Potter theme is fine for a friend, but strip it before any wider
distribution (trademarks).
