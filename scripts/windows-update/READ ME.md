# Install K3LS

Extract this ZIP anywhere on the Windows PC and double-click `Install K3LS.vbs`.
Approve the administrator prompt. No pasted commands or special folder nesting
are needed.

The installer finds `K3LS-transfer-20261003-174403` in Documents, Desktop or
Downloads, including an extra extraction folder level. If the backup is elsewhere,
select its folder when asked. The original transfer and its manifest remain intact.

This update corrects the uploaded-file archive check for verified Mac metadata.
It uses the same Linux environment as the original transfer. The database restore
completion marker preserves the database already restored, including logins.
The installer retries missing dependencies, restores the actual uploaded files,
checks the saved data and sets up the Windows startup task.

PowerShell stays open and logs are saved in the original backup's `installation-logs`.
Wait for `K3LS is installed`, then check the existing login at `http://localhost:8000`.
Windows completion still needs confirmation on the receiving PC.
