& {
    $ErrorActionPreference = 'Stop'
    $pr94Root = '__LOCAL_SCRATCH__'
    $pr94Commit = '__REVIEWED_COMMIT__'
    $pr94Zip = Join-Path $pr94Root '__PREFLIGHT_ZIP__'
    if ((Get-FileHash -LiteralPath $pr94Zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'c8c709a0f495baa0b1e060364544397c6d6c47f60421904b2f696212a304c8df') {
        throw 'SHA256 do preflight original diverge. Preserve os arquivos.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $pr94Archive = [System.IO.Compression.ZipFile]::OpenRead($pr94Zip)
    try {
        $pr94Entry = $pr94Archive.GetEntry('input-paths.private.json')
        if ($null -eq $pr94Entry -or $pr94Entry.Length -gt 65536) { throw 'Mapa privado ausente ou excessivo.' }
        $pr94Reader = [System.IO.StreamReader]::new($pr94Entry.Open())
        try { $pr94Map = $pr94Reader.ReadToEnd() | ConvertFrom-Json } finally { $pr94Reader.Dispose() }
    } finally { $pr94Archive.Dispose() }
    $pr94Parents = [ordered]@{}
    foreach ($pr94Parent in @('CFL_medium_instance_5','CFL_medium_instance_6','CFL_medium_instance_9','CFL_medium_instance_13','CFL_medium_instance_20','CFL_medium_instance_26')) {
        $pr94Found = @($pr94Map | Where-Object { $_.parent -eq $pr94Parent })
        if ($pr94Found.Count -ne 1 -or @($pr94Found[0].candidate_paths).Count -ne 1) { throw 'Identidade privada ambigua.' }
        $pr94Path = [string]$pr94Found[0].candidate_paths[0]
        if (-not $pr94Path.StartsWith('/raid/vrcelestino/data/')) { throw 'Caminho fora do diretorio de dados.' }
        $pr94Parents[$pr94Parent] = $pr94Path
    }
    $pr94Nonce = [guid]::NewGuid().ToString('N')
    $pr94Bash = Join-Path $pr94Root ('pr94-install-' + $pr94Nonce + '.sh')
    $pr94Config = Join-Path $pr94Root ('pr94-inputs-' + $pr94Nonce + '.private.json')
    if ((Test-Path -LiteralPath $pr94Bash) -or (Test-Path -LiteralPath $pr94Config)) { throw 'Destino ja existe.' }
    $pr94Text = [System.IO.File]::ReadAllText((Join-Path $pr94Root 'pr94-installation.template.sh')).Replace('__REVIEWED_COMMIT__', $pr94Commit)
    [System.IO.File]::WriteAllText($pr94Bash, $pr94Text.Replace("`r`n","`n"), [System.Text.UTF8Encoding]::new($false))
    $pr94ConfigText = ([ordered]@{ parents=$pr94Parents; checkpoint_path='' } | ConvertTo-Json -Depth 5) + "`n"
    [System.IO.File]::WriteAllText($pr94Config, $pr94ConfigText, [System.Text.UTF8Encoding]::new($false))
    $pr94BashHash = (Get-FileHash -LiteralPath $pr94Bash -Algorithm SHA256).Hash.ToLowerInvariant()
    $pr94ConfigHash = (Get-FileHash -LiteralPath $pr94Config -Algorithm SHA256).Hash.ToLowerInvariant()
    scp -- $pr94Bash $pr94Config 'vrcelestino@dgx-dasci.ujaen.es:/raid/vrcelestino/data/cfl-mvp2-evidence/'
    if ($LASTEXITCODE -ne 0) { throw 'SCP falhou. Preserve a saida e os arquivos; nao repita automaticamente.' }
    $pr94RemoteBash = '/raid/vrcelestino/data/cfl-mvp2-evidence/' + [System.IO.Path]::GetFileName($pr94Bash)
    $pr94RemoteConfig = '/raid/vrcelestino/data/cfl-mvp2-evidence/' + [System.IO.Path]::GetFileName($pr94Config)
    $pr94Command = "( set -euo pipefail; printf '%s  %s\n' '{0}' '{1}' | sha256sum -c -; bash -- '{1}' '{2}' '{3}' )" -f $pr94BashHash,$pr94RemoteBash,$pr94RemoteConfig,$pr94ConfigHash
    Write-Host 'Na sessao tfm_env do dgx-dasci, execute somente esta linha:'
    Write-Host $pr94Command
    Write-Host 'Instalacao/preflight apenas: nenhum solve, forward, treinamento ou job.'
}
