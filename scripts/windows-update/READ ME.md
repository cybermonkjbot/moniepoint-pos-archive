# Install K3LS

Extract this ZIP anywhere on the Windows PC and double-click `Install K3LS.vbs`.
Approve the administrator prompt. No pasted commands or special folder nesting
are needed.

The installer finds `K3LS-transfer-20261003-174403` in Documents, Desktop or
Downloads, including an extra extraction folder level. If the backup is elsewhere,
select its folder when asked.

The installer checks the database, uploaded files and source archives first.
If an earlier update replaced files in the original transfer, this version saves
copies in `installation-logs` and restores the original installer files.
The backup manifest and shop data are not changed. Corrected scripts run from
their own folder so the archive fix remains active.

This update corrects the uploaded-file archive check for verified Mac metadata.
It creates the log and lock folders before checking the restored site.
It uses the same Linux environment as the original transfer. The database restore
completion marker preserves the database already restored, including logins.
The installer retries missing dependencies, restores the actual uploaded files,
checks the saved data and sets up the Windows startup task.

PowerShell stays open and logs are saved in the original backup's `installation-logs`.
Wait for `K3LS is installed`, then check the existing login at `http://localhost:8000`.
Windows completion still needs confirmation on the receiving PC.
