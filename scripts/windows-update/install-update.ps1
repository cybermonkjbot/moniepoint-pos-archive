$ErrorActionPreference = 'Stop'
try {
    $updateRoot = [IO.Path]::GetFullPath($PSScriptRoot)
    $prefix = $updateRoot.TrimEnd('\') + '\'
    $manifest = Get-Content -LiteralPath (Join-Path $updateRoot 'update-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.format -ne 'k3ls-installer-update-v1') { throw 'Unknown installer-update format.' }
    foreach ($file in $manifest.files) {
        $path = [IO.Path]::GetFullPath((Join-Path $updateRoot $file.path))
        if (-not $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid installer-update file path.' }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing installer file: $($file.path)" }
        if ((Get-Item -LiteralPath $path).Length -ne $file.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
            throw "Changed installer file: $($file.path)"
        }
    }
    $packageRoot = $null
    $candidates = @()
    $candidate = $updateRoot
    while ($candidate) {
        $candidates += $candidate
        $parent = Split-Path -Parent $candidate
        if ($parent -eq $candidate) { break }
        $candidate = $parent
    }
    foreach ($knownFolder in @([Environment]::GetFolderPath('MyDocuments'), [Environment]::GetFolderPath('Desktop'), (Join-Path $env:USERPROFILE 'Downloads'))) {
        $outer = Join-Path $knownFolder $manifest.backup_folder
        $candidates += $outer
        $candidates += Join-Path $outer $manifest.backup_folder
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        $backupManifest = Join-Path $candidate 'manifest.json'
        if ((Test-Path -LiteralPath $backupManifest -PathType Leaf) -and
            (Get-FileHash -LiteralPath $backupManifest -Algorithm SHA256).Hash.ToLowerInvariant() -eq $manifest.backup_manifest_sha256) {
            $packageRoot = $candidate
            break
        }
    }
    if (-not $packageRoot) {
        Add-Type -AssemblyName System.Windows.Forms
        $picker = New-Object System.Windows.Forms.FolderBrowserDialog
        $picker.Description = 'Select the original K3LS-transfer-20261003-174403 folder containing manifest.json and snapshot.'
        $picker.ShowNewFolderButton = $false
        try {
            if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { Write-Host 'Installation cancelled. No shop data was changed.'; return }
            $packageRoot = $picker.SelectedPath
        } finally { $picker.Dispose() }
    }
    $originalManifest = Join-Path $packageRoot 'manifest.json'
    if (-not (Test-Path -LiteralPath $originalManifest -PathType Leaf) -or
        (Get-FileHash -LiteralPath $originalManifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.backup_manifest_sha256) {
        throw 'The selected folder is not the matching K3LS backup. No shop data was changed.'
    }
    $verifier = Join-Path $packageRoot 'verify-transfer.ps1'
    if (-not (Test-Path -LiteralPath $verifier -PathType Leaf) -or
        (Get-FileHash -LiteralPath $verifier -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.backup_verifier_sha256) {
        throw 'The original backup verifier is missing or changed.'
    }
    Write-Host ('Using backup: ' + $packageRoot)
    & (Join-Path $updateRoot 'windows\launch-setup.ps1') -PackageRoot $packageRoot
} catch {
    Write-Host ('Installation stopped: ' + $_.Exception.Message) -ForegroundColor Red
} finally {
    Write-Host 'Close this window when finished.'
}
