# K3LS account update

Extract this ZIP to a folder on the Windows shop computer. Double-click `Update K3LS.vbs`.

The PowerShell window stays open. Wait for `Update complete`, then refresh the browser. Use the same Windows account that installed K3LS.

This package adds the blue-and-white login design, the supplied shop logo and username-only sign-in. Email is disabled. It adds password-change dialogs, owner password resets and 100 one-use recovery codes per user.

It uses the installed WSL environment, needs no downloads and does not reinstall ERPNext. Sales, passwords, accounts and uploads remain in place. It changes login/security settings and assigns usernames to accounts that need them. Existing email reset links are invalidated.

After updating, open the account menu and choose `Password and recovery`. Choose `New recovery codes` and save the list. Owners can do the same for staff under `Users` > the person > `Password`. New codes replace the previous unused set. Each code works for that user only and can be used once.

On the login screen, `Forgot password?` asks for the username, one recovery code and the new password. Existing passwords are not changed by installing the update.

The web server pauses briefly during the update. Run it when nobody is checking out. Old app files and the changed security settings are saved inside `/opt/k3ls/updates`. If the new login fails its server check, the updater restores the previous app files and settings. The additive recovery table stays in place; no live shop database is restored.

Logs are in the extracted package's `update-logs` folder. Do not rerun the original full installer to apply this update.
