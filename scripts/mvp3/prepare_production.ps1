param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$SourceCommit,
    [Parameter(Mandatory=$true)][string]$CIReceipt,
    [Parameter(Mandatory=$true)][string]$Output,
    [string]$LicenseFile = 'C:\gurobi1400\gurobi.lic'
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'Run this entry with PowerShell 7.' }
if (-not (Test-Path -LiteralPath $LicenseFile -PathType Leaf)) { throw 'Existing local Gurobi14 license path unavailable.' }
$productionRepo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$productionEntry = Join-Path $PSScriptRoot 'qualify_production.py'
$productionStart = [System.Diagnostics.ProcessStartInfo]::new()
$productionStart.FileName = $Python
$productionStart.UseShellExecute = $false
$productionStart.WorkingDirectory = $productionRepo
# ProcessStartInfo inherits the normal environment; only the child route changes.
$productionStart.Environment['GRB_LICENSE_FILE'] = $LicenseFile
foreach ($productionArgument in @('-B', $productionEntry, 'prepare', '--repository', $productionRepo, '--source-commit', $SourceCommit, '--ci-receipt', $CIReceipt, '--output', $Output, '--local-license-file', $LicenseFile)) {
    [void]$productionStart.ArgumentList.Add($productionArgument)
}
$productionProcess = [System.Diagnostics.Process]::Start($productionStart)
$productionProcess.WaitForExit()
if ($productionProcess.ExitCode -ne 0) { throw 'Preparation failed. Preserve output; do not execute remote steps or retry automatically.' }
