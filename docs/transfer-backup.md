# K3LS transfer backup

This package preserves the running K3LS shop as of the date in `manifest.json`.
It contains private business records, login hashes and connection secrets. Keep
the folder and archive private. Do not publish them or put them in a public repository.

## Transfer

Copy the complete `K3LS-transfer-...` folder to the other machine. Alternatively,
copy and extract the matching `.zip` archive. Keep its `.sha256` checksum too.
On Windows, double-click `Verify Backup.cmd` to check the files after copying.
The verifier uses built-in PowerShell and does not install software or restore data.

## Preserved state

- `snapshot/database.sql.gz` is the full database, including users, password hashes,
  roles, permissions, company/shop settings, custom fields, products and records.
- `snapshot/site_config.json` preserves the encryption key needed to read the
  encrypted connection credentials. Keep it with the database.
- `snapshot/public-files.tar` and `private-files.tar` are Frappe's file backups.
- `snapshot/project-source.tar.gz` contains the exact live app working trees, all
  available local Git history, unsaved-to-Git changes, generated CSS/JS assets,
  startup scripts, project documentation and original source checkouts. The
  `bench/apps` trees are the running apps, not `original-checkouts`.
- `snapshot/site-assets.tar.gz` contains the asset manifest and compiled translations.
- `snapshot/python-requirements.txt` records the installed Python dependencies.
- `snapshot/site-state.json` and `code-state.json` record app versions, record counts,
  account identities, authentication fingerprint, commits and working-tree status.
- `snapshot/client-source` preserves the original workbook and supplied app logo.
- `snapshot/walkthrough-project.tar.gz` preserves the existing video project without
  rendering or changing it.

Mac-specific programs, the Python virtual environment, Node dependencies, live
database files and Redis queues are not portable and are not copied as runtimes.
The SQL dump is the portable database backup. Shallow core Git repositories retain
all history already present locally, not history that was never downloaded.

## Accounts

Use the same usernames and current passwords after a proper restoration. Passwords
are preserved as hashes, not exported as readable text. Encrypted settings need the
original `encryption_key` in `site_config.json`. No passwords, roles or payment
settings were reset for this export.

## Install on Windows

Use a 64-bit Intel/AMD Windows 10 PC, version 2004 or newer, with virtualization
enabled and internet access. Extract the entire ZIP to a local drive. Double-click
`Install K3LS.vbs` at the top of the extracted folder and approve Windows elevation.
It opens PowerShell directly, without a Command Prompt window. PowerShell stays
open after success, a restart request or failure. Installation output is also
saved under `installation-logs` in the extracted folder.
`Setup K3LS.cmd` remains available as a compatibility launcher for the same window.
If setup enables WSL2 and asks for a restart, restart and run the same file again.

The script imports a dedicated Ubuntu 24.04 WSL2 distribution named `K3LS-Shop`,
installs the pinned Python, Node and Bench runtimes, MariaDB, Redis and Nginx,
then restores the saved database, files, encryption key and exact app source.
It checks file checksums before installation and compares restored app versions,
table and record counts, and authentication records with the backup.
Existing WSL distributions are not changed. Docker and Homebrew are not used.
No initial shop setup, password reset, stock posting or asset build runs.

Open http://localhost:8000 and use the same shop login. `Start K3LS.cmd` and
`Stop K3LS.cmd` are copied to the Windows desktop. A scheduled task starts the
server after sign-in, and systemd restarts failed services. A foreground WSL
process keeps the distribution active rather than relying on systemd alone.
The PC must remain powered on and awake. The script does not change sleep or
firewall settings and does not configure access from other computers or the internet.

The installer has been reviewed in source but has not run successfully on Windows. Preserve
the original ZIP and Mac installation until the Windows shop and login have
been checked.

Frappe installation requirements: https://docs.frappe.io/framework/user/en/installation

## Restoration requirements

Restore to a fresh supported environment using the exact app source and dependency
versions in the package. Do not clone the latest upstream code instead. Recreate
the Python/Node dependencies for the target machine and link the app public asset
directories. Existing compiled assets are included; copying them does not require
rebuilding the interface.

For manual restoration, use the database and both file archives only on a new,
isolated target site. Adapt database socket/host/port and
Redis paths to that machine; macOS paths in the saved configuration cannot be used
as runtime paths. Preserve the original site encryption key and current login
hashes. Do not run the initial shop setup again or reset the Administrator password.

The export reads the database dump to completion and checks all source tables and
login records. Package files have SHA-256 checksums. No second-machine restore or
Windows runtime has been tested; backup verification is not a restoration test.

## Make another backup on this Mac

Start the app and run, from the project folder:

```bash
PATH="$PWD/.local/mariadb-build/client:$PATH" \
  bench/env/bin/python bench/apps/moniepoint_pos/scripts/export_transfer_backup.py \
  --project-root "$PWD"
```

This creates a new private timestamped folder and ZIP under `backups`. It does
not remove earlier backups or change shop records. Avoid editing records or files
while exporting.
