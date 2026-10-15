<#
.SYNOPSIS
Removes the Pensieve auto-start shortcut installed by
Install-PensieveAutoStart.ps1. Also cleans up the legacy
"Pensieve Backend" Scheduled Task if present.

.PARAMETER ShortcutName
Override the shortcut filename (no extension). Default: "Pensieve Backend".

.PARAMETER StopRunning
Also kill any currently-running Pensieve backend python process.
Without this flag, the shortcut is removed but the already-running
backend keeps serving until you close its window or reboot.
#>
[CmdletBinding()]
param(
    [string]$ShortcutName = "Pensieve Backend",
    [switch]$StopRunning
)

$ErrorActionPreference = "Stop"

$removed = $false

# Remove startup shortcut.
$startupDir = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupDir "$ShortcutName.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "[OK] Removed startup shortcut: $shortcutPath" -ForegroundColor Green
    $removed = $true
}

# Remove legacy Scheduled Task if it exists (from an older installer revision).
$legacyTask = Get-ScheduledTask -TaskName "Pensieve Backend" -ErrorAction SilentlyContinue
if ($legacyTask) {
    Unregister-ScheduledTask -TaskName "Pensieve Backend" -Confirm:$false
    Write-Host "[OK] Removed legacy Scheduled Task 'Pensieve Backend'." -ForegroundColor Green
    $removed = $true
}

if (-not $removed) {
    Write-Host "No Pensieve auto-start found. Nothing to do."
}

if ($StopRunning) {
    $candidates = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match "pensieve\.cli\s+serve" -or $_.CommandLine -match "uvicorn\s+pensieve" }
    foreach ($c in $candidates) {
        try {
            Stop-Process -Id $c.ProcessId -Force -ErrorAction Stop
            Write-Host "[OK] Stopped Pensieve backend PID $($c.ProcessId)."
        } catch {
            Write-Warning "Could not stop PID $($c.ProcessId): $_"
        }
    }
}

Write-Host ""
Write-Host "Pensieve will no longer auto-start at logon."
Write-Host "To restart manually: .\Start-Pensieve-Server.ps1"
