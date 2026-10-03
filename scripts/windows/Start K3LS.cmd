@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\K3LS\Launcher\start-windows.ps1"
if errorlevel 1 pause
