<#
.SYNOPSIS
Builds PensieveSetup-<version>.exe, a Windows installer you can send to a friend.

.DESCRIPTION
1. Bootstraps an x64 Python build toolchain outside the repo (once).
2. Compiles the Pensieve.exe launcher.
3. Generates THIRD-PARTY-NOTICES.txt from the exact packages being bundled.
4. Bundles the backend with PyInstaller (server\pensieve-server.exe).
5. Stages the app with baked defaults (pensieve.env) and wizard art.
6. Smoke-tests the bundled backend on a spare port with a throwaway data folder.
7. Compiles the installer with Inno Setup (ISCC).

The backend is x64, so one installer runs natively on x64 PCs and through
Windows' x64 emulation on ARM64 PCs.

.PARAMETER MicrosoftClientId
Public client id of the Pensieve app registration (see desktop/SHARING.md).
Without it the installed app cannot sign in to Microsoft To Do.

.PARAMETER CopilotModel
Default GitHub Copilot model for the installed app. gpt-5-mini is included in
every Copilot plan without spending premium requests; people can change it in
More > AI models.

.PARAMETER SkipServer
Reuse the previous PyInstaller output (faster when only the launcher, the
installer script or the baked settings changed).
#>
[CmdletBinding()]
param(
    [string]$Version = "1.0.0",
    [string]$MicrosoftClientId = "",
    [string]$CopilotModel = "gpt-5-mini",
    [string]$BuildRoot = "",
    [switch]$SkipServer
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here "..\..")).Path
if (-not $BuildRoot) { $BuildRoot = Join-Path (Split-Path $repo -Parent) "pensieve-build" }
$pyHome = Join-Path $BuildRoot "python-x64"
$venvPy = Join-Path $BuildRoot "venv-x64\Scripts\python.exe"
$stage = Join-Path $BuildRoot "stage"
$output = Join-Path $BuildRoot "output"

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }

# ---- 1. x64 toolchain ---------------------------------------------------------------
if (-not (Test-Path $venvPy)) {
    Step "Bootstrapping the x64 Python toolchain in $BuildRoot"
    New-Item -ItemType Directory -Force (Join-Path $BuildRoot "downloads"), $pyHome | Out-Null
    $pkg = Join-Path $BuildRoot "downloads\python-3.12.10-x64.nupkg"
    if (-not (Test-Path $pkg)) {
        Invoke-WebRequest -Uri "https://www.nuget.org/api/v2/package/python/3.12.10" -OutFile $pkg -UseBasicParsing
    }
    Expand-Archive -Path $pkg -DestinationPath $pyHome -Force
    $sig = Get-AuthenticodeSignature (Join-Path $pyHome "tools\python.exe")
    if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "Python Software Foundation") {
        throw "python.exe from nuget is not signed by the Python Software Foundation."
    }
    & (Join-Path $pyHome "tools\python.exe") -m venv (Join-Path $BuildRoot "venv-x64")
    & $venvPy -m pip install -q --upgrade pip setuptools wheel
    & $venvPy -m pip install -q -c (Join-Path $here "constraints-x64.txt") $repo pyinstaller
    & $venvPy -m pip uninstall -y -q pensieve  # the spec bundles the package from source
}

# ---- 2. launcher ---------------------------------------------------------------------
Step "Compiling the launcher"
& (Join-Path $repo "desktop\build.ps1") -NoShortcuts
$launcher = Join-Path $repo "desktop\dist\Pensieve.exe"

# ---- 3. embedding model + notices ----------------------------------------------------
$modelDir = Join-Path $env:USERPROFILE ".cache\chroma\onnx_models\all-MiniLM-L6-v2"
if (-not (Test-Path (Join-Path $modelDir "onnx\model.onnx"))) {
    Step "Downloading the embedding model once (Chroma's all-MiniLM-L6-v2)"
    & $venvPy -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as D; D()(['warm up'])"
}
Step "Generating third-party notices"
New-Item -ItemType Directory -Force $stage | Out-Null
$notices = Join-Path $stage "THIRD-PARTY-NOTICES.txt"
& $venvPy (Join-Path $here "make_notices.py") $notices --python-license (Join-Path $pyHome "tools\LICENSE.txt")
if ($LASTEXITCODE -ne 0) { throw "make_notices.py failed ($LASTEXITCODE)" }
Copy-Item $notices (Join-Path $repo "frontend-proto\third-party-notices.txt") -Force  # shown in About and legal

# ---- 4. backend bundle -----------------------------------------------------------------
if (-not $SkipServer) {
    Step "Bundling the backend with PyInstaller (several minutes)"
    $env:PENSIEVE_MODEL_DIR = $modelDir
    & $venvPy -m PyInstaller (Join-Path $here "pensieve-server.spec") --noconfirm --log-level WARN `
        --distpath (Join-Path $BuildRoot "dist") --workpath (Join-Path $BuildRoot "work")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }
}

# ---- 5. stage ------------------------------------------------------------------------
Step "Staging the app"
foreach ($item in "server", "installer-art", "Pensieve.exe", "pensieve.ico", "pensieve.env", "LICENSE-AND-PRIVACY.txt") {
    $p = Join-Path $stage $item
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
Copy-Item -Recurse (Join-Path $BuildRoot "dist\server") (Join-Path $stage "server")
Copy-Item $launcher $stage
Copy-Item (Join-Path $repo "desktop\pensieve.ico") $stage
Copy-Item (Join-Path $here "LICENSE-AND-PRIVACY.txt") $stage

if (-not $MicrosoftClientId) {
    Write-Warning "No -MicrosoftClientId: the installed app will say Microsoft To Do is not set up yet. See desktop/SHARING.md."
}
$envText = @"
# Pensieve installed defaults (written by the installer; replaced on upgrade).
# Put your own overrides in %LOCALAPPDATA%\Pensieve\pensieve.env, which wins.
LLM_PROVIDER=github_copilot
COPILOT_MODEL=$CopilotModel
PENSIEVE_DEFAULT_SOURCE=personal_graph
PERSONAL_GRAPH_CLIENT_ID=$MicrosoftClientId
PENSIEVE_RECAP_LIST_NAMES=
PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS=120
PENSIEVE_API_CORS_ORIGINS=http://127.0.0.1:8765,http://localhost:8765
"@
Set-Content -Path (Join-Path $stage "pensieve.env") -Value $envText -Encoding UTF8

# Wizard art from the rendered emblem: a tall side panel and a small header badge.
Add-Type -AssemblyName System.Drawing
$art = Join-Path $stage "installer-art"
New-Item -ItemType Directory -Force $art | Out-Null
$emblem = [System.Drawing.Image]::FromFile((Join-Path $repo "desktop\art\pensieve-emblem.png"))
function New-Panel([int]$w, [int]$h, [string]$path, [double]$emblemFrac, [bool]$withTitle) {
    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = "HighQualityBicubic"; $g.SmoothingMode = "HighQuality"; $g.TextRenderingHint = "AntiAliasGridFit"
    $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect,
        [System.Drawing.Color]::FromArgb(255, 30, 40, 78), [System.Drawing.Color]::FromArgb(255, 8, 11, 24), 90.0)
    $g.FillRectangle($brush, $rect)
    $ew = [int]($w * $emblemFrac); $eh = [int]($emblem.Height * $ew / $emblem.Width)
    $ey = if ($withTitle) { [int]($h * 0.30) } else { [int](($h - $eh) / 2) }
    $g.DrawImage($emblem, [int](($w - $ew) / 2), $ey, $ew, $eh)
    if ($withTitle) {
        $font = New-Object System.Drawing.Font("Georgia", 15, [System.Drawing.FontStyle]::Bold)
        $gold = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 233, 207, 138))
        $fmt = New-Object System.Drawing.StringFormat; $fmt.Alignment = "Center"
        $g.DrawString("PENSIEVE", $font, $gold, (New-Object System.Drawing.RectangleF(0, [single]($ey + $eh + 14), $w, 30)), $fmt)
    }
    $g.Dispose(); $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Bmp); $bmp.Dispose()
}
New-Panel 164 314 (Join-Path $art "wizard-large.bmp") 0.82 $true
New-Panel 58 58 (Join-Path $art "wizard-small.bmp") 0.86 $false
$emblem.Dispose()

# ---- 6. smoke test -------------------------------------------------------------------
Step "Smoke-testing the bundled backend"
$tmpData = Join-Path $BuildRoot ("smoke-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
$env:PENSIEVE_DATA_DIR = $tmpData
$env:PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS = "0"
$env:COPILOT_PREWARM = "0"
$env:PENSIEVE_SESSION_TOKEN = "smoke-" + [Guid]::NewGuid().ToString("N")
$auth = @{ "X-Pensieve-Token" = $env:PENSIEVE_SESSION_TOKEN }
$proc = Start-Process (Join-Path $stage "server\pensieve-server.exe") -ArgumentList "--port", "8799" -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $BuildRoot "smoke.out.log") -RedirectStandardError (Join-Path $BuildRoot "smoke.err.log")
try {
    $ok = $false
    for ($i = 0; $i -lt 180; $i++) {
        try { $h = Invoke-RestMethod "http://127.0.0.1:8799/api/healthz" -TimeoutSec 2; $ok = $true; break } catch { Start-Sleep -Milliseconds 500 }
        if ($proc.HasExited) { break }
    }
    if (-not $ok) { throw "Bundled backend did not start; see $BuildRoot\smoke.err.log" }
    $page = Invoke-WebRequest "http://127.0.0.1:8799/" -UseBasicParsing -TimeoutSec 10
    if ($page.Content -notmatch "The Pensieve") { throw "Dashboard was not served by the bundle." }
    if ($page.Headers["Content-Security-Policy"] -notmatch "script-src 'self'") { throw "Dashboard is missing its Content-Security-Policy." }
    $locked = $false
    try { $null = Invoke-WebRequest "http://127.0.0.1:8799/api/goals" -UseBasicParsing -TimeoutSec 10 } catch { $locked = ($_.Exception.Response.StatusCode.value__ -eq 401) }
    if (-not $locked) { throw "The bundled API answered without the session key." }
    $goals = Invoke-RestMethod "http://127.0.0.1:8799/api/goals" -Headers $auth -TimeoutSec 10
    if (($goals.goals | Measure-Object).Count -ne 4) { throw "Starter goals were not seeded." }
    $strands = Invoke-RestMethod "http://127.0.0.1:8799/api/strands" -Headers $auth -TimeoutSec 10
    if (($strands.strands | Measure-Object).Count -lt 1) { throw "Starter strands were not seeded." }
    $null = Invoke-RestMethod "http://127.0.0.1:8799/api/search?q=planning" -Headers $auth -TimeoutSec 60   # embedding model loads
    Write-Host "   healthz ok, dashboard + CSP served, API locked without the key, starter goals and strands seeded, embeddings work" -ForegroundColor Green
} finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    Remove-Item Env:PENSIEVE_DATA_DIR, Env:PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS, Env:COPILOT_PREWARM, Env:PENSIEVE_SESSION_TOKEN -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Remove-Item $tmpData -Recurse -Force -ErrorAction SilentlyContinue
}

# ---- 7. installer --------------------------------------------------------------------
Step "Compiling the installer"
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup --scope user" }
New-Item -ItemType Directory -Force $output | Out-Null
& $iscc /Q "/DAppVersion=$Version" "/DStageDir=$stage" "/DOutputDir=$output" (Join-Path $here "pensieve.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed ($LASTEXITCODE)" }
$setup = Join-Path $output "PensieveSetup-$Version.exe"
Write-Host ("`nBuilt {0} ({1:N0} MB)" -f $setup, ((Get-Item $setup).Length / 1MB)) -ForegroundColor Green
