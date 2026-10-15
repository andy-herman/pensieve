# Pensieve tools

Windows helpers for running the local Pensieve backend on your laptop.

> Looking for the legacy Phase 0 PowerShell prototype? That's in `scripts/`
> and is kept for historical reference only. Use the helpers here for
> day-to-day operation.

## Files

| Script | Purpose |
| --- | --- |
| `Start-Pensieve-Server.ps1` | Starts the FastAPI backend in the foreground using the repo's `.venv`. Reads `PENSIEVE_BACKEND_PORT` from `.env` (defaults to 8765). Skips startup if the port is already responding. |
| `Install-PensieveAutoStart.ps1` | Drops a shortcut into your Windows Startup folder so `Start-Pensieve-Server.ps1` runs minimized at every logon. No admin needed. Idempotent — re-run anytime. |
| `Uninstall-PensieveAutoStart.ps1` | Removes the Startup shortcut. Optional `-StopRunning` flag also kills the currently-running backend. |

## Recommended one-time setup

```powershell
cd "<repo>\tools"
.\Install-PensieveAutoStart.ps1
```

After this, the backend is up every time you log in — no more
"Pull from To-Do: failed to fetch" caused by a dead server. The console
window stays minimized in your taskbar (look for "Windows PowerShell"),
so you can click it any time to see live uvicorn logs.

## Other usage

```powershell
# Manually start the backend (e.g. you killed it and don't want to wait for next logon):
.\Start-Pensieve-Server.ps1

# Stop auto-starting it on logon:
.\Uninstall-PensieveAutoStart.ps1

# Also kill the currently-running backend on uninstall:
.\Uninstall-PensieveAutoStart.ps1 -StopRunning
```

## How auto-start works

`Install-PensieveAutoStart.ps1` creates a Windows shortcut at:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Pensieve Backend.lnk
```

The shortcut runs:

```
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <repo>\tools\Start-Pensieve-Server.ps1 -NoBrowser
```

…with the window minimized. The console stays alive as a minimized
taskbar window so you can:

- Click it to see live uvicorn / FastAPI logs
- Close it to stop the backend
- See its status in **Task Manager → Startup apps**

This is more reliable than a hidden Scheduled Task: uvicorn requires a
real console for its log handlers to initialize, and Scheduled Tasks
with hidden windows have intermittent failure modes around proxy
resolution and console allocation on corporate Windows installs.

## Troubleshooting

- **"Pull from To-Do" still fails after install:** click the minimized "Windows PowerShell" taskbar window and read the uvicorn output. Most common: the `.venv` is missing or `pip install -e .` was never run.
- **Backend window keeps closing immediately:** run `.\Start-Pensieve-Server.ps1` in a normal PowerShell window so you can see the full error before it disappears.
- **Port already in use:** another tool grabbed port 8765. Either kill it or set `PENSIEVE_BACKEND_PORT=8766` in `.env` and re-run `Install-PensieveAutoStart.ps1` so the shortcut picks up the new port.
- **Want to disable temporarily:** open Task Manager → Startup apps → right-click "Pensieve Backend" → Disable. Re-enable from the same place. (For permanent removal, use `Uninstall-PensieveAutoStart.ps1`.)
