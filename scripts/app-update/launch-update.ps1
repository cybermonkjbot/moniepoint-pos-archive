# The visible host stays open. Only the child updater uses exit statements.
$ErrorActionPreference = 'Stop'
$log = $null
try {
    $Host.UI.RawUI.WindowTitle = 'K3LS update'
    Set-Location -LiteralPath $PSScriptRoot
    $logs = Join-Path $PSScriptRoot 'update-logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $log = Join-Path $logs ('k3ls-update-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
    Write-Host 'Updating K3LS. This window stays open when the update finishes or fails.'
    Write-Host ('Log: ' + $log)
    $powershell = Join-Path $PSHOME 'powershell.exe'
    $ErrorActionPreference = 'Continue'
    & $powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'update-windows.ps1') 2>&1 | Tee-Object -FilePath $log
    $result = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    Write-Host ''
    if ($result -eq 0) {
        Write-Host 'Update complete. Refresh the shop browser.' -ForegroundColor Green
    } else {
        Write-Host ('Update did not complete. Exit code: ' + $result) -ForegroundColor Red
        Write-Host 'The error above shows where the update stopped.'
    }
    Write-Host ('Log saved to ' + $log)
} catch {
    Write-Host ('Update launcher stopped: ' + $_.Exception.Message) -ForegroundColor Red
} finally {
    Write-Host 'Close this window when finished.'
}
