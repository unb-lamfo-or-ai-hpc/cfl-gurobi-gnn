# Workstation handoff: install in the task's outputs directory, alongside the
# frozen validator checkout at ../work/pr78-mvp2-delivery-plan (head 173b63d).
# Never store the SSH password; the OpenSSH client owns its interactive prompt.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('easy','medium')][string]$Parent,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReturnSha,
    [string]$DownloadRoot = $PSScriptRoot
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$TaskRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $TaskRoot 'work/pr78-mvp2-delivery-plan'
$Validator = Join-Path $Source 'scripts/evidence/paired_matrix_workflow_v2.py'
$Python = 'C:/Users/cvict/miniconda3/python.exe'
$Head = & git -C $Source rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $Head.Trim() -ne '173b63d62658731678357772fa2d3bba48f9bc81') {
    throw 'Wrong local validator source; preserve checkout.'
}
$Dirty = & git -C $Source status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0 -or $Dirty) { throw 'Local validator checkout is dirty.' }
if ((Get-FileHash -LiteralPath $Validator -Algorithm SHA256).Hash.ToLowerInvariant() -ne '787efe0a98f353ac7957173f5284769bd4d0a1a8a80c191e8097890e1cd3df56') {
    throw 'Validator dependency pin mismatch.'
}
$RemoteDirectory = "/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/recovery-job3481-v2/flow/return-$Parent"
$Destination = Join-Path ([System.IO.Path]::GetFullPath($DownloadRoot)) ("pr78-recovery-" + $Parent + "-" + $ExpectedReturnSha.Substring(0,12))
if (Test-Path -LiteralPath $Destination) { throw 'Destination exists: preserve it; no automatic retry or overwrite.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
# One connection for the complete fixed public allowlist, not one per file.
# BatchMode=no permits OpenSSH's own password prompt; no password is captured.
# The optional archive may be absent for a failed job. Validation below still
# rejects a missing declared archive, unexpected files, or any hash mismatch.
$BatchPath = Join-Path $PSScriptRoot ("pr78-sftp-" + [guid]::NewGuid().ToString('N') + '.batch')
$SftpDestination = $Destination.Replace('\','/')
if ($SftpDestination -match '["\r\n\[\]*?]') { throw 'Unsupported SFTP destination characters.' }
$Batch = @(
    ('lcd "' + $SftpDestination + '"'),
    ('cd "' + $RemoteDirectory + '"'),
    'get SHA256SUMS.txt',
    'get accounting.json',
    'get operator_approval.json',
    'get operator_plan.json',
    'get submission.json',
    '-get matrix.tar.gz',
    'bye'
)
[System.IO.File]::WriteAllLines($BatchPath, $Batch, [System.Text.UTF8Encoding]::new($false))
& sftp -o BatchMode=no -o NumberOfPasswordPrompts=1 -b $BatchPath 'vrcelestino@dgx-dasci.ujaen.es'
if ($LASTEXITCODE -ne 0) { throw 'SFTP transfer failed: preserve partial directory; no automatic retry.' }
$Manifest = Join-Path $Destination 'SHA256SUMS.txt'
if ((Get-FileHash -LiteralPath $Manifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedReturnSha) { throw 'Return SHA mismatch.' }
$Names = @()
foreach ($Line in (Get-Content -LiteralPath $Manifest)) {
    if ($Line -cnotmatch '^[0-9a-f]{64}  (accounting.json|operator_approval.json|operator_plan.json|submission.json|matrix.tar.gz)$') {
        throw 'Unexpected manifest member; no private or raw-log download permitted.'
    }
    $Name = $Matches[1]
    if ($Names -contains $Name) { throw 'Duplicate manifest member.' }
    $Names += $Name
}
foreach ($Required in @('accounting.json','operator_approval.json','operator_plan.json','submission.json')) {
    if ($Names -notcontains $Required) { throw 'Missing public receipt member.' }
}
$ActualNames = @(Get-ChildItem -LiteralPath $Destination -Force | ForEach-Object { $_.Name })
$ExpectedNames = @('SHA256SUMS.txt') + $Names
if (Compare-Object $ExpectedNames $ActualNames) { throw 'Downloaded member set differs from manifest.' }
& $Python -B $Validator validate-return --directory $Destination --expected-sha $ExpectedReturnSha
if ($LASTEXITCODE -ne 0) { throw 'Nested contract validation failed; preserve evidence; no medium submission.' }
$Accounting = Get-Content -Raw -LiteralPath (Join-Path $Destination 'accounting.json') | ConvertFrom-Json
if ($Accounting.parent -ne $Parent) { throw 'Unexpected parent in return.' }
Write-Host "PR78_RECOVERY_DOWNLOAD_HASH_AND_NESTED_CONTRACT_OK: $Destination"
Write-Host "READY_FOR_INDEPENDENT_REVIEW=$($Accounting.ready_for_independent_review)"
Write-Host 'Return this directory and collection receipt. No raw logs, automatic retry or medium submission.'
