param([switch]$KeepAlive, [switch]$Stop)
$ErrorActionPreference = 'Stop'
$serverConfig = Join-Path $PSScriptRoot 'server.json'
$distro = 'K3LS-Shop'
if (Test-Path -LiteralPath $serverConfig -PathType Leaf) {
    $server = Get-Content -LiteralPath $serverConfig -Raw | ConvertFrom-Json
    if ($server.distro -notmatch '^K3LS-Shop-[0-9a-f]{12}$' -or $server.backup_manifest_sha256 -notmatch '^[0-9a-f]{64}$' -or
        $server.distro -ne ('K3LS-Shop-' + $server.backup_manifest_sha256.Substring(0, 12))) {
        throw 'The saved K3LS server configuration is invalid.'
    }
    $distro = $server.distro
}
if ($Stop) {
    Stop-ScheduledTask -TaskName 'K3LS Shop Server'
    & wsl.exe --terminate $distro
    if ($LASTEXITCODE -ne 0) { throw "Could not stop $distro." }
} elseif ($KeepAlive) {
    # Systemd alone does not prevent WSL from becoming idle. Keep a foreground
    # Linux process attached, and retry if the instance shuts down unexpectedly.
    while ($true) {
        & wsl.exe -d $distro -u root --exec /bin/bash /opt/k3ls/keep-alive.sh
        Start-Sleep -Seconds 15
    }
} else {
    Start-ScheduledTask -TaskName 'K3LS Shop Server'
    Start-Process 'http://localhost:8000'
}
