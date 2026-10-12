param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceCommit,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReturnSha
)
$ErrorActionPreference = 'Stop'
$stage = '/raid/vrcelestino/data/cfl-mvp2-evidence/pr86/guidance-' + $SourceCommit.Substring(0,12)
$destination = Join-Path $PSScriptRoot ('../../outputs/pr86-guidance-' + $ExpectedReturnSha.Substring(0,12))
if (Test-Path -LiteralPath $destination) { throw 'Preserve prior download; do not repeat.' }
$null = New-Item -ItemType Directory -Path $destination
$receipt = Join-Path $destination 'public_return.json'
& scp "vrcelestino@dgx-dasci.ujaen.es:${stage}/public_return.json" $receipt
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed; preserve output.' }
if ((Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedReturnSha) {
    throw 'Return hash mismatch; preserve output.'
}
$value = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if ($value.plan.source_commit -ne $SourceCommit) { throw 'Source commit mismatch.' }
& python -B (Join-Path $PSScriptRoot 'pr86_guidance_preparation.py') review --receipt $receipt
if ($LASTEXITCODE -ne 0) { throw 'Independent review failed; preserve bytes.' }
Write-Host "PR86_GUIDANCE_RETURN_VERIFIED=$destination"
Write-Host 'Return receipt and directory. No automatic retry, main comparison, training or merge.'
