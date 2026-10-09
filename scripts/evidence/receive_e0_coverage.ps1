param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^/raid/vrcelestino/data/cfl-mvp2-evidence/e0/coverage-[A-Za-z0-9]+$')]
    [string]$RemoteDirectory,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$ExpectedSha256,
    [string]$OutputRoot = (Join-Path $PSScriptRoot '../../outputs')
)
$ErrorActionPreference = 'Stop'
$destination = Join-Path $OutputRoot ('e0-coverage-' + $ExpectedSha256.Substring(0,12))
if (Test-Path -LiteralPath $destination) { throw 'Preserve existing download; do not overwrite.' }
$null = New-Item -ItemType Directory -Path $destination
$receipt = Join-Path $destination 'coverage.json'
# One file, one SSH connection, normally one password prompt. No remote command.
& scp "vrcelestino@dgx-dasci.ujaen.es:${RemoteDirectory}/coverage.json" $receipt
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed. Preserve directory.' }
$actual = (Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedSha256) { throw 'Receipt hash mismatch. Preserve downloaded bytes.' }
& python -B (Join-Path $PSScriptRoot 'reconcile_e0_coverage.py') review `
    --receipt $receipt --expected-sha256 $ExpectedSha256 `
    --output-directory (Join-Path $destination 'review')
if ($LASTEXITCODE -ne 0) { throw 'Offline reconciliation failed. Preserve output.' }
Write-Host "E0_DOWNLOAD_HASH_AND_RECONCILIATION_OK: $destination"
Write-Host 'Return this directory and the HPC receipt. No solver, training, retry or merge.'
