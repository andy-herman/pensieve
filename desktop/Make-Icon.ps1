<#
.SYNOPSIS
Regenerates desktop\pensieve.ico (and frontend-proto\favicon.ico) from desktop\pensieve-icon.svg.

.DESCRIPTION
Renders the SVG to a 512px PNG with headless Microsoft Edge, then downsamples
it with System.Drawing into a multi-size ICO (16 to 256 px, PNG-compressed
entries). No Python packages needed. Only rerun this after editing the SVG;
the generated .ico files are committed.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here "..")).Path
$svg = Join-Path $here "pensieve-icon.svg"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("pensieve-icon-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$png = Join-Path $tmp "icon512.png"

$edge = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw "Microsoft Edge not found; it is used to rasterize the SVG." }

& $edge --headless=new --disable-gpu --hide-scrollbars --default-background-color=00000000 `
    --window-size=512,512 "--screenshot=$png" "--user-data-dir=$tmp\profile" ([Uri]$svg).AbsoluteUri 2>&1 | Out-Null
for ($i = 0; $i -lt 20 -and -not (Test-Path $png); $i++) { Start-Sleep -Milliseconds 250 }
if (-not (Test-Path $png)) { throw "Edge did not produce $png" }

$src = [System.Drawing.Image]::FromFile($png)
$sizes = 256, 128, 64, 48, 32, 24, 16
$images = @()
foreach ($s in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap($s, $s, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $g.DrawImage($src, 0, 0, $s, $s)
    $g.Dispose()
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    $images += , @{ Size = $s; Bytes = $ms.ToArray() }
    $ms.Dispose()
}
$src.Dispose()

function Write-Ico([string]$path) {
    $fs = [System.IO.File]::Create($path)
    $bw = New-Object System.IO.BinaryWriter($fs)
    $bw.Write([UInt16]0); $bw.Write([UInt16]1); $bw.Write([UInt16]$images.Count)
    $offset = 6 + 16 * $images.Count
    foreach ($img in $images) {
        $dim = if ($img.Size -ge 256) { 0 } else { $img.Size }
        $bw.Write([byte]$dim); $bw.Write([byte]$dim); $bw.Write([byte]0); $bw.Write([byte]0)
        $bw.Write([UInt16]1); $bw.Write([UInt16]32)
        $bw.Write([UInt32]$img.Bytes.Length); $bw.Write([UInt32]$offset)
        $offset += $img.Bytes.Length
    }
    foreach ($img in $images) { $bw.Write($img.Bytes) }
    $bw.Dispose()
}

Write-Ico (Join-Path $here "pensieve.ico")
Write-Ico (Join-Path $repo "frontend-proto\favicon.ico")
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Write-Host "Wrote desktop\pensieve.ico and frontend-proto\favicon.ico ($($sizes -join ', ') px)"
