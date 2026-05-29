<#
.SYNOPSIS
Starts the Pensieve FastAPI backend on the configured port.

.DESCRIPTION
Resolves the repo root, the .venv Python interpreter, and the port
(from .env if PENSIEVE_BACKEND_PORT is set, otherwise 8765), then runs
`python -m pensieve.cli serve` in the foreground.

Designed to be invoked by:
  - A user double-click ("just start Pensieve")
  - The auto-start shortcut installed by Install-PensieveAutoStart.ps1
    (which launches this script with -WindowStyle Minimized so the
    console stays accessible in the taskbar for debugging)

Exits non-zero on misconfiguration.

.PARAMETER Port
Override the port. Otherwise defaults to PENSIEVE_BACKEND_PORT from .env
(if set) or 8765.

.PARAMETER NoBrowser
By default, when run interactively, opens http://localhost:<port>/ once
the server is up. Pass -NoBrowser to skip (auto-start shortcut uses this).
#>
[CmdletBinding()]
param(
    [int]$Port = 0,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[ERROR] Pensieve venv not found at $venvPython" -ForegroundColor Red
    Write-Host "Run: cd '$repoRoot'; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e .[dev]"
    Read-Host "Press Enter to close"
    exit 2
}

if ($Port -eq 0) {
    $envFile = Join-Path $repoRoot ".env"
    if (Test-Path $envFile) {
        $portLine = Select-String -Path $envFile -Pattern "^\s*PENSIEVE_BACKEND_PORT\s*=\s*(\d+)" | Select-Object -First 1
        if ($portLine -and $portLine.Matches[0].Groups[1].Value) {
            $Port = [int]$portLine.Matches[0].Groups[1].Value
        }
    }
    if ($Port -eq 0) { $Port = 8765 }
}

# Raw TCP socket check — no Invoke-WebRequest (which can hang on proxy
# resolution under non-interactive contexts).
$alreadyUp = $false
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(1500, $false) -and $tcp.Connected) {
        $alreadyUp = $true
    }
    $tcp.Close()
} catch { }

if ($alreadyUp) {
    Write-Host "Pensieve already responding on port $Port. Nothing to do." -ForegroundColor Yellow
    if (-not $NoBrowser -and [Environment]::UserInteractive) {
        Start-Process "http://localhost:$Port/"
    }
    exit 0
}

Write-Host "Starting Pensieve backend on port $Port from $repoRoot ..." -ForegroundColor Cyan
Write-Host "(Leave this window open. Closing it stops the backend.)" -ForegroundColor DarkGray
Write-Host ""

Push-Location $repoRoot
try {
    & $venvPython -m pensieve.cli serve --port $Port
} finally {
    Pop-Location
}
