# Pensieve desktop app

`Pensieve.exe` opens Pensieve in its own window, like any desktop app. No
terminal, no browser tab, no localhost URL to remember.

## What happens when you double-click it

1. It finds this repo, the repo's `.venv` Python, and the port from `.env`
   (`PENSIEVE_BACKEND_PORT`, default 8765).
2. It starts the backend hidden in the background, unless one is already
   running.
3. It opens Microsoft Edge in app mode (no tabs, no address bar) on a
   dedicated profile in `%LOCALAPPDATA%\Pensieve\EdgeProfile`. A short
   "Stirring the surface..." splash shows while the backend warms up.
4. When you close the last Pensieve window, it stops the backend it started.
   If it found a backend already running (for example one started by
   `tools\Install-PensieveAutoStart.ps1`), it leaves that one alone.

Double-clicking again while Pensieve is open just opens another window.

The UI still talks to the backend over a private loopback port
(127.0.0.1), which never leaves the machine. All data stays in `data/`.

## Build

```powershell
.\desktop\build.ps1               # builds desktop\dist\Pensieve.exe + Desktop and Start menu shortcuts
.\desktop\build.ps1 -NoShortcuts  # build only
```

Uses the .NET Framework C# compiler that ships with Windows, so there is
nothing to install. The repo path is baked in as a fallback, so rerun the
build if you move the repo. `PENSIEVE_HOME` and `PENSIEVE_PYTHON` environment
variables override the repo and Python paths.

To change the icon, edit `pensieve-icon.svg` and run `.\desktop\Make-Icon.ps1`
(regenerates `pensieve.ico` and `frontend-proto\favicon.ico`).

## Troubleshooting

Logs live in `%LOCALAPPDATA%\Pensieve\logs\`:

- `launcher.log`: what the launcher did (paths, start, stop).
- `server.log`: backend output (uvicorn, sync results, enrichment errors).

If the window shows the splash forever, check `server.log`. The usual causes
are a broken `.venv` (rebuild it; see the repo SETUP notes for the win-arm64
workarounds) or another program already using the port.
