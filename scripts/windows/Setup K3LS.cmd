@echo off
if exist "%~dp0windows\launch-setup.ps1" (
  start "K3LS installation" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\launch-setup.ps1"
) else (
  start "K3LS installation" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-setup.ps1"
)
exit /b
