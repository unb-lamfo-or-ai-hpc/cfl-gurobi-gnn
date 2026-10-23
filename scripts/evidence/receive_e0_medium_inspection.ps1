param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{12}$')][string]$StageSuffix,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$Download = Join-Path $RepoRoot ('outputs/e0-medium-inspection-' + $ExpectedSha256.Substring(0,12))
if (Test-Path -LiteralPath $Download) { throw 'Output exists; preserve it and report its path.' }
New-Item -ItemType Directory -Path $Download | Out-Null
$Remote = '/raid/vrcelestino/data/cfl-mvp2-evidence/e0/medium-inspection-' + $StageSuffix + '/run/inspection.json'
& scp ('vrcelestino@dgx-dasci.ujaen.es:' + $Remote) $Download
if ($LASTEXITCODE -ne 0) { throw 'Transfer incomplete; preserve directory.' }
$Receipt = Join-Path $Download 'inspection.json'
$Actual = (Get-FileHash -LiteralPath $Receipt -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $ExpectedSha256) { throw 'Receipt hash mismatch; preserve directory.' }
$Python = (Get-Command python -ErrorAction Stop).Source
& $Python -B (Join-Path $PSScriptRoot 'inspect_e0_medium_artifacts.py') review --receipt $Receipt --expected-sha256 $ExpectedSha256
if ($LASTEXITCODE -ne 0) { throw 'Receipt scope validation failed; preserve directory.' }
Write-Host "E0_MEDIUM_INSPECTION_DOWNLOAD_OK: $Download"
Write-Host 'Return receipt and directory. No private bindings, solver, inference, training or retry.'
