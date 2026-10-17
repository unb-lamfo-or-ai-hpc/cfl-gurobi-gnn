param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceCommit,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReturnSha
)
$ErrorActionPreference = 'Stop'
$stage = '/raid/vrcelestino/data/cfl-mvp2-evidence/pr86/next-61-' + $SourceCommit.Substring(0,12)
$destination = Join-Path $PSScriptRoot ('../../outputs/pr86-next61-' + $ExpectedReturnSha.Substring(0,12))
if (Test-Path -LiteralPath $destination) {
    $destination += '-transfer-' + [guid]::NewGuid().ToString('N')
}
$null = New-Item -ItemType Directory -Path $destination
Write-Host "PR86_TRANSFER_DIRECTORY=$destination"
$receipt = Join-Path $destination 'public_return.json'
& scp -o ConnectionAttempts=1 -o ConnectTimeout=30 "vrcelestino@dgx-dasci.ujaen.es:${stage}/public_return.json" $receipt
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed; preserve output.' }
if ((Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedReturnSha) {
    throw 'Return hash mismatch; preserve output.'
}
$value = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if ($value.plan.source_commit -ne $SourceCommit) { throw 'Source commit mismatch.' }
& python -B (Join-Path $PSScriptRoot 'pr86_wave61.py') review --receipt $receipt
if ($LASTEXITCODE -ne 0) { throw 'Independent nested validation failed; preserve bytes.' }
Write-Host "PR86_NEXT_WAVE_RETURN_VERIFIED=$destination"
Write-Host 'Return receipt and directory. No retry, further submission or merge.'
