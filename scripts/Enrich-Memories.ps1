# scripts/Enrich-Memories.ps1
#
# *** LEGACY (Phase 0) — superseded by `pensieve sync` (Python CLI) on 2026-05-28. ***
# Kept for historical reference only; not maintained.
# See README.md, AGENTS.md, and pensieve/cli.py for the current path.
#
# Phase 0 main script. Reads To-Do tasks (canned samples in Phase 0;
# live Graph in Phase 1), runs each through Azure OpenAI using the
# Pensieve enrichment prompt, and emits a Memory record per task.
#
# STATUS: Phase 0 (dry-run mode) is functional. The Microsoft Graph
# integration path (real To-Do CRUD + Notes write-back) is stubbed
# because Microsoft's corp tenant Conditional Access blocks the
# built-in Microsoft.Graph PowerShell SDK app for `Tasks.ReadWrite`
# on Andy's account (mirrors the Inbox Copilot 2026-05-22 finding;
# verify with `az account get-access-token --resource https://graph.microsoft.com`
# before relying on the Azure CLI workaround).
#
# Three paths under evaluation to unblock the Graph side (see
# OPEN-QUESTIONS.md Q1):
#   1. Custom Entra app registration via Microsoft corp app-onboarding
#      process (long-term right answer, takes days for admin consent).
#   2. Azure CLI client minting Graph tokens, if `Tasks.ReadWrite` is
#      pre-consented for the Azure CLI client in Microsoft tenant.
#   3. Wait for built-in PS SDK app to be allow-listed (not viable).
#
# Until one of those resolves, use -DryRunSampleFile mode below.

[CmdletBinding()]
param(
    [string] $DryRunSampleFile = (Join-Path (Split-Path $PSScriptRoot -Parent) 'data\samples.json'),
    [string] $OutputJson,                              # optional path to write the enriched memories JSON
    [switch] $NoAudit                                  # if set, skip writing to data/audit-log.jsonl
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'lib\Load-DotEnv.ps1')
. (Join-Path $PSScriptRoot 'lib\Invoke-AzureOpenAI.ps1')

Import-DotEnv -Verbose:$false

$threshold = [double]($env:PENSIEVE_ENRICHMENT_CONFIDENCE_THRESHOLD ?? 0.5)
$dataDir   = $env:PENSIEVE_DATA_DIR ?? (Join-Path (Split-Path $PSScriptRoot -Parent) 'data')
$auditPath = Join-Path $dataDir 'audit-log.jsonl'

if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
}

$promptPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'prompts\enrich-memory-prompt.md'
if (-not (Test-Path $promptPath)) { throw "Prompt file not found at $promptPath" }
$systemPrompt = Get-Content $promptPath -Raw

$goalsPath = Join-Path $dataDir 'connect-goals.json'
$connectGoals = @()
if (Test-Path $goalsPath) {
    $goalsBlob = Get-Content $goalsPath -Raw | ConvertFrom-Json
    $connectGoals = @($goalsBlob.goals)
    Write-Host ("Loaded {0} Connect goals from connect-goals.json" -f $connectGoals.Count) -ForegroundColor DarkGray
} else {
    Write-Host "WARN: connect-goals.json not found at $goalsPath - Connect alignment will be empty." -ForegroundColor Yellow
}

function Write-Audit {
    param([hashtable] $Entry)
    if ($NoAudit) { return }
    $Entry.timestamp = (Get-Date).ToString('o')
    ($Entry | ConvertTo-Json -Compress -Depth 6) | Out-File -FilePath $auditPath -Append -Encoding utf8
}

function Invoke-Enrich {
    param(
        [hashtable] $Task,
        [array]     $StrandCatalog,
        [array]     $ConnectGoals,
        [hashtable] $RecentContext
    )

    $userPayload = @{
        task            = $Task
        strand_catalog  = $StrandCatalog
        connect_goals   = $ConnectGoals
        recent_context  = $RecentContext
    } | ConvertTo-Json -Depth 10 -Compress

    $messages = @(
        @{ role = 'system'; content = $systemPrompt },
        @{ role = 'user';   content = "Enrich this task into a Memory.`n`nINPUT:`n$userPayload" }
    )

    $resp    = Invoke-AzureOpenAIChat -Messages $messages -MaxOutputTokens 1500 -ResponseFormat 'json_object'
    $content = $resp.choices[0].message.content
    $parsed  = $content | ConvertFrom-Json

    return @{
        memory    = $parsed
        tokens    = $resp.usage.total_tokens
    }
}

# ---------------------------------------------------------------------
# Phase 0: dry-run against canned samples
# ---------------------------------------------------------------------

Write-Host "Pensieve - Phase 0 dry-run enrichment" -ForegroundColor Cyan
Write-Host "Samples:    $DryRunSampleFile"
Write-Host "Prompt:     $promptPath"
Write-Host "Threshold:  $threshold (memories below this go to review queue)"
Write-Host ""

if (-not (Test-Path $DryRunSampleFile)) {
    throw "Sample file not found: $DryRunSampleFile"
}

$payload = Get-Content $DryRunSampleFile -Raw | ConvertFrom-Json
$strandCatalog = $payload.strand_catalog
$recentContext = @{
    user_recent_strands         = $payload.recent_context.user_recent_strands
    recent_titles_in_same_list  = $payload.recent_context.recent_titles_in_same_list
}

if (-not $strandCatalog -or $strandCatalog.Count -eq 0) {
    throw "samples.json missing strand_catalog array"
}
if (-not $payload.tasks -or $payload.tasks.Count -eq 0) {
    throw "samples.json missing tasks array"
}

Write-Host ("Loaded {0} strands and {1} sample tasks." -f $strandCatalog.Count, $payload.tasks.Count) -ForegroundColor DarkGray
Write-Host ""

$enrichedMemories = @()
$failed           = 0
$reviewQueue      = 0
$totalTokens      = 0

foreach ($task in $payload.tasks) {
    $taskHash = @{
        id         = $task.id
        title      = $task.title
        notes      = $task.notes
        created_at = $task.created_at
        list_name  = $task.list_name
    }

    try {
        $result   = Invoke-Enrich -Task $taskHash -StrandCatalog $strandCatalog -ConnectGoals $connectGoals -RecentContext $recentContext
        $memory   = $result.memory
        $totalTokens += $result.tokens

        $strandConf = [double]$memory.confidence_strand
        $impactConf = [double]$memory.confidence_impact
        $alignConf  = [double]$memory.connect_alignment_confidence
        $needsReview = $strandConf -lt $threshold -or $impactConf -lt $threshold -or $memory.needs_human_strand_review -eq $true

        $strandDisplay = if ($memory.suggested_strand) {
            $hit = $strandCatalog | Where-Object { $_.id -eq $memory.suggested_strand } | Select-Object -First 1
            if ($hit) { $hit.display_name } else { "<unknown:$($memory.suggested_strand)>" }
        } else { "<unstranded>" }

        $goalDisplay = if ($memory.connect_goal_ids -and @($memory.connect_goal_ids).Count -gt 0) {
            $names = foreach ($gid in @($memory.connect_goal_ids)) {
                $g = $connectGoals | Where-Object { $_.id -eq $gid } | Select-Object -First 1
                if ($g) { "#$($g.number) $($g.short_name)" } else { "<unknown:$gid>" }
            }
            ($names -join ', ')
        } else { '<no Connect alignment>' }

        $marker = if ($needsReview) { "REVIEW" } else { "OK    " }
        $color  = if ($needsReview) { 'Yellow' } else { 'Green' }
        Write-Host ("[{0}] {1,-26} (s={2,4:N2} i={3,4:N2} a={4,4:N2}) {5}" -f $marker, $strandDisplay, $strandConf, $impactConf, $alignConf, $task.title) -ForegroundColor $color
        Write-Host ("    why:    {0}" -f $memory.why) -ForegroundColor DarkGray
        Write-Host ("    impact: {0}" -f $memory.impact) -ForegroundColor DarkGray
        Write-Host ("    goals:  {0}" -f $goalDisplay) -ForegroundColor DarkCyan
        if ($memory.connect_alignment_note) {
            Write-Host ("    align:  {0}" -f $memory.connect_alignment_note) -ForegroundColor DarkCyan
        }
        if ($memory.notes_for_user) {
            Write-Host ("    note:   {0}" -f $memory.notes_for_user) -ForegroundColor DarkYellow
        }

        if ($needsReview) { $reviewQueue++ }
        $enrichedMemories += $memory
        Write-Audit @{ mode = 'dry-run'; task_id = $task.id; memory = $memory; tokens = $result.tokens }
    } catch {
        $failed++
        Write-Host "[FAIL ] $($task.title) -- $($_.Exception.Message)" -ForegroundColor Red
        Write-Audit @{ mode = 'dry-run'; task_id = $task.id; error = $_.Exception.Message }
    }
}

Write-Host ""
Write-Host ("Done. {0} enriched, {1} in review queue, {2} failed. Tokens used: {3}." -f $enrichedMemories.Count, $reviewQueue, $failed, $totalTokens) -ForegroundColor Cyan

if ($OutputJson) {
    $enrichedMemories | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutputJson -Encoding utf8
    Write-Host "Wrote enriched memories to $OutputJson" -ForegroundColor Cyan
}
