param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceCommit,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReturnSha,
    [ValidateRange(1,60)][int]$SubmittedCells = 60
)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$Output = Join-Path $Root ('outputs/pr89-cpu-' + $ExpectedReturnSha.Substring(0,12) + '-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Output | Out-Null
$Remote = '/raid/vrcelestino/data/cfl-mvp2-evidence/pr89/cpu12h-' + $SourceCommit.Substring(0,12) + ('/return-{0:d2}.json' -f $SubmittedCells)
Write-Host "PR89_DOWNLOAD_DIRECTORY=$Output"
# One transfer / one SSH authentication. Never password per evidence member.
& scp -- ('vrcelestino@dgx-dasci.ujaen.es:' + $Remote) (Join-Path $Output 'public_return.json')
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed. Preserve this directory; no automatic retry.' }
$Receipt = Join-Path $Output 'public_return.json'
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Receipt).Hash.ToLowerInvariant() -ne $ExpectedReturnSha) {
    throw 'Return hash mismatch. Preserve output; no solver retry.'
}
& python -B (Join-Path $PSScriptRoot 'pr89_cpu_workflow.py') review --receipt $Receipt --expected-sha256 $ExpectedReturnSha
if ($LASTEXITCODE -ne 0) { throw 'Nested review failed; preserve output and share this directory.' }
Write-Host "PR89_TRANSFER_AND_NESTED_REVIEW_OK=$Output"
Write-Host 'Return receipt and directory. No retry, new solve, training, or merge.'
