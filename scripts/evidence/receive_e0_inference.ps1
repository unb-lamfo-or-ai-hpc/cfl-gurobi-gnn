param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^/raid/vrcelestino/data/cfl-mvp2-evidence/e0/inference-[A-Za-z0-9]+$')]
    [string]$RemoteDirectory,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
$destination = Join-Path $PSScriptRoot ('../../outputs/e0-inference-' + $ExpectedSha256.Substring(0,12))
if (Test-Path -LiteralPath $destination) { throw 'Preserve existing download.' }
$null = New-Item -ItemType Directory -Path $destination
$receipt = Join-Path $destination 'public_return.json'
& scp "vrcelestino@dgx-dasci.ujaen.es:${RemoteDirectory}/public_return.json" $receipt
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed; preserve directory.' }
if ((Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedSha256) {
    throw 'Hash mismatch; preserve downloaded bytes.'
}
Write-Host "E0_DOWNLOAD_HASH_OK: $destination"
& python -B (Join-Path $PSScriptRoot 'e0_frozen_inference.py') review `
    --receipt $receipt --expected-sha256 $ExpectedSha256 --output (Join-Path $destination 'review')
if ($LASTEXITCODE -eq 3) {
    Write-Warning "E0_INCOMPLETE_RETURN_PRESERVED: $destination. Share for diagnosis; do not resubmit."
    return
}
if ($LASTEXITCODE -ne 0) { throw 'Inconsistent return. Share directory for review; no retry.' }
Write-Host "E0_FROZEN_TEST_RETURN_OK: $destination"
