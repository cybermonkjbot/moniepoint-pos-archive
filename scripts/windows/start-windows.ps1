param([switch]$KeepAlive)
$ErrorActionPreference = 'Stop'
if ($KeepAlive) {
    # Systemd alone does not prevent WSL from becoming idle. Keep a foreground
    # Linux process attached, and retry if the instance shuts down unexpectedly.
    while ($true) {
        & wsl.exe -d K3LS-Shop -u root -- bash -c 'systemctl start mariadb nginx k3ls.target && exec /usr/bin/sleep infinity'
        Start-Sleep -Seconds 15
    }
} else {
    Start-ScheduledTask -TaskName 'K3LS Shop Server'
    Start-Process 'http://localhost:8000'
}
