param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$SourceCommit
)
$ErrorActionPreference = 'Stop'
$stage = '/raid/vrcelestino/data/cfl-mvp2-evidence/pr86/bindings-' + $SourceCommit.Substring(0,12)
$destination = Join-Path $PSScriptRoot ('../../outputs/pr86-bindings-' + $SourceCommit.Substring(0,12))
if (Test-Path -LiteralPath $destination) { throw 'Preserve existing download; do not repeat.' }
$null = New-Item -ItemType Directory -Path $destination
# One recursive transfer of the PUBLIC directory only: one SSH authentication.
& scp -r "vrcelestino@dgx-dasci.ujaen.es:${stage}/prepared/public" $destination
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed; preserve destination.' }
$public = Join-Path $destination 'public'
$names = @(Get-ChildItem -LiteralPath $public -Force | ForEach-Object { $_.Name })
if ($names.Count -ne 2 -or 'binding.json' -notin $names -or 'SHA256SUMS.txt' -notin $names) { throw 'Unexpected public members.' }
$line = (Get-Content -LiteralPath (Join-Path $public 'SHA256SUMS.txt') -Raw).Trim()
if ($line -notmatch '^([0-9a-f]{64})  binding\.json$') { throw 'Invalid checksum sidecar.' }
$expectedSha = $Matches[1]
$receipt = Join-Path $public 'binding.json'
if ((Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha) { throw 'Hash mismatch; preserve bytes.' }
$value = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if ($value.source_commit -ne $SourceCommit) { throw 'Source commit mismatch.' }
& python -B (Join-Path $PSScriptRoot 'bind_pr86_existing_starts.py') review --receipt $receipt --expected-sha256 $expectedSha
if ($LASTEXITCODE -ne 0) { throw 'Independent public-contract review failed; preserve bytes.' }
Write-Host "PR86_BINDING_DOWNLOAD_OK=$destination"
Write-Host "PR86_BINDING_SHA256=$expectedSha"
Write-Host 'Return the sanitized receipt. No job, solver, inference, training, retry or merge.'
