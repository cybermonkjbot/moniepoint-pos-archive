# The visible PowerShell host never runs the installer's exit statements.
# The installer runs in a child process, with output kept in this window.
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot
$powershell = Join-Path $PSHOME 'powershell.exe'
$log = $null
try {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $arguments = '-NoExit -NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '"'
        Start-Process -FilePath $powershell -Verb RunAs -ArgumentList $arguments -WorkingDirectory $packageRoot
        Write-Host 'Continue in the administrator PowerShell window.'
        return
    }
    $Host.UI.RawUI.WindowTitle = 'K3LS installation'
    Set-Location -LiteralPath $packageRoot
    $logs = Join-Path $packageRoot 'installation-logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $log = Join-Path $logs ('k3ls-install-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
    Write-Host 'Installing K3LS. This window stays open when setup finishes or fails.'
    Write-Host ('Log: ' + $log)
    # Windows PowerShell 5.1 can wrap native stderr as non-terminating errors.
    # Keep all output and use the installer process exit code as the result.
    $ErrorActionPreference = 'Continue'
    & $powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'setup-windows.ps1') -Elevated 2>&1 | Tee-Object -FilePath $log
    $result = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    Write-Host ''
    if ($result -eq 0) {
        Write-Host 'Installer finished. Check the message above for installation success or a Windows restart.' -ForegroundColor Green
    } else {
        Write-Host ('Installation did not complete. Installer exit code: ' + $result) -ForegroundColor Red
        Write-Host 'The error above and the log file show where setup stopped.'
    }
    Write-Host ('Log saved to ' + $log)
} catch {
    Write-Host ('Launcher stopped: ' + $_.Exception.Message) -ForegroundColor Red
    if ($log) { Write-Host ('Log: ' + $log) }
} finally {
    Write-Host 'You can now read the results. Close this window when finished.'
}
