<#
.SYNOPSIS
Installs an auto-start shortcut so the Pensieve backend launches every
time you log in to Windows. No admin needed.

.DESCRIPTION
Creates a shortcut in your per-user Startup folder
(%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup) that runs
`Start-Pensieve-Server.ps1` in a minimized PowerShell window at logon.

Why a Startup shortcut instead of a Scheduled Task?
  - Real console attached → uvicorn output is visible (just click the
    minimized taskbar window to see live logs).
  - No silent failures: if the venv or .env is missing, the launcher
    prints a clear error and waits for Enter.
  - Trivially debuggable: open Task Manager > Startup apps to see status.
  - Trivially disabled: run Uninstall-PensieveAutoStart.ps1 or just
    delete the shortcut from the Startup folder.

Also removes any legacy "Pensieve Backend" Scheduled Task from earlier
versions of this installer.

.PARAMETER ShortcutName
Override the shortcut filename (no extension). Default: "Pensieve Backend".

.PARAMETER Force
Replace any existing shortcut with the same name without prompting.

.EXAMPLE
.\Install-PensieveAutoStart.ps1
Installs the shortcut. If one already exists, prompts before replacing.

.EXAMPLE
.\Install-PensieveAutoStart.ps1 -Force
Replaces any existing shortcut silently.
#>
[CmdletBinding()]
param(
    [string]$ShortcutName = "Pensieve Backend",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $PSScriptRoot "Start-Pensieve-Server.ps1"

if (-not (Test-Path $launcher)) {
    Write-Error "Launcher not found at $launcher. Did you move this script?"
    exit 2
}

# Clean up any legacy Scheduled Task from a previous installer revision.
$legacyTask = Get-ScheduledTask -TaskName "Pensieve Backend" -ErrorAction SilentlyContinue
if ($legacyTask) {
    Unregister-ScheduledTask -TaskName "Pensieve Backend" -Confirm:$false
    Write-Host "[INFO] Removed legacy Scheduled Task 'Pensieve Backend'." -ForegroundColor DarkYellow
}

$startupDir = [Environment]::GetFolderPath("Startup")
if (-not (Test-Path $startupDir)) {
    Write-Error "Startup folder not found at $startupDir"
    exit 2
}

$shortcutPath = Join-Path $startupDir "$ShortcutName.lnk"

if (Test-Path $shortcutPath) {
    if (-not $Force) {
        $ans = Read-Host "Shortcut '$ShortcutName.lnk' already exists in Startup. Replace? (y/N)"
        if ($ans -ne "y" -and $ans -ne "Y") {
            Write-Host "Aborted."
            exit 0
        }
    }
    Remove-Item $shortcutPath -Force
    Write-Host "Removed existing shortcut."
}

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($shortcutPath)
$sc.TargetPath = "powershell.exe"
$sc.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`" -NoBrowser"
$sc.WorkingDirectory = $repoRoot
$sc.WindowStyle = 7  # 7 = Minimized
$sc.IconLocation = "powershell.exe,0"
$sc.Description = "Auto-starts the Pensieve local FastAPI backend on logon. See Pensieve\tools\Start-Pensieve-Server.ps1."
$sc.Save()

Write-Host ""
Write-Host "[OK] Installed auto-start shortcut:" -ForegroundColor Green
Write-Host "     $shortcutPath"
Write-Host "     Runs: $launcher (minimized)"
Write-Host ""
Write-Host "Starting it now so you don't have to log out and back in..."
# Invoke the shortcut the same way Explorer does at logon, rather than
# calling Start-Process directly — the latter has subtle console-inheritance
# issues that can prevent uvicorn from initializing under a minimized
# window when launched from another PowerShell session.
Invoke-Item $shortcutPath

# Wait for the backend to come up.
$port = 8765
$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    $portLine = Select-String -Path $envFile -Pattern "^\s*PENSIEVE_BACKEND_PORT\s*=\s*(\d+)" | Select-Object -First 1
    if ($portLine) { $port = [int]$portLine.Matches[0].Groups[1].Value }
}

Write-Host "Waiting up to 30s for backend on port $port ..."
$up = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/healthz" -TimeoutSec 2
        if ($h.ok) {
            Write-Host "[OK] Pensieve backend is up. Memories: $($h.memories)" -ForegroundColor Green
            Write-Host "     Dashboard: http://localhost:$port/"
            $up = $true
            break
        }
    } catch { }
}

if (-not $up) {
    Write-Warning "Backend didn't respond within 30s. Click the minimized 'Windows PowerShell' taskbar icon to see uvicorn output and diagnose."
}

Write-Host ""
Write-Host "To remove auto-start later:"
Write-Host "  .\Uninstall-PensieveAutoStart.ps1"
