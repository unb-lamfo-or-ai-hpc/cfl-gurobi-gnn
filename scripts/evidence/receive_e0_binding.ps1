param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^/raid/vrcelestino/data/cfl-mvp2-evidence/e0/starts-[A-Za-z0-9]+/prepared$')]
    [string]$RemoteDirectory,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
$destination = Join-Path $PSScriptRoot ('../../outputs/e0-binding-' + $ExpectedSha256.Substring(0,12))
if (Test-Path -LiteralPath $destination) { throw 'Preserve existing download.' }
$null = New-Item -ItemType Directory -Path $destination
$receipt = Join-Path $destination 'binding.json'
& scp "vrcelestino@dgx-dasci.ujaen.es:${RemoteDirectory}/binding.json" $receipt
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed; preserve directory.' }
if ((Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedSha256) { throw 'Hash mismatch; preserve bytes.' }
& python -B (Join-Path $PSScriptRoot 'prepare_e0_easy_starts.py') review --receipt $receipt --expected-sha256 $ExpectedSha256
if ($LASTEXITCODE -ne 0) { throw 'Binding review failed; preserve output.' }
Write-Host "E0_BINDING_DOWNLOAD_OK: $destination"
