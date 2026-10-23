# Offline workstation integration test. Place next to the receiver and the
# previously validated pr78-recovery-easy-c66cf6b3d10d public return fixture.
# The sftp function below is a mock: this test never opens an SSH connection.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Receiver = Join-Path $PSScriptRoot 'receive_pr78_recovery_parent.ps1'
$Fixture = Join-Path $PSScriptRoot 'pr78-recovery-easy-c66cf6b3d10d'
$ExpectedSha = 'c66cf6b3d10df04a443f371f070432c98edb4a5f10bef6ace5f8c9260bd7ac22'
$TestRoot = Join-Path $PSScriptRoot ('pr78-sftp-offline-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TestRoot | Out-Null
$TestState = @{ Calls = 0; Mode = 'success' }
function sftp {
    $TestState.Calls++
    $BatchIndex = [array]::IndexOf($args, '-b')
    if ($BatchIndex -lt 0 -or $args -notcontains 'BatchMode=no' -or $args -notcontains 'NumberOfPasswordPrompts=1') { throw 'Wrong SFTP options' }
    $Lines = @(Get-Content -LiteralPath $args[$BatchIndex + 1])
    if ($Lines.Count -ne 9 -or $Lines[0] -notmatch '^lcd "([^"]+)"$') { throw 'Wrong batch' }
    $Target = $Matches[1]
    $ExpectedCommands = @('cd "/raid/vrcelestino/data/cfl-mvp2-evidence/pr78/recovery-job3481-v2/flow/return-easy"','get SHA256SUMS.txt','get accounting.json','get operator_approval.json','get operator_plan.json','get submission.json','-get matrix.tar.gz','bye')
    if (Compare-Object $ExpectedCommands $Lines[1..8]) { throw 'Non-allowlisted command' }
    if ($TestState.Mode -eq 'connection_error') { $global:LASTEXITCODE = 255; return }
    Get-ChildItem -LiteralPath $Fixture -File | Copy-Item -Destination $Target
    if ($TestState.Mode -eq 'corrupt_manifest') { [IO.File]::AppendAllText((Join-Path $Target 'SHA256SUMS.txt'), 'corrupt') }
    if ($TestState.Mode -eq 'missing_member') { Rename-Item -LiteralPath (Join-Path $Target 'submission.json') -NewName 'missing.json' }
    if ($TestState.Mode -eq 'unexpected_archive') { [IO.File]::WriteAllText((Join-Path $Target 'matrix.tar.gz'), 'unexpected') }
    if ($TestState.Mode -eq 'corrupt_member') { [IO.File]::AppendAllText((Join-Path $Target 'accounting.json'), 'corrupt') }
    $global:LASTEXITCODE = 0
}
foreach ($Case in @('success','corrupt_manifest','missing_member','unexpected_archive','corrupt_member','connection_error')) {
    $TestState.Mode = $Case
    $Before = $TestState.Calls
    $CaseRoot = Join-Path $TestRoot $Case
    New-Item -ItemType Directory -Path $CaseRoot | Out-Null
    $Failed = $false
    try { & $Receiver -Parent easy -ExpectedReturnSha $ExpectedSha -DownloadRoot $CaseRoot | Out-Null }
    catch { $Failed = $true; Write-Output $_.Exception.Message }
    if ($TestState.Calls -ne $Before + 1) { throw "Not exactly one connection: $Case" }
    if ($Failed -ne ($Case -ne 'success')) { throw "Unexpected outcome: $Case" }
    Write-Output "PASS: $Case"
}
$Before = $TestState.Calls
$Failed = $false
try { & $Receiver -Parent easy -ExpectedReturnSha $ExpectedSha -DownloadRoot (Join-Path $TestRoot 'success') | Out-Null }
catch { $Failed = $true }
if (-not $Failed -or $TestState.Calls -ne $Before) { throw 'Existing destination must stop before connection' }
Write-Output 'PASS: existing_destination_no_connection'
Write-Output 'PR78_SFTP_RECEIVER_7_OFFLINE_CASES_PASSED_NO_NETWORK'
