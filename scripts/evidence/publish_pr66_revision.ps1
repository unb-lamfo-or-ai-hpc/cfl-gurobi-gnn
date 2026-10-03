# SPDX-License-Identifier: MIT
# Update the existing draft through GitHub's Git Data API, preserving remote history.
[CmdletBinding()]
param([switch] $CheckOnly)
$ErrorActionPreference = 'Stop'
$Repository = 'unb-lamfo-or-ai-hpc/cfl-gurobi-gnn'
$Branch = 'feature/pr66-reconciliation-thread-pilot'
$Baseline = '5d4e675af6ece1fa229a167f3b1f776eba7081c3'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$Utf8 = New-Object System.Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'pr66_git_read.ps1')
function Git-Text([string[]] $GitArguments) {
    return (Invoke-Pr66GitRead -Repository $Root -GitArguments $GitArguments).TrimEnd("`r", "`n")
}
function Git-Blob([string] $Revision, [string] $Name) {
    if ($Name -notmatch '^[A-Za-z0-9_./-]+$') { throw 'Unsupported publication path' }
    return Invoke-Pr66GitRead -Repository $Root -GitArguments @('cat-file', 'blob', "${Revision}:$Name")
}
if ((Git-Text @('branch', '--show-current')) -ne $Branch) { throw 'Wrong local branch' }
if (Git-Text @('status', '--porcelain')) { throw 'Commit/review local changes before publication' }
$Source = Git-Text @('rev-parse', 'HEAD')
$null = Git-Blob $Source 'configs/experiments/pr66_thread_screen_v1.json'
$null = Git-Blob $Baseline 'configs/experiments/pr66_thread_screen_v1.json'
& python -m ruff check --config "$Root/configs/quality/pr64-ruff.toml" "$Root/scripts/evidence" "$Root/tests/evidence"
if ($LASTEXITCODE -ne 0) { throw 'Ruff check failed' }
& python -m ruff format --check --config "$Root/configs/quality/pr64-ruff.toml" "$Root/scripts/evidence" "$Root/tests/evidence"
if ($LASTEXITCODE -ne 0) { throw 'Ruff format check failed' }
Push-Location $Root
try {
    & python -m unittest discover -s tests/evidence
    if ($LASTEXITCODE -ne 0) { throw 'Evidence tests failed' }
} finally { Pop-Location }
if ($CheckOnly) {
    Write-Output 'PR66_PUBLISHER_LOCAL_CHECKS_OK_NO_GITHUB_WRITE'
    return
}
$ReceiptRoot = Join-Path (Split-Path (Split-Path $Root -Parent) -Parent) 'output/pr66'
$Operation = Join-Path $ReceiptRoot ('publication-' + [Guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($Operation) | Out-Null
function Api([string] $Endpoint, [string] $Method = 'GET', $Payload = $null) {
    $ApiArguments = @('api', $Endpoint, '--method', $Method)
    if ($null -ne $Payload) {
        $InputPath = Join-Path $Operation 'request.json'
        [System.IO.File]::WriteAllText($InputPath, ($Payload | ConvertTo-Json -Depth 100), $Utf8)
        $ApiArguments += @('--input', $InputPath)
    }
    $reply = & gh @ApiArguments
    if ($LASTEXITCODE -ne 0) { throw 'GitHub API failed; inspect the remote before retrying' }
    return (($reply -join "`n") | ConvertFrom-Json)
}
$Account = Api 'user'
Write-Output "GITHUB_ACCOUNT=$($Account.login)"
$Pr = Api "repos/$Repository/pulls/66"
if ($Pr.state -ne 'open' -or !$Pr.draft -or $Pr.base.ref -ne 'develop' -or $Pr.head.ref -ne $Branch -or $Pr.head.repo.full_name -ne $Repository) {
    throw 'Existing PR66 must be an open canonical draft into develop'
}
$Head = $Pr.head.sha
$PreviousReceiptPath = Join-Path $ReceiptRoot 'publication_receipt.json'
if (Test-Path -LiteralPath $PreviousReceiptPath) {
    $Previous = Get-Content -LiteralPath $PreviousReceiptPath -Raw | ConvertFrom-Json
    if ($Previous.pull_request -ne "https://github.com/$Repository/pull/66" -or $Previous.base -ne 'develop' -or !$Previous.draft -or
        $Previous.source_commit -notmatch '^[0-9a-f]{40}$' -or $Previous.local_candidate -notmatch '^[0-9a-f]{40}$') {
        throw 'Invalid previous publication receipt; preserve it for review'
    }
    if ($Previous.source_commit -ne $Head) {
        throw 'Remote differs from the last verified publication; inspect before retrying'
    }
    $Baseline = Git-Text @('rev-parse', $Previous.local_candidate)
    if ($Baseline -ne $Previous.local_candidate) { throw 'Previous local candidate unavailable' }
    Write-Output "PR66_INCREMENTAL_BASELINE=$Baseline"
}
$Tree = Api "repos/$Repository/git/trees/${Head}?recursive=1"
if ($Tree.truncated) { throw 'Truncated tree inventory' }
$Remote = @{}
foreach ($entry in $Tree.tree) { if ($entry.type -eq 'blob') { $Remote[$entry.path] = $entry.sha } }
$OldNames = (Git-Text @('ls-tree', '-r', '--name-only', $Baseline)) -split "`n"
$Names = (Git-Text @('diff', '--name-only', $Baseline, $Source)) -split "`n"
$Changes = @()
foreach ($Name in $Names) {
    if (!$Name) { continue }
    $NewText = Git-Blob $Source $Name
    $CurrentText = $null
    if ($Remote.ContainsKey($Name)) {
        $blob = Api "repos/$Repository/git/blobs/$($Remote[$Name])"
        $CurrentText = $Utf8.GetString([Convert]::FromBase64String(($blob.content -replace '\s', '')))
        if ($CurrentText -ceq $NewText) { continue }
    }
    if ($Name -in $OldNames) {
        $OldText = Git-Blob $Baseline $Name
        if ($null -eq $CurrentText -or $CurrentText.Replace("`r`n", "`n") -cne $OldText.Replace("`r`n", "`n")) {
            throw "Remote content conflict: $Name; no ref update performed"
        }
    } elseif ($null -ne $CurrentText) {
        throw "Remote added-file conflict: $Name; no ref update performed"
    }
    $Changes += @{ path = $Name; mode = '100644'; type = 'blob'; content = $NewText }
}
$Published = $Head
if ($Changes.Count -gt 0) {
    $NewTree = Api "repos/$Repository/git/trees" 'POST' @{ base_tree = $Tree.sha; tree = $Changes }
    $Commit = Api "repos/$Repository/git/commits" 'POST' @{
        message = 'Qualify PR66 default-algorithm thread screen and DaSCI hand-off'
        tree = $NewTree.sha; parents = @($Head)
    }
    $Fresh = Api "repos/$Repository/git/ref/heads/$Branch"
    if ($Fresh.object.sha -ne $Head) { throw 'Remote advanced during preparation; no ref update performed' }
    # Non-force update: a concurrent non-ancestor update is rejected by GitHub.
    $Updated = Api "repos/$Repository/git/refs/heads/$Branch" 'PATCH' @{ sha = $Commit.sha; force = $false }
    if ($Updated.object.sha -ne $Commit.sha) { throw 'Remote update not confirmed' }
    $Published = $Commit.sha
}
$Final = Api "repos/$Repository/pulls/66"
if ($Final.head.sha -ne $Published -or $Final.base.ref -ne 'develop' -or !$Final.draft) {
    throw 'Final PR snapshot differs; inspect before further action'
}
$BeginMarker = '<!-- PR66_DEFAULTS_V2_BEGIN -->'
$EndMarker = '<!-- PR66_DEFAULTS_V2_END -->'
$RevisionNotes = @"
$BeginMarker
## Approved defaults-v2 amendment

Restore all Gurobi 13.0.1 model parameters to version defaults before each run.
Do not force Barrier, NodeMethod, Crossover, presolve or heuristics. Threads alone
varies between arms; seed 42, 300-second budget, 10% gap and a common memory guard
remain fixed. One shared dgx-dasci job reserves sixteen physical cores and 64 GiB,
with ten fresh serial attempts on the frozen easy/medium fitting-parent pair.

Adds a licensed read-only preflight, pinned installation, private algorithm logs,
allowlisted receipt packaging with hash/read-back/sanitization checks, and a CLI
runbook. Historical reconciliation remains qualification foundations, not complete
incumbent totals or historical cost certification. The earlier barrier draft is
superseded and was not executed.

Local evidence tests: 124 passed on Python 3.10 and 3.13. Scoped Ruff check/format,
Bash/PowerShell syntax and diff checks passed. Real licensed execution and physical
affinity qualification remain pending on DaSCI. Preserve draft into develop.
No merge, main/Pages update, training, HPC submission or Zenodo upload is included.

The PR57 role-plan pin is its recomputed canonical contract, not the JSON file
digest. Verify the declared/recomputed/expected contract and the 54-parent roles
before freezing; bind stored JSON bytes separately. Retain the failed preflight.
$EndMarker
"@
$Body = [string]$Final.body
$Pattern = '(?s)<!-- PR66_DEFAULTS_V2_BEGIN -->.*?<!-- PR66_DEFAULTS_V2_END -->\s*'
$Body = [regex]::Replace($Body, $Pattern, '')
$UpdatedPr = Api "repos/$Repository/pulls/66" 'PATCH' @{ body = ($RevisionNotes + "`n`n" + $Body) }
if ($UpdatedPr.head.sha -ne $Published -or $UpdatedPr.base.ref -ne 'develop' -or !$UpdatedPr.draft) {
    throw 'Updated PR metadata differs; inspect before further action'
}
$Receipt = @{ source_commit = $Published; local_candidate = $Source; pull_request = $Final.html_url;
    base = 'develop'; draft = $true; hpc_submission = $false; main_updated = $false }
[System.IO.File]::WriteAllText((Join-Path $ReceiptRoot 'publication_receipt.json'), ($Receipt | ConvertTo-Json), $Utf8)
Write-Output "PR66_DRAFT_UPDATE_VERIFIED=$($Final.html_url)"
Write-Output "SOURCE_COMMIT=$Published"
Write-Output 'NO_MERGE_NO_MAIN_UPDATE_NO_HPC_SUBMISSION_NO_ZENODO_UPLOAD'
