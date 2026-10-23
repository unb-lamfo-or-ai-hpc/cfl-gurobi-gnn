param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/integrated-[0-9a-f]{12}$')]
    [string]$StageDirectory,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$ExpectedReturnSha,
    [string]$OutputRoot = (Join-Path $PSScriptRoot '../../../../outputs')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Destination = Join-Path $OutputRoot ('pr80-integrated-' + $ExpectedReturnSha.Substring(0,12))
if (Test-Path -LiteralPath $Destination) { throw "Preserve existing directory: $Destination" }
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$Target = Join-Path $Destination 'public_return.json'
# A single file and a single SSH connection. No password is captured or stored.
& scp "vrcelestino@dgx-dasci.ujaen.es:${StageDirectory}/public_return.json" $Target
if ($LASTEXITCODE -ne 0) { throw "Transfer failed; preserve $Destination" }
$Actual = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -cne $ExpectedReturnSha) { throw "Outer hash mismatch; preserve $Destination" }
$Return = Get-Content -LiteralPath $Target -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Return.protocol_id -cne 'pr80_existing_runtime_integrated_v1' -or
    $Return.raw_logs_included -cne $false -or
    $Return.scientific_reporting_eligible -cne $false -or
    $Return.job_id -notmatch '^[0-9]+$') { throw 'Return scope mismatch' }
$Allowed = @('runtime.json','integrated.json','numeric/numeric.json','inference.json',
             'parent_statistics.csv','descriptive_statistics.csv')
$Sha = [Security.Cryptography.SHA256]::Create()
try {
    foreach ($Member in $Return.members.PSObject.Properties) {
        if ($Member.Name -cnotin $Allowed) { throw 'Unexpected return member' }
        $Bytes = [Text.Encoding]::UTF8.GetBytes([string]$Member.Value.text)
        $Hash = [BitConverter]::ToString($Sha.ComputeHash($Bytes)).Replace('-','').ToLowerInvariant()
        if ($Hash -cne $Member.Value.sha256) { throw "Member hash mismatch: $($Member.Name)" }
    }
} finally { $Sha.Dispose() }
$Names = @($Return.members.PSObject.Properties.Name)
$State = 'no_application_receipt'
if ('integrated.json' -cin $Names) {
    $Integrated = $Return.members.'integrated.json'.text | ConvertFrom-Json
    if ($Integrated.protocol_id -cne $Return.protocol_id -or
        $Integrated.job_id -cne $Return.job_id -or
        $Integrated.optimization_runs_added -ne 0 -or
        $Integrated.training_runs_added -ne 0 -or
        $Integrated.training_admitted -cne $false -or
        $Integrated.scientific_reporting_eligible -cne $false) { throw 'Integrated scope mismatch' }
    $State = $Integrated.state
    if ($State -ceq 'complete_pending_independent_review') {
        if ($Names.Count -ne $Allowed.Count) { throw 'Complete return lacks required members' }
        $Numeric = $Return.members.'numeric/numeric.json'.text | ConvertFrom-Json
        $Inference = $Return.members.'inference.json'.text | ConvertFrom-Json
        if (@($Numeric.parents.PSObject.Properties).Count -ne 54 -or
            $Numeric.cohorts.easy.numeric_checks_passed -cne $true -or
            $Numeric.cohorts.mixed.numeric_checks_passed -cne $true -or
            $Inference.state -cne 'complete' -or @($Inference.cases).Count -ne 4 -or
            $Inference.optimization_runs_added -ne 0 -or $Inference.training_runs_added -ne 0) {
            throw 'Complete application scope mismatch'
        }
    }
}
[ordered]@{return_sha256=$Actual; job_id=$Return.job_id; state=$State;
    downloaded_directory=[IO.Path]::GetFullPath($Destination);
    scientific_reporting_eligible=$false} | ConvertTo-Json
Write-Host 'PR80_INTEGRATED_TRANSFER_VERIFIED: return receipt and directory; no retry or merge.'
