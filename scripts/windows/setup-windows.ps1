param([switch]$Elevated)
$ErrorActionPreference = 'Stop'
$distro = 'K3LS-Shop'
$taskName = 'K3LS Shop Server'
$packageRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Wsl {
    param([string[]]$Arguments)
    & wsl.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed with code $LASTEXITCODE." }
}

try {
    $build = [int](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuildNumber
    if ($build -lt 19041) { throw 'Windows 10 version 2004 or newer is required. Update Windows before setup.' }
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw 'This package requires a 64-bit Intel/AMD Windows PC.'
    }
    if ($packageRoot.StartsWith('\\')) { throw 'Copy the package to a local drive before running setup.' }
    if ($env:USERNAME -eq 'SYSTEM') { throw 'Run setup as the Windows account that will use the shop.' }
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Elevated'
        $child = Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
        exit $child.ExitCode
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $packageRoot 'verify-transfer.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Backup verification failed. Copy the complete package again.' }
    $localRoot = Join-Path $env:LOCALAPPDATA 'K3LS'
    New-Item -ItemType Directory -Path $localRoot -Force | Out-Null
    $wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
    $vmFeature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
    if ($wslFeature.State -ne 'Enabled' -or $vmFeature.State -ne 'Enabled') {
        Write-Host 'Enabling WSL2. Windows may need a restart; run this same script again afterward.'
        Invoke-Wsl -Arguments @('--install', '--no-distribution')
        Write-Host 'Restart Windows, then double-click Setup K3LS.cmd again.'
        exit 0
    }
    Invoke-Wsl -Arguments @('--update')
    & wsl.exe --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Update the WSL app from Microsoft, restart Windows and rerun setup.' }
    $registered = @(& wsl.exe --list --quiet | ForEach-Object { ($_ -replace "`0", '').Trim() })
    if ($LASTEXITCODE -ne 0) { throw 'WSL is not ready. Restart Windows and rerun setup.' }
    $installLocation = Join-Path $localRoot 'Linux'
    $fingerprint = (Get-FileHash -LiteralPath (Join-Path $packageRoot 'manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    $ownership = Join-Path $localRoot 'imported-backup-id.txt'
    if ($registered -notcontains $distro) {
        if (Test-Path -LiteralPath $installLocation) { throw 'A previous Linux folder exists. Setup will not overwrite it.' }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $image = Join-Path $localRoot 'ubuntu-24.04-amd64.rootfs.tar.gz'
        if (-not (Test-Path -LiteralPath $image)) {
            Write-Host 'Downloading Ubuntu from Canonical...'
            $oldProgress = $ProgressPreference
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://cloud-images.ubuntu.com/wsl/releases/24.04/current/ubuntu-noble-wsl-amd64-24.04lts.rootfs.tar.gz' -OutFile $image
            $ProgressPreference = $oldProgress
        }
        $expected = '2a790896740b14d637dbdc583cce1ba081ac53b9e9cdb46dc09a2f73abbd9934'
        if ((Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
            throw 'Ubuntu image checksum mismatch. The download may be incomplete or Canonical changed this image. Do not use it.'
        }
        Invoke-Wsl -Arguments @('--import', $distro, $installLocation, $image, '--version', '2')
        Set-Content -LiteralPath $ownership -Value $fingerprint -Encoding ASCII
        Invoke-Wsl -Arguments @('-d', $distro, '-u', 'root', '--', 'bash', '-c', 'printf "[boot]\nsystemd=true\n[user]\ndefault=k3ls\n" > /etc/wsl.conf')
        Invoke-Wsl -Arguments @('--terminate', $distro)
    } else {
        & wsl.exe -d $distro -u root -- test -f /opt/k3ls/.complete
        $complete = $LASTEXITCODE -eq 0
        & wsl.exe -d $distro -u root -- test -f /opt/k3ls/.package-id
        if ($LASTEXITCODE -ne 0) {
            $registration = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | ForEach-Object { Get-ItemProperty $_.PSPath } | Where-Object { $_.DistributionName -eq $distro }
            $ownedImport = (Test-Path -LiteralPath $ownership) -and ((Get-Content -LiteralPath $ownership -Raw).Trim() -eq $fingerprint)
            $basePath = if ($registration) { $registration.BasePath -replace '^\\\\\?\\', '' } else { '' }
            $sameLocation = $registration -and ([IO.Path]::GetFullPath($basePath).TrimEnd('\') -eq [IO.Path]::GetFullPath($installLocation).TrimEnd('\'))
            if (-not $ownedImport -or -not $sameLocation) { throw 'A different K3LS-Shop distribution already exists. Setup will not change it.' }
            Invoke-Wsl -Arguments @('-d', $distro, '-u', 'root', '--', 'bash', '-c', 'printf "[boot]\nsystemd=true\n[user]\ndefault=k3ls\n" > /etc/wsl.conf')
            Invoke-Wsl -Arguments @('--terminate', $distro)
        } else {
            $saved = (& wsl.exe -d $distro -u root -- cat /opt/k3ls/.package-id).Trim()
            if ($saved -ne $fingerprint) { throw 'This installation belongs to another backup. Restoring over it is blocked.' }
        }
    }
    $linuxRoot = (& wsl.exe -d $distro -u root -- wslpath -u $packageRoot).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $linuxRoot) { throw 'Could not locate the transferred folder inside Linux.' }
    Write-Host 'Installing the exact K3LS backup into its own Linux environment...'
    Invoke-Wsl -Arguments @('-d', $distro, '-u', 'root', '--', 'bash', "$linuxRoot/windows/install-linux.sh", $linuxRoot)
    $stable = Join-Path $localRoot 'Launcher'
    New-Item -ItemType Directory -Path $stable -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'start-windows.ps1') -Destination $stable -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Start K3LS.cmd') -Destination $stable -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Stop K3LS.cmd') -Destination $stable -Force
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $stable 'start-windows.ps1') + '" -KeepAlive')
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
    $taskPrincipal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $taskPrincipal -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $stable 'Start K3LS.cmd') -Destination ([Environment]::GetFolderPath('Desktop')) -Force
    Copy-Item -LiteralPath (Join-Path $stable 'Stop K3LS.cmd') -Destination ([Environment]::GetFolderPath('Desktop')) -Force
    Start-ScheduledTask -TaskName $taskName
    Write-Host 'K3LS is installed. It starts after Windows sign-in and restarts failed services.'
    Write-Host 'The PC must stay powered on and awake. No sleep or firewall settings were changed.'
    Write-Host 'Open http://localhost:8000 and use the same shop username and password.'
    Start-Process 'http://localhost:8000'
} catch {
    Write-Host "Setup stopped: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
