param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{40}$')][string]$SourceCommit,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReturnSha
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$outputRoot = Join-Path $repoRoot 'outputs'
[void][IO.Directory]::CreateDirectory($outputRoot)
$destination = Join-Path $outputRoot ('pr87-training-' + $ExpectedReturnSha.Substring(0,12) + '-' + [guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($destination)
$remote = '/raid/vrcelestino/data/cfl-mvp2-evidence/pr87/training-' + $SourceCommit.Substring(0,12) + '/public_return.json'
Write-Host "PR87_DOWNLOAD_DIRECTORY=$destination"
# Exactly one SCP connection/file; credentials remain in the SSH client.
& scp "vrcelestino@dgx-dasci.ujaen.es:$remote" (Join-Path $destination 'public_return.json')
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed. Preserve this directory; no training retry.' }
$target = Join-Path $destination 'public_return.json'
$actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedReturnSha) { throw 'Return hash mismatch; preserve download.' }
& python -B (Join-Path $PSScriptRoot 'pr87_workflow.py') inspect --receipt $target --expected-sha256 $ExpectedReturnSha
if ($LASTEXITCODE -ne 0) { throw 'Incomplete/inconsistent pair. Preserve receipt for review; no resubmission.' }
Write-Host "PR87_DOWNLOAD_HASH_AND_ENVELOPE_OK=$destination"
Write-Host 'An intact failed receipt is preserved evidence, not a qualified complete training pair.'
Write-Host 'Return receipt and directory. No retry, new training, solver or merge.'
