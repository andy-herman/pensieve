# scripts/Test-AzureOpenAI.ps1
#
# Phase 0 sanity check #1: prove the Azure OpenAI call path works for
# Pensieve. Loads .env, calls the deployment with a trivial memory-
# enrichment prompt, verifies the response is well-formed JSON.
# Independent of Microsoft Graph and independent of the real
# enrichment prompt.
#
# Run from the repo root:
#   pwsh -File scripts\Test-AzureOpenAI.ps1

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib\Load-DotEnv.ps1')
. (Join-Path $PSScriptRoot 'lib\Invoke-AzureOpenAI.ps1')

Import-DotEnv -Verbose:$false

Write-Host "Pensieve - Azure OpenAI sanity check" -ForegroundColor Cyan
Write-Host "Endpoint:   $env:AZURE_OPENAI_ENDPOINT"
Write-Host "Deployment: $env:AZURE_OPENAI_DEPLOYMENT"
Write-Host "API ver:    $env:AZURE_OPENAI_API_VERSION"
$authMode = if ($env:AZURE_OPENAI_API_KEY -and $env:AZURE_OPENAI_API_KEY -ne 'REPLACE_WITH_KEY_FROM_AZURE_PORTAL') { 'api-key' } else { 'AAD (az login)' }
Write-Host "Auth mode:  $authMode"
Write-Host ""

$systemMsg = @{
    role = 'system'
    content = @'
You classify a single To-Do task into one strand archetype. Return ONLY a JSON
object with this exact shape:

{ "strand_kind": "<one of: deep, tactical, learning, writing, unknown>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one short sentence>" }

If confidence is below 0.6, set "strand_kind" to "unknown".
Do not use em-dashes in any text field.
'@
}
$userMsg = @{
    role = 'user'
    content = @"
Classify this To-Do task:

Title: Draft DORA Article 6 risk taxonomy
Notes: Need first cut by Friday for EU Reg lead
"@
}

Write-Host "Calling deployment..." -ForegroundColor Yellow
$start = Get-Date
$resp = Invoke-AzureOpenAIChat -Messages @($systemMsg, $userMsg) `
                               -MaxOutputTokens 200 `
                               -ResponseFormat 'json_object'
$elapsed = (Get-Date) - $start

$content = $resp.choices[0].message.content
$parsed  = $content | ConvertFrom-Json

Write-Host ""
Write-Host "[OK] Azure OpenAI responded in $([int]$elapsed.TotalMilliseconds) ms" -ForegroundColor Green
Write-Host "  strand_kind: $($parsed.strand_kind)"
Write-Host "  confidence:  $($parsed.confidence)"
Write-Host "  reasoning:   $($parsed.reasoning)"
Write-Host ""
Write-Host "Token usage: prompt=$($resp.usage.prompt_tokens) completion=$($resp.usage.completion_tokens) total=$($resp.usage.total_tokens)" -ForegroundColor DarkGray
