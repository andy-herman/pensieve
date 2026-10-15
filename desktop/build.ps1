<#
.SYNOPSIS
Builds desktop\dist\Pensieve.exe and (by default) adds Desktop and Start menu shortcuts.

.DESCRIPTION
Compiles Pensieve.cs with the .NET Framework C# compiler that ships with
Windows (no SDK, Rust, or Node needed). The repo path is baked into the exe
as a fallback, so the exe keeps working if it is copied elsewhere. Rerun
after moving the repo.

.PARAMETER NoShortcuts
Build only; do not create or update the Desktop / Start menu shortcuts.
#>
[CmdletBinding()]
param(
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here "..")).Path
$dist = Join-Path $here "dist"
$obj = Join-Path $here "obj"
New-Item -ItemType Directory -Force -Path $dist, $obj | Out-Null

$csc = @(
    "$env:WINDIR\Microsoft.NET\FrameworkArm64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $csc) { throw "No .NET Framework C# compiler (csc.exe) found under $env:WINDIR\Microsoft.NET." }

# Bake the repo path into the source as a C# string literal.
$source = Get-Content -Raw (Join-Path $here "Pensieve.cs")
$source = $source.Replace("@@REPO_ROOT@@", $repo.Replace("\", "\\"))
$generated = Join-Path $obj "Pensieve.generated.cs"
Set-Content -Path $generated -Value $source -Encoding UTF8

$exe = Join-Path $dist "Pensieve.exe"
$icon = Join-Path $here "pensieve.ico"
& $csc /nologo /target:winexe /platform:anycpu /optimize+ `
    "/win32icon:$icon" `
    /reference:System.Management.dll /reference:System.Windows.Forms.dll `
    "/out:$exe" $generated
if ($LASTEXITCODE -ne 0) { throw "csc failed with exit code $LASTEXITCODE" }
Write-Host "Built $exe"

if ($NoShortcuts) { return }

$shell = New-Object -ComObject WScript.Shell
$targets = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Pensieve.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "Pensieve.lnk")
)
foreach ($lnkPath in $targets) {
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = $exe
    $lnk.WorkingDirectory = $repo
    $lnk.IconLocation = "$exe,0"
    $lnk.Description = "Pensieve - your work memories, in a bowl"
    $lnk.Save()
    Write-Host "Shortcut: $lnkPath"
}
