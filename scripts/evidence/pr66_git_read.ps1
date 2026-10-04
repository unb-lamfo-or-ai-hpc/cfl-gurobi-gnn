# SPDX-License-Identifier: MIT
# Read the exact checkout with child-process-only trust, including older Git.
function Invoke-Pr66GitRead {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string] $Repository,
        [Parameter(Mandatory = $true)][string[]] $GitArguments
    )
    $Resolved = (Resolve-Path -LiteralPath $Repository -ErrorAction Stop).ProviderPath
    if (!(Test-Path -LiteralPath (Join-Path $Resolved '.git'))) {
        throw 'Existing Git checkout required; no trust configuration created'
    }
    $Normalized = $Resolved.Replace('\', '/').TrimEnd('/')
    $Revision = '^(HEAD|[0-9a-f]{7,40})$'
    $Permitted = $false
    switch ($GitArguments[0]) {
        'branch' { $Permitted = $GitArguments.Count -eq 2 -and $GitArguments[1] -eq '--show-current' }
        'status' { $Permitted = $GitArguments.Count -eq 2 -and $GitArguments[1] -eq '--porcelain' }
        'rev-parse' { $Permitted = $GitArguments.Count -eq 2 -and $GitArguments[1] -match $Revision }
        'ls-tree' { $Permitted = $GitArguments.Count -eq 4 -and $GitArguments[1] -eq '-r' -and $GitArguments[2] -eq '--name-only' -and $GitArguments[3] -match $Revision }
        'diff' { $Permitted = $GitArguments.Count -eq 4 -and $GitArguments[1] -eq '--name-only' -and $GitArguments[2] -match $Revision -and $GitArguments[3] -match $Revision }
        'cat-file' { $Permitted = $GitArguments.Count -eq 3 -and $GitArguments[1] -eq 'blob' -and $GitArguments[2] -match '^(HEAD|[0-9a-f]{7,40}):[A-Za-z0-9_./-]+$' }
    }
    if (!$Permitted) {
        throw 'Only publisher Git inspection commands are permitted'
    }
    $Arguments = @('-C', $Normalized) + $GitArguments
    if ($Arguments | Where-Object { $_ -match '["\r\n]' -or $_.EndsWith('\') }) {
        throw 'Unsupported Git inspection argument'
    }
    $Utf8Encoding = New-Object System.Text.UTF8Encoding($false)
    $Directory = Join-Path ([System.IO.Path]::GetTempPath()) ('cfl-pr66-git-' + [Guid]::NewGuid().ToString('N'))
    $Configuration = Join-Path $Directory 'config'
    $Process = $null
    try {
        [System.IO.Directory]::CreateDirectory($Directory) | Out-Null
        # Clear inherited entries; do not trust '*', the common gitdir or any sibling.
        $QuotedPath = ConvertTo-Json -InputObject $Normalized -Compress
        [System.IO.File]::WriteAllText($Configuration, "[safe]`n`tdirectory =`n`tdirectory = $QuotedPath`n", $Utf8Encoding)
        $Start = New-Object System.Diagnostics.ProcessStartInfo
        $Start.FileName = 'git'
        $Start.Arguments = (($Arguments | ForEach-Object { '"' + $_ + '"' }) -join ' ')
        $Start.UseShellExecute = $false
        $Start.RedirectStandardOutput = $true
        $Start.RedirectStandardError = $true
        $Start.StandardOutputEncoding = $Utf8Encoding
        $Start.EnvironmentVariables['GIT_CONFIG_GLOBAL'] = $Configuration
        $Start.EnvironmentVariables['GIT_CONFIG_NOSYSTEM'] = '1'
        $Start.EnvironmentVariables['GIT_CONFIG_COUNT'] = '0'
        $Start.EnvironmentVariables['GIT_CONFIG_PARAMETERS'] = ''
        $Start.EnvironmentVariables['GIT_OPTIONAL_LOCKS'] = '0'
        $Process = [System.Diagnostics.Process]::Start($Start)
        $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
        $StderrTask = $Process.StandardError.ReadToEndAsync()
        $Process.WaitForExit()
        $StdoutText = $StdoutTask.GetAwaiter().GetResult()
        $StderrText = $StderrTask.GetAwaiter().GetResult()
        if ($Process.ExitCode -ne 0) {
            throw "Git inspection failed (exit $($Process.ExitCode)); preserve the checkout. $StderrText"
        }
        return $StdoutText
    } finally {
        if ($null -ne $Process) { $Process.Dispose() }
        if ([System.IO.File]::Exists($Configuration)) { [System.IO.File]::Delete($Configuration) }
        if ([System.IO.Directory]::Exists($Directory)) { [System.IO.Directory]::Delete($Directory, $false) }
    }
}
