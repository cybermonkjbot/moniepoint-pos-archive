@echo off
powershell.exe -NoProfile -Command "Stop-ScheduledTask -TaskName 'K3LS Shop Server'"
wsl.exe --terminate K3LS-Shop
pause
