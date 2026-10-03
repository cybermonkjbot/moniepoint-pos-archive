$ErrorActionPreference = 'Stop'
function Test-IdenticalFile {
    param([string]$Path, $File)
    return ((Test-Path -LiteralPath $Path -PathType Leaf) -and
        (Get-Item -LiteralPath $Path).Length -eq $File.bytes -and
        (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $File.sha256)
}
try {
    $updateRoot = [IO.Path]::GetFullPath($PSScriptRoot)
    $prefix = $updateRoot.TrimEnd('\') + '\'
    $manifest = Get-Content -LiteralPath (Join-Path $updateRoot 'update-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.format -ne 'k3ls-installer-update-v2') { throw 'Unknown installer-update format.' }
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
    $backup = Get-Content -LiteralPath $originalManifest -Raw | ConvertFrom-Json
    if ($backup.format -ne 'k3ls-transfer-v1') { throw 'Unknown backup format.' }
    $packagePrefix = [IO.Path]::GetFullPath($packageRoot).TrimEnd('\') + '\'
    $repairs = @()
    Write-Host 'Checking shop backup files and installer replacements...'
    # Verify the complete data payload before making any installer repairs.
    # Only the pinned manifest's installer files can be replaced.
    foreach ($file in $backup.files) {
        $target = [IO.Path]::GetFullPath((Join-Path $packageRoot $file.path))
        if (-not $target.StartsWith($packagePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid backup file path.' }
        if ($file.path.StartsWith('snapshot/', [StringComparison]::Ordinal)) {
            if (-not (Test-IdenticalFile -Path $target -File $file)) { throw ('Missing or changed shop backup file: ' + $file.path) }
            continue
        }
        if ($file.path -notin @('Install K3LS.vbs', 'READ ME.md', 'verify-transfer.ps1') -and
            -not $file.path.StartsWith('windows/', [StringComparison]::Ordinal)) { throw 'Unexpected backup installer path.' }
        $source = [IO.Path]::GetFullPath((Join-Path $updateRoot ('original-installer/' + $file.path)))
        if (-not $source.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-IdenticalFile -Path $source -File $file)) { throw ('Original installer replacement is missing or changed: ' + $file.path) }
        if (-not (Test-IdenticalFile -Path $target -File $file)) {
            if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath $target -PathType Leaf)) { throw ('Installer file path is a folder: ' + $file.path) }
            $repairs += [PSCustomObject]@{ File = $file; Target = $target; Source = $source }
        }
    }
    Write-Host ('Using backup: ' + $packageRoot)
    # Stage corrected scripts first. If the ZIP was extracted over the original
    # windows folder, restoring its old files must not remove the archive fix.
    $stage = Join-Path $packageRoot ('installation-logs\installer-update-' + [Guid]::NewGuid().ToString('N'))
    $stageWindows = Join-Path $stage 'windows'
    New-Item -ItemType Directory -Path $stageWindows -Force | Out-Null
    foreach ($file in $manifest.files) {
        if (-not $file.path.StartsWith('windows/', [StringComparison]::Ordinal)) { continue }
        $target = Join-Path $stageWindows $file.path.Substring(8)
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $updateRoot $file.path) -Destination $target
        if (-not (Test-IdenticalFile -Path $target -File $file)) { throw ('Installer staging failed: ' + $file.path) }
    }
    foreach ($repair in $repairs) {
        if (Test-Path -LiteralPath $repair.Target -PathType Leaf) {
            $saved = Join-Path $stage ('replaced-installer-files/' + $repair.File.path)
            New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
            Copy-Item -LiteralPath $repair.Target -Destination $saved
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $repair.Target) -Force | Out-Null
        Copy-Item -LiteralPath $repair.Source -Destination $repair.Target -Force
        if (-not (Test-IdenticalFile -Path $repair.Target -File $repair.File)) { throw ('Installer file repair failed: ' + $repair.File.path) }
        Write-Host ('Restored installer file: ' + $repair.File.path)
    }
    if ($repairs.Count -gt 0) { Write-Host ('Copies of replaced files: ' + (Join-Path $stage 'replaced-installer-files')) }
    & (Join-Path $stageWindows 'launch-setup.ps1') -PackageRoot $packageRoot
} catch {
    Write-Host ('Installation stopped: ' + $_.Exception.Message) -ForegroundColor Red
} finally {
    Write-Host 'Close this window when finished.'
}
