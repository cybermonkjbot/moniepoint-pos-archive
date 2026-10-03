param([switch]$ForSetup)
$ErrorActionPreference = 'Stop'
try {
    $manifestPath = Join-Path $PSScriptRoot 'manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.format -ne 'k3ls-transfer-v1') { throw 'Unknown backup format.' }
    $rootPath = [IO.Path]::GetFullPath($PSScriptRoot) + [IO.Path]::DirectorySeparatorChar
    foreach ($file in $manifest.files) {
        $path = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $file.path))
        if (-not $path.StartsWith($rootPath, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'The manifest contains a path outside the backup folder.'
        }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing file: $($file.path)" }
        if ((Get-Item -LiteralPath $path).Length -ne $file.bytes) { throw "Incomplete file: $($file.path)" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
            throw "Changed file: $($file.path)"
        }
    }
    Write-Host 'Backup verified. Database, files and source archives are intact.'
    if ($ForSetup) {
        Write-Host 'File check passed. Continuing installation...'
    } else {
        Write-Host 'This checks the transfer. It does not install or start ERPNext on Windows.'
    }
    exit 0
} catch {
    Write-Host "Backup verification failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
