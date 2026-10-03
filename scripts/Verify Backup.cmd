@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-transfer.ps1"
set "K3LS_RESULT=%ERRORLEVEL%"
pause
exit /b %K3LS_RESULT%
