@echo off
if exist "%~dp0windows\setup-windows.ps1" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\setup-windows.ps1"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1"
)
set "K3LS_RESULT=%ERRORLEVEL%"
pause
exit /b %K3LS_RESULT%
