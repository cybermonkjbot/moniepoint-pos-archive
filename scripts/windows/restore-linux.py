#!/usr/bin/env python3
"""Restore only into the isolated new K3LS WSL instance, preserving authentication."""
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1]).resolve()
if root != Path("/opt/k3ls"):
    raise SystemExit("Unexpected target. Only /opt/k3ls is supported.")
backup = root / "backup"
bench = root / "project/bench"
state = json.loads((backup / "site-state.json").read_text())
source = json.loads((backup / "site_config.json").read_text())
sites = bench / "sites"
site = sites / "development.localhost"
site.mkdir(parents=True, exist_ok=True)
marker = root / ".database-restored"
owned = root / ".database-owned"
os.umask(0o077)
db_name = "k3ls_shop"
db_user = "k3ls_shop"
if not source.get("encryption_key"):
    raise SystemExit("Backup encryption key is missing. Do not reset it.")

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")

if not marker.exists():
    exists = subprocess.check_output(["mariadb", "--batch", "--skip-column-names", "-e",
        "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='k3ls_shop'"], text=True).strip()
    if exists and not owned.exists():
        raise SystemExit("Existing database will not be overwritten.")
    config_path = site / "site_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        password = config.get("db_password")
    else:
        import secrets
        password = secrets.token_hex(32)
    if not password or not re.fullmatch(r"[0-9a-f]{64}", password):
        raise SystemExit("Target database configuration is not from this installer.")
    config = dict(source)
    for key in ("db_host", "db_port", "db_socket", "db_user", "admin_password"):
        config.pop(key, None)
    config.update(db_name=db_name, db_user=db_user, db_password=password,
        db_type="mariadb", db_socket="/run/mysqld/mysqld.sock", developer_mode=0,
        host_name="http://localhost:8000", maintenance_mode=0)
    write_json(config_path, config)
    common = json.loads((backup / "common_site_config.json").read_text())
    for key in ("db_host", "db_port", "db_socket", "frappe_user", "file_watcher_port"):
        common.pop(key, None)
    common.update(redis_cache="redis://127.0.0.1:13000", redis_queue="redis://127.0.0.1:11000",
        redis_socketio="redis://127.0.0.1:11000", socketio_port=9000, webserver_port=8001,
        serve_default_site=True, default_site="development.localhost", live_reload=False,
        restart_supervisor_on_update=False, restart_systemd_on_update=False)
    write_json(sites / "common_site_config.json", common)
    (sites / "currentsite.txt").write_text("development.localhost\n")
    owned.touch()
    sql = ("CREATE DATABASE IF NOT EXISTS `k3ls_shop` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        f"CREATE USER IF NOT EXISTS 'k3ls_shop'@'localhost' IDENTIFIED BY '{password}';"
        f"ALTER USER 'k3ls_shop'@'localhost' IDENTIFIED BY '{password}';"
        "GRANT ALL PRIVILEGES ON `k3ls_shop`.* TO 'k3ls_shop'@'localhost'; FLUSH PRIVILEGES;")
    subprocess.run(["mariadb"], input=sql, text=True, check=True)
    # Send credentials via a private defaults file, never through command arguments.
    with tempfile.NamedTemporaryFile(mode="w", prefix="k3ls-db-", delete=True) as credentials:
        credentials.write(f"[client]\nuser={db_user}\npassword={password}\nsocket=/run/mysqld/mysqld.sock\n")
        credentials.flush()
        with gzip.open(backup / "database.sql.gz", "rb") as dump:
            process = subprocess.Popen(["mariadb", f"--defaults-extra-file={credentials.name}", db_name], stdin=subprocess.PIPE)
            try:
                for line in dump:
                    if b"enable the sandbox mode" in line:
                        continue
                    process.stdin.write(line)
                process.stdin.close()
                if process.wait() != 0:
                    raise RuntimeError("Database restore failed. No completion marker was written.")
            except BaseException:
                process.terminate()
                process.wait()
                raise
    marker.touch()

def uploaded_members(archive, section):
    members = []
    for member in archive:
        path = PurePosixPath(member.name)
        parts = path.parts
        if path.is_absolute() or ".." in parts or "\\" in member.name or len(parts) < 3 or parts[:2] != ("development.localhost", section):
            raise RuntimeError(f"Unexpected uploaded-file archive path: {member.name!r}")
        if not (member.isfile() or member.isdir()):
            raise RuntimeError(f"Unsupported uploaded-file archive entry: {member.name!r}")
        # macOS tar emits AppleDouble records beside their actual files,
        # including a ._files record outside the uploaded-files directory.
        # Ignore only records with the AppleDouble magic/version header and
        # a corresponding legal uploaded-file path. Never extract metadata.
        if member.isfile() and parts[-1].startswith("._"):
            counterpart = (*parts[:-1], parts[-1][2:])
            if counterpart[2] == "files" and counterpart[-1]:
                with archive.extractfile(member) as contents:
                    if contents.read(8) == b"\x00\x05\x16\x07\x00\x02\x00\x00":
                        continue
        if parts[2] != "files" or (len(parts) == 3 and not member.isdir()):
            raise RuntimeError(f"Unexpected uploaded-file archive path: {member.name!r}")
        member.name = str(PurePosixPath(*parts[1:]))
        members.append(member)
    return members


# Validate both archives before extracting either. The data filter still
# rejects paths escaping the target through an existing symlink.
for archive_name, section in (("public-files.tar", "public"), ("private-files.tar", "private")):
    with tarfile.open(backup / archive_name, "r") as archive:
        uploaded_members(archive, section)
for archive_name, section in (("public-files.tar", "public"), ("private-files.tar", "private")):
    (site / section / "files").mkdir(parents=True, exist_ok=True)
    with tarfile.open(backup / archive_name, "r") as archive:
        archive.extractall(site, members=uploaded_members(archive, section), filter="data")

os.chdir(sites)
sys.path[:0] = [str(bench / "apps" / app) for app in state["installed_apps"]]
import frappe
frappe.init(site="development.localhost")
frappe.connect()
try:
    versions = {app: frappe.get_module(app).__version__ for app in frappe.get_installed_apps()}
    if versions != state["versions"]:
        raise RuntimeError("Restored app versions do not match the backup.")
    tables = sorted(frappe.db.get_tables())
    if tables != state["tables"]:
        raise RuntimeError("Restored database tables do not match the backup.")
    counts = {doctype: frappe.db.count(doctype) for doctype in state["record_counts"]}
    if counts != state["record_counts"]:
        raise RuntimeError("Restored record counts do not match the backup.")
    auth = frappe.db.sql("select doctype, name, fieldname, password, encrypted from `__Auth` order by doctype, name, fieldname", as_dict=True)
    fingerprint = hashlib.sha256(json.dumps(auth, sort_keys=True, default=str).encode()).hexdigest()
    if fingerprint != state["auth_records_sha256"]:
        raise RuntimeError("Restored login or encrypted credentials do not match the backup.")
    if frappe.conf.encryption_key != source["encryption_key"]:
        raise RuntimeError("Site encryption key changed.")
    print("Restored app versions, database tables, record counts and authentication records match the backup.")
finally:
    frappe.destroy()
