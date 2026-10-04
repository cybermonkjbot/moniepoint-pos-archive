# K3LS login update

Extract this ZIP to a folder on the Windows shop computer. Double-click `Update K3LS.vbs`.

The PowerShell window stays open. Wait for `Update complete`, then refresh the browser. Use the same Windows account that installed K3LS.

This package adds the blue-and-white login design and the supplied shop logo. It uses the installed WSL environment, needs no downloads and does not reinstall ERPNext. It does not replace sales, users, passwords, accounts, uploaded files or site settings.

The web server pauses briefly during the update. Run it when nobody is checking out. Old app files are saved inside the shop's Linux environment under `/opt/k3ls/updates`. If the new login fails the server check, the updater restores the previous app files.

Logs are in the extracted package's `update-logs` folder. Do not rerun the original full installer to apply this update.
