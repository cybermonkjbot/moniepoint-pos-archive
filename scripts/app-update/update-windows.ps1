$ErrorActionPreference = 'Stop'
function Invoke-Wsl {
    param([string[]]$Arguments)
    & wsl.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed with code $LASTEXITCODE." }
}
try {
    $updateRoot = [IO.Path]::GetFullPath($PSScriptRoot)
    $manifestPath = Join-Path $updateRoot 'update-manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.format -ne 'k3ls-app-update-v1') { throw 'Unknown app-update format.' }
    $prefix = $updateRoot.TrimEnd('\') + '\'
    $seen = @{}
    foreach ($file in $manifest.files) {
        if ($file.path -notmatch '^[A-Za-z0-9_ .\-/]+$' -or $seen.ContainsKey($file.path)) { throw 'Invalid or duplicate update path.' }
        $seen[$file.path] = $true
        $path = [IO.Path]::GetFullPath((Join-Path $updateRoot $file.path))
        if (-not $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid update path.' }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            (Get-Item -LiteralPath $path).Length -ne $file.bytes -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
            throw ('Missing or changed update file: ' + $file.path)
        }
    }
    $serverPath = Join-Path $env:LOCALAPPDATA 'K3LS\Launcher\server.json'
    if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) { throw 'K3LS is not installed for this Windows account. Use the account that installed the shop.' }
    $server = Get-Content -LiteralPath $serverPath -Raw | ConvertFrom-Json
    if ($server.backup_manifest_sha256 -ne $manifest.backup_manifest_sha256 -or
        $server.distro -ne ('K3LS-Shop-' + $manifest.backup_manifest_sha256.Substring(0, 12))) {
        throw 'This update does not match the installed shop. No app files were changed.'
    }
    Write-Host ('Updating installed shop: ' + $server.distro)
    Write-Host 'Sales, users, passwords, accounts and uploaded files will not be replaced.'
    # Pass paths straight to wslpath, never through bash, which strips backslashes.
    $lines = @(& wsl.exe -d $server.distro -u root --exec /usr/bin/wslpath -u $updateRoot)
    if ($LASTEXITCODE -ne 0) { throw 'Could not locate the update folder inside WSL.' }
    $linuxRoot = (($lines -join "`n") -replace "`0", '').Trim()
    if (-not $linuxRoot.StartsWith('/mnt/')) { throw 'Copy the extracted update to a local Windows drive.' }
    $manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Invoke-Wsl -Arguments @('-d', $server.distro, '-u', 'root', '--exec', '/usr/bin/python3', "$linuxRoot/update-linux.py", $linuxRoot, $manifestHash)
    exit 0
} catch {
    Write-Host ('Update stopped: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
