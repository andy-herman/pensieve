# scripts/lib/Load-DotEnv.ps1
#
# *** LEGACY (Phase 0) — replaced by python-dotenv via pydantic-settings on 2026-05-28. ***
# Kept for historical reference only; not maintained.
#
# Tiny .env loader. Mirrors python-dotenv semantics enough for our needs:
#   - lines starting with `#` are comments
#   - blank lines ignored
#   - `KEY=VALUE` parsed; surrounding whitespace trimmed
#   - quoted values ("..." or '...') have quotes stripped
#   - values may NOT contain `${VAR}` expansion (we don't need it)
#
# Sets variables on $env:* (process scope) so children inherit.
#
# Lifted verbatim from Inbox Copilot 2026-05-28 per Pensieve's tech-stack
# inheritance decision (SPEC.md section 11).

function Import-DotEnv {
    [CmdletBinding()]
    param(
        [string] $Path = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) '.env')
    )

    if (-not (Test-Path $Path)) {
        Write-Warning "No .env file found at $Path. Copy .env.example to .env and fill in values."
        return
    }

    $count = 0
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }

        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { return }

        $key   = $line.Substring(0, $eq).Trim()
        $value = $line.Substring($eq + 1).Trim()

        if ($value.Length -ge 2) {
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        Set-Item -Path "Env:$key" -Value $value
        $count++
    }

    Write-Verbose "Loaded $count environment variables from $Path"
}
