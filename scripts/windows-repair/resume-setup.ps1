param([string]$PackageRoot)
$ErrorActionPreference = 'Stop'
try {
    $repairRoot = [IO.Path]::GetFullPath($PSScriptRoot)
    $repairPrefix = $repairRoot.TrimEnd('\') + '\'
    $manifest = Get-Content -LiteralPath (Join-Path $repairRoot 'repair-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.format -ne 'k3ls-windows-repair-v1') { throw 'Unknown repair format.' }
    foreach ($file in $manifest.files) {
        $path = [IO.Path]::GetFullPath((Join-Path $repairRoot $file.path))
        if (-not $path.StartsWith($repairPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid repair file path.' }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing repair file: $($file.path)" }
        if ((Get-Item -LiteralPath $path).Length -ne $file.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
            throw "Changed repair file: $($file.path)"
        }
    }
    if (-not $PackageRoot) {
        # Windows Extract All can add another wrapper folder. Check ancestors
        # for this exact backup rather than requiring one fixed folder depth.
        $candidate = $repairRoot
        while ($candidate) {
            $candidateManifest = Join-Path $candidate 'manifest.json'
            if ((Test-Path -LiteralPath $candidateManifest -PathType Leaf) -and
                (Get-FileHash -LiteralPath $candidateManifest -Algorithm SHA256).Hash.ToLowerInvariant() -eq $manifest.backup_manifest_sha256) {
                $PackageRoot = $candidate
                break
            }
            $parent = Split-Path -Parent $candidate
            if ($parent -eq $candidate) { break }
            $candidate = $parent
        }
    }
    if (-not $PackageRoot) {
        throw 'No matching backup was found above this repair folder. Place the repair anywhere inside K3LS-transfer-20261003-170202, or pass -PackageRoot with the original backup folder.'
    }
    $packageRoot = [IO.Path]::GetFullPath($PackageRoot)
    $originalManifest = Join-Path $packageRoot 'manifest.json'
    if (-not (Test-Path -LiteralPath $originalManifest -PathType Leaf)) {
        throw ('The selected backup folder has no manifest.json: ' + $packageRoot)
    }
    if ((Get-FileHash -LiteralPath $originalManifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.backup_manifest_sha256) {
        throw 'This repair belongs to K3LS-transfer-20261003-170202. The backup manifest does not match. No changes were made.'
    }
    $verifier = Join-Path $packageRoot 'verify-transfer.ps1'
    if (-not (Test-Path -LiteralPath $verifier -PathType Leaf) -or (Get-FileHash -LiteralPath $verifier -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.backup_verifier_sha256) {
        throw 'The original backup verifier is missing or changed. Keep the original transfer files intact.'
    }
    Write-Host 'Repair files verified. Resuming the existing K3LS backup.'
    & (Join-Path $repairRoot 'windows\launch-setup.ps1') -PackageRoot $packageRoot
} catch {
    Write-Host ('Setup stopped: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'No backup files were replaced. Close this window when finished.'
}
