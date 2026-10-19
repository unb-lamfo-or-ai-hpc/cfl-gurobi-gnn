param(
    [Parameter(Mandatory=$true)][ValidatePattern('^/raid/vrcelestino/data/cfl-mvp2-evidence/pr86/numeric-m12-[0-9a-f]{12}$')][string]$RemoteDirectory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReceiptSha,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedCollectorCommit
)
$ErrorActionPreference = 'Stop'
$destination = Join-Path $PSScriptRoot ('../../outputs/pr86-m12-numeric-' + $ExpectedReceiptSha.Substring(0,12))
if (Test-Path -LiteralPath $destination) { $destination += '-transfer-' + [guid]::NewGuid().ToString('N') }
$null = New-Item -ItemType Directory -Path $destination
Write-Host "PR86_TRANSFER_DIRECTORY=$destination"
$receipt = Join-Path $destination 'numeric_audit.json'
& scp -o ConnectionAttempts=1 -o ConnectTimeout=30 "vrcelestino@dgx-dasci.ujaen.es:${RemoteDirectory}/numeric_audit.json" $receipt
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed; preserve output. No automatic retry.' }
if ((Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedReceiptSha) { throw 'Receipt hash mismatch; preserve output.' }
& python -B (Join-Path $PSScriptRoot 'audit_pr86_wave61_numeric.py') `
    --receipt $receipt --expected-sha256 $ExpectedReceiptSha --collector-commit $ExpectedCollectorCommit
if ($LASTEXITCODE -ne 0) { throw 'Independent numeric receipt binding failed; preserve output.' }
Write-Host "PR86_M12_NUMERIC_DOWNLOAD_HASH_AND_SCOPE_OK=$destination"
Write-Host "RECEIPT_SHA256=$ExpectedReceiptSha"
Write-Host 'Return sanitized receipt/hash/directory. No optimization, parameter change, further submission or merge.'
