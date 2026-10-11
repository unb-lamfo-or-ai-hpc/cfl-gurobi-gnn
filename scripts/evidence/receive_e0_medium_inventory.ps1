param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{12}$')][string]$StageSuffix,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$Download = Join-Path $RepoRoot ('outputs/e0-medium-inventory-' + $ExpectedSha256.Substring(0,12))
if (Test-Path -LiteralPath $Download) { throw 'Output exists; preserve it and report its path, do not download again.' }
New-Item -ItemType Directory -Path $Download | Out-Null
$Remote = '/raid/vrcelestino/data/cfl-mvp2-evidence/e0/medium-artifacts-' + $StageSuffix + '/run/inventory.json'
# One file, one SCP connection. Never transfer private_paths.json.
& scp ('vrcelestino@dgx-dasci.ujaen.es:' + $Remote) $Download
if ($LASTEXITCODE -ne 0) { throw 'Transfer incomplete; preserve directory.' }
$Receipt = Join-Path $Download 'inventory.json'
$Actual = (Get-FileHash -LiteralPath $Receipt -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $ExpectedSha256) { throw 'Receipt hash mismatch; preserve directory.' }
$Python = (Get-Command python -ErrorAction Stop).Source
& $Python -B (Join-Path $PSScriptRoot 'inventory_e0_medium.py') review --receipt $Receipt --expected-sha256 $ExpectedSha256
if ($LASTEXITCODE -ne 0) { throw 'Receipt scope validation failed; preserve directory.' }
Write-Host "E0_MEDIUM_INVENTORY_DOWNLOAD_OK: $Download"
Write-Host 'Return this directory and receipt hash. No solver, inference, training or retry.'
