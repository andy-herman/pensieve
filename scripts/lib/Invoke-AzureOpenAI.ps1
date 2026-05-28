# scripts/lib/Invoke-AzureOpenAI.ps1
#
# *** LEGACY (Phase 0) — ported into pensieve/enrichment/llm_client.py on 2026-05-28. ***
# Kept for historical reference only; not maintained.
#
# Thin wrapper around the Azure OpenAI chat-completions REST endpoint.
# Mirrors Argus's `_ClientShim` behavior:
#   - Routes max_tokens -> max_completion_tokens for gpt-5+/o1+/o3+/o4+
#   - Omits temperature (some GPT-5 deployments reject non-default values)
#   - Supports BOTH api-key auth and AAD bearer auth (key wins if set)
#
# Returns the raw OpenAI response object (parsed JSON). The caller is
# responsible for extracting `.choices[0].message.content`.
#
# Lifted verbatim from Inbox Copilot 2026-05-28 per Pensieve's tech-stack
# inheritance decision (SPEC.md section 11).

function Test-IsMaxCompletionTokensModel {
    param([string] $Deployment)
    $name = ($Deployment ?? '').ToLower()
    return ($name -like 'gpt-5*' -or
            $name -like 'o1*'    -or
            $name -like 'o3*'    -or
            $name -like 'o4*')
}

function Get-AzureOpenAIToken {
    # AAD path: shells out to `az account get-access-token`. Requires
    # the caller to have run `az login` once.
    param([string] $TokenScope = 'https://ai.azure.com/.default')

    $resource = $TokenScope -replace '/\.default$', ''
    $raw = az account get-access-token --resource $resource 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        throw "az account get-access-token failed. Run 'az login' first, or set AZURE_OPENAI_API_KEY in .env."
    }
    return ($raw | ConvertFrom-Json).accessToken
}

function Invoke-AzureOpenAIChat {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [array] $Messages,

        [int]    $MaxOutputTokens = 800,
        [string] $ResponseFormat  = $null,  # set to 'json_object' for structured output
        [int]    $TimeoutSeconds  = 60
    )

    $endpoint   = $env:AZURE_OPENAI_ENDPOINT
    $deployment = $env:AZURE_OPENAI_DEPLOYMENT
    $apiVersion = $env:AZURE_OPENAI_API_VERSION
    $apiKey     = $env:AZURE_OPENAI_API_KEY
    $tokenScope = if ($env:AZURE_OPENAI_TOKEN_SCOPE) { $env:AZURE_OPENAI_TOKEN_SCOPE } else { 'https://ai.azure.com/.default' }

    if (-not $endpoint)   { throw "AZURE_OPENAI_ENDPOINT not set in .env" }
    if (-not $deployment) { throw "AZURE_OPENAI_DEPLOYMENT not set in .env" }
    if (-not $apiVersion) { throw "AZURE_OPENAI_API_VERSION not set in .env" }

    $endpoint = $endpoint.TrimEnd('/')
    $url = "$endpoint/openai/deployments/$deployment/chat/completions?api-version=$apiVersion"

    $headers = @{ 'Content-Type' = 'application/json' }
    if ($apiKey -and $apiKey -ne 'REPLACE_WITH_KEY_FROM_AZURE_PORTAL') {
        $headers['api-key'] = $apiKey
    } else {
        $token = Get-AzureOpenAIToken -TokenScope $tokenScope
        $headers['Authorization'] = "Bearer $token"
    }

    $body = [ordered]@{ messages = $Messages }
    if (Test-IsMaxCompletionTokensModel -Deployment $deployment) {
        $body.max_completion_tokens = $MaxOutputTokens
    } else {
        $body.max_tokens = $MaxOutputTokens
    }
    if ($ResponseFormat) {
        $body.response_format = @{ type = $ResponseFormat }
    }

    $jsonBody = $body | ConvertTo-Json -Depth 10 -Compress

    try {
        $response = Invoke-RestMethod -Uri $url `
                                      -Method Post `
                                      -Headers $headers `
                                      -Body $jsonBody `
                                      -TimeoutSec $TimeoutSeconds `
                                      -ErrorAction Stop
        return $response
    } catch {
        $detail = $_.Exception.Message
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            $detail += " :: " + $_.ErrorDetails.Message
        }
        throw "Azure OpenAI call failed: $detail"
    }
}
