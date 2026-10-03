# Resume K3LS installation

Extract this ZIP inside the existing `K3LS-transfer-20261003-170202` folder.
Open the new `K3LS-Windows-Repair-20261003` folder and double-click `Resume K3LS.vbs`.
Approve the administrator prompt. PowerShell stays open and saves the installation
log in the original transfer's `installation-logs` folder.

This repair keeps the original transfer, checks its unchanged manifest and files,
and uses corrected installer scripts from this separate folder. It resumes only
the `K3LS-Shop` distribution belonging to that backup. Other Ubuntu distributions,
shop passwords and company records are not reset.

The fix passes Linux commands directly through `wsl --exec`, copies a valid Linux
startup configuration, and preserves the previous configuration at
`/etc/wsl.conf.k3ls-before-repair`. It does not force a WSL update if WSL 0.67.6 or
newer is already installed. Internet access is still needed for Linux dependencies.

Wait for `K3LS is installed` and open `http://localhost:8000` with the existing
shop login. If setup stops, send the final error and installation log.

The updated installer has been reviewed in source. Windows execution and the
complete restoration still need confirmation on the receiving PC.
