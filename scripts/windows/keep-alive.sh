#!/usr/bin/env bash
set -euo pipefail
systemctl start mariadb nginx k3ls.target
exec /usr/bin/sleep infinity
