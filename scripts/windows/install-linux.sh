#!/usr/bin/env bash
set -euo pipefail
umask 077
K3LS_PACKAGE="$(cd "$1" && pwd)"
K3LS_WINDOWS="$(cd "${2:-$K3LS_PACKAGE/windows}" && pwd)"
K3LS_ROOT=/opt/k3ls
K3LS_BENCH=/opt/k3ls/project/bench
K3LS_PACKAGE_ID="$(sha256sum "$K3LS_PACKAGE/manifest.json" | cut -d' ' -f1)"
[[ $EUID -eq 0 ]] || { echo "Run through Install K3LS.vbs." >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo "64-bit Intel/AMD Linux is required." >&2; exit 1; }
[[ $(ps -p 1 -o comm=) == systemd ]] || { echo "WSL systemd is not active. Restart this distribution." >&2; exit 1; }
if [[ -f "$K3LS_ROOT/.complete" ]]; then
    [[ $(<"$K3LS_ROOT/.package-id") == "$K3LS_PACKAGE_ID" ]] || { echo "Another backup is already installed." >&2; exit 1; }
    install -m 0755 "$K3LS_WINDOWS/keep-alive.sh" "$K3LS_ROOT/keep-alive.sh"
    systemctl start mariadb nginx k3ls.target
    exit 0
fi
if [[ -e "$K3LS_ROOT" ]]; then
    [[ -f "$K3LS_ROOT/.package-id" && $(<"$K3LS_ROOT/.package-id") == "$K3LS_PACKAGE_ID" ]] || { echo "Existing K3LS files will not be overwritten." >&2; exit 1; }
else
    mkdir -p "$K3LS_ROOT"
    printf '%s\n' "$K3LS_PACKAGE_ID" > "$K3LS_ROOT/.package-id"
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git build-essential pkg-config libmariadb-dev libmariadb-dev-compat \
    mariadb-server mariadb-client redis-server nginx python3 python3-venv python3-dev \
    libffi-dev libssl-dev libjpeg-dev zlib1g-dev libpango-1.0-0 libpangoft2-1.0-0 \
    libharfbuzz-subset0 libfontconfig1 fonts-dejavu-core xz-utils gzip file
if ! id k3ls >/dev/null 2>&1; then useradd --create-home --shell /bin/bash k3ls; fi
systemctl disable --now redis-server
install -m 0644 "$K3LS_WINDOWS/mariadb.cnf" /etc/mysql/mariadb.conf.d/60-k3ls.cnf
systemctl restart mariadb
mkdir -p "$K3LS_ROOT/bin" "$K3LS_ROOT/runtime" "$K3LS_ROOT/backup" "$K3LS_ROOT/project"
if [[ ! -x "$K3LS_ROOT/runtime/node/bin/node" ]]; then
    curl -fsSL https://nodejs.org/dist/v24.21.0/node-v24.21.0-linux-x64.tar.xz -o "$K3LS_ROOT/runtime/node.tar.xz"
    printf '%s  %s\n' fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6 "$K3LS_ROOT/runtime/node.tar.xz" | sha256sum -c -
    mkdir -p "$K3LS_ROOT/runtime/node"
    tar -xJf "$K3LS_ROOT/runtime/node.tar.xz" --strip-components=1 -C "$K3LS_ROOT/runtime/node"
fi
if [[ ! -x "$K3LS_ROOT/bin/uv" ]]; then
    curl -fsSL https://astral.sh/uv/install.sh -o "$K3LS_ROOT/runtime/install-uv.sh"
    UV_UNMANAGED_INSTALL="$K3LS_ROOT/bin" sh "$K3LS_ROOT/runtime/install-uv.sh"
fi
export PATH="$K3LS_ROOT/bin:$K3LS_ROOT/runtime/node/bin:/usr/bin:/bin"
export UV_PYTHON_INSTALL_DIR="$K3LS_ROOT/runtime/python"
export UV_TOOL_DIR="$K3LS_ROOT/runtime/tools"
export UV_TOOL_BIN_DIR="$K3LS_ROOT/bin"
uv python install 3.14.7
uv tool install --python 3.14.7 frappe-bench==5.31.0
if [[ ! -f "$K3LS_ROOT/.source-ready" ]]; then
    cp -a "$K3LS_PACKAGE/snapshot/." "$K3LS_ROOT/backup/"
    tar -xzf "$K3LS_ROOT/backup/project-source.tar.gz" -C "$K3LS_ROOT/project"
    mkdir -p "$K3LS_BENCH/sites/assets"
    tar -xzf "$K3LS_ROOT/backup/site-assets.tar.gz" -C "$K3LS_BENCH/sites/assets"
    touch "$K3LS_ROOT/.source-ready"
fi
# Runtime folders are not part of the source archive. Frappe opens both bench
# and site log files while connecting, before restore verification completes.
mkdir -p "$K3LS_BENCH/logs" "$K3LS_BENCH/config/pids" \
    "$K3LS_BENCH/sites/development.localhost/logs" \
    "$K3LS_BENCH/sites/development.localhost/locks" \
    "$K3LS_BENCH/sites/development.localhost/private/backups"
uv venv --python 3.14.7 --allow-existing "$K3LS_BENCH/env"
uv pip install --python "$K3LS_BENCH/env/bin/python" -r "$K3LS_ROOT/backup/python-requirements.txt"
uv pip install --python "$K3LS_BENCH/env/bin/python" --no-deps -e "$K3LS_BENCH/apps/frappe" -e "$K3LS_BENCH/apps/erpnext" -e "$K3LS_BENCH/apps/moniepoint_pos"
if [[ ! -x "$K3LS_ROOT/runtime/node/bin/yarn" ]]; then npm install --global yarn@1.22.22; fi
for K3LS_APP in frappe erpnext; do
    (cd "$K3LS_BENCH/apps/$K3LS_APP" && yarn install --frozen-lockfile --ignore-scripts --non-interactive)
done
# Only the existing compiled assets are used. No build, watcher, lint or tests run.
for K3LS_APP in frappe erpnext moniepoint_pos; do
    ln -sfn "$K3LS_BENCH/apps/$K3LS_APP/$K3LS_APP/public" "$K3LS_BENCH/sites/assets/$K3LS_APP"
done
ln -sfn ../../node_modules "$K3LS_BENCH/apps/frappe/frappe/public/node_modules"
install -m 0755 "$K3LS_WINDOWS/restore-linux.py" "$K3LS_ROOT/restore-linux.py"
"$K3LS_BENCH/env/bin/python" "$K3LS_ROOT/restore-linux.py" "$K3LS_ROOT"
chown -R k3ls:k3ls "$K3LS_ROOT/project" "$K3LS_ROOT/backup"
# Nginx reads public files as www-data. Keep configs, database backups and
# private uploads restricted to k3ls while allowing traversal to public assets.
chmod 0755 "$K3LS_ROOT/project" "$K3LS_BENCH" "$K3LS_BENCH/sites" "$K3LS_BENCH/apps"
chmod -R a+rX "$K3LS_BENCH/sites/assets"
for K3LS_APP in frappe erpnext moniepoint_pos; do
    chmod 0755 "$K3LS_BENCH/apps/$K3LS_APP" "$K3LS_BENCH/apps/$K3LS_APP/$K3LS_APP"
    chmod -R a+rX "$K3LS_BENCH/apps/$K3LS_APP/$K3LS_APP/public"
done
chmod -R a+rX "$K3LS_BENCH/apps/frappe/node_modules"
chmod 0755 "$K3LS_BENCH/sites/development.localhost"
chmod -R a+rX "$K3LS_BENCH/sites/development.localhost/public"
chmod 0700 "$K3LS_BENCH/sites/development.localhost/private"
chmod 0755 "$K3LS_ROOT" "$K3LS_ROOT/runtime" "$K3LS_ROOT/bin"
chmod -R a+rX "$K3LS_ROOT/runtime" "$K3LS_ROOT/bin"
chown -R k3ls:k3ls "$K3LS_BENCH/logs" "$K3LS_BENCH/config"
cd "$K3LS_BENCH"
bench setup redis
chown -R k3ls:k3ls "$K3LS_BENCH/config"
for K3LS_FILE in "$K3LS_WINDOWS"/units/*; do install -m 0644 "$K3LS_FILE" /etc/systemd/system/; done
install -m 0755 "$K3LS_WINDOWS/keep-alive.sh" "$K3LS_ROOT/keep-alive.sh"
install -m 0644 "$K3LS_WINDOWS/nginx.conf" /etc/nginx/sites-available/k3ls
ln -sfn /etc/nginx/sites-available/k3ls /etc/nginx/sites-enabled/k3ls
systemctl daemon-reload
systemctl enable mariadb nginx k3ls.target
systemctl restart nginx
systemctl start k3ls.target
for K3LS_ATTEMPT in {1..60}; do
    if curl -fsS http://127.0.0.1:8000/login >/dev/null; then
        touch "$K3LS_ROOT/.complete"
        echo "K3LS is running at http://localhost:8000. Existing shop logins are preserved."
        exit 0
    fi
    sleep 1
done
echo "Installed, but the app did not respond. Run: journalctl -u k3ls-web -n 40" >&2
exit 1
