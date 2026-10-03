#!/usr/bin/env python3
"""Export the K3LS site and its exact source trees without changing site records."""

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def source_filter(info):
    parts = Path(info.name).parts
    if any(part in {"node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
           for part in parts):
        return None
    if info.name.endswith((".pyc", ".pyo", ".DS_Store")):
        return None
    if ".git" in parts and ("hooks" in parts or info.name.endswith("index.lock")):
        return None
    if not (info.isfile() or info.isdir() or info.issym()):
        return None
    return info


def archive_sources(output, entries):
    with tarfile.open(output, "w:gz") as archive:
        for source, name in entries:
            if source.exists():
                archive.add(source, arcname=name, filter=source_filter)


def site_summary(frappe):
    doctypes = ["Company", "User", "Item", "Item Price", "Account", "Bank", "Bank Account", "Mode of Payment", "Customer", "Supplier", "POS Profile",
                "POS Invoice", "Sales Invoice", "Purchase Invoice", "K3LS Repair"]
    auth_rows = frappe.db.sql(
        "select doctype, name, fieldname, password, encrypted from `__Auth` "
        "order by doctype, name, fieldname", as_dict=True)
    return {
        "installed_apps": frappe.get_installed_apps(),
        "versions": {app: frappe.get_module(app).__version__ for app in frappe.get_installed_apps()},
        "record_counts": {doctype: frappe.db.count(doctype) for doctype in doctypes},
        "tables": sorted(frappe.db.get_tables()),
        "auth_record_count": len(auth_rows),
        "auth_records_sha256": hashlib.sha256(
            json.dumps(auth_rows, sort_keys=True, default=str).encode()).hexdigest(),
        "accounts": frappe.get_all("User", fields=["name", "full_name", "enabled", "user_type"],
                                   order_by="name"),
    }


def verify_database(path, expected_tables):
    table_names = set()
    has_auth_data = False
    complete = False
    with gzip.open(path, "rt", errors="strict") as handle:
        for line in handle:
            match = re.search(r"CREATE (?:TABLE|SEQUENCE)(?: IF NOT EXISTS)? `([^`]+)`", line)
            if match:
                table_names.add(match.group(1))
            if line.startswith("INSERT INTO `__Auth`"):
                has_auth_data = True
            if line.startswith("-- Dump completed on"):
                complete = True
    missing = set(expected_tables) - table_names
    if missing or not has_auth_data or not complete:
        raise RuntimeError(f"Incomplete database backup. Missing tables: {sorted(missing)}, "
                           f"login records present: {has_auth_data}, dump complete: {complete}")
    return {"table_count": len(table_names), "login_records_present": True, "dump_completed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--site", default="development.localhost")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve(strict=True)
    bench = root / "bench"
    if not re.fullmatch(r"[A-Za-z0-9.-]+", args.site):
        parser.error("Site name must contain only letters, numbers, dots and hyphens.")
    site_dir = bench / "sites" / args.site
    if not (site_dir / "site_config.json").is_file():
        parser.error("The site's configuration was not found.")
    os.umask(0o077)
    stamp = datetime.now(ZoneInfo("Europe/London")).strftime("%Y%m%d-%H%M%S")
    name = f"K3LS-transfer-{stamp}"
    output_dir = (args.output_dir or root / "backups").resolve()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    package = output_dir / name
    package.mkdir(mode=0o700)
    snapshot = package / "snapshot"
    snapshot.mkdir(mode=0o700)
    temporary = Path(tempfile.mkdtemp(prefix="k3ls-export-"))
    previous_cwd = Path.cwd()

    try:
        import frappe
        from frappe.utils.backups import BackupGenerator

        os.chdir(bench / "sites")
        frappe.init(site=args.site)
        frappe.connect()
        if frappe.get_system_settings("encrypt_backup"):
            raise RuntimeError("Encrypted site backups need a separate export procedure. "
                               "No encryption setting was changed.")
        before = site_summary(frappe)
        backup = BackupGenerator(
            frappe.conf.db_name, frappe.conf.db_user, frappe.conf.db_password,
            db_socket=frappe.conf.db_socket, db_host=frappe.conf.db_host,
            db_port=frappe.conf.db_port, db_type=frappe.conf.db_type,
            backup_path_db=str(temporary / "database.sql.gz"),
            backup_path_files=str(temporary / "public-files.tar"),
            backup_path_private_files=str(temporary / "private-files.tar"),
            backup_path_conf=str(temporary / "site_config.json"),
            ignore_conf=True)
        print("Exporting the complete database and public/private files...", flush=True)
        backup.get_backup(force=True, ignore_files=False)
        verification = verify_database(temporary / "database.sql.gz", before["tables"])
        for filename in ("database.sql.gz", "public-files.tar", "private-files.tar", "site_config.json"):
            shutil.copy2(temporary / filename, snapshot / filename)
        for filename in ("public-files.tar", "private-files.tar"):
            with tarfile.open(snapshot / filename, "r") as archive:
                for member in archive:
                    if member.isfile():
                        handle = archive.extractfile(member)
                        while handle.read(1024 * 1024):
                            pass
        after = site_summary(frappe)
        if before != after:
            raise RuntimeError("Site records changed during export. This package is incomplete; "
                               "rerun when no one is editing the shop.")
        frappe.destroy()
        os.chdir(previous_cwd)
        shutil.copy2(bench / "sites/common_site_config.json", snapshot / "common_site_config.json")

        repositories = {}
        entries = []
        for app in before["installed_apps"]:
            repo = bench / "apps" / app
            repositories[app] = {
                "commit": git_output(repo, "rev-parse", "HEAD").decode().strip(),
                "branch": git_output(repo, "branch", "--show-current").decode().strip(),
                "working_tree": git_output(repo, "status", "--short").decode(),
                "shallow": git_output(repo, "rev-parse", "--is-shallow-repository").decode().strip() == "true",
            }
            patch = snapshot / "working-tree" / f"{app}.patch"
            patch.parent.mkdir(exist_ok=True)
            patch.write_bytes(git_output(repo, "diff", "HEAD", "--binary"))
            entries.append((repo, f"bench/apps/{app}"))

        for filename in ("README.md", "start.sh", "bench-local.py"):
            entries.append((root / filename, filename))
        for filename in ("Procfile", "Procfile.runtime", "patches.txt", "sites/apps.txt", "sites/apps.json"):
            entries.append((bench / filename, f"bench/{filename}"))
        entries.append((root / "docs", "docs"))
        for repo in ("frappe", "erpnext"):
            entries.append((root / repo, f"original-checkouts/{repo}"))
        print("Archiving source, local changes, existing built assets and Git history...", flush=True)
        archive_sources(snapshot / "project-source.tar.gz", entries)
        with tarfile.open(snapshot / "site-assets.tar.gz", "w:gz") as archive:
            for child in sorted((bench / "sites/assets").iterdir()):
                if not child.is_symlink():
                    archive.add(child, arcname=child.name, filter=source_filter)
        frozen = subprocess.check_output([
            shutil.which("uv") or str(Path.home() / ".local/bin/uv"), "pip", "freeze",
            "--python", str(bench / "env/bin/python")], text=True)
        requirements = "\n".join(line for line in frozen.splitlines() if not line.startswith("-e ")) + "\n"
        (snapshot / "python-requirements.txt").write_text(requirements)
        write_json(snapshot / "site-state.json", before)
        write_json(snapshot / "code-state.json", repositories)
        write_json(snapshot / "export-info.json", {
            "created_at": datetime.now(ZoneInfo("Europe/London")).isoformat(),
            "site": args.site,
            "source_platform": sys.platform,
            "python": "3.14.7",
            "node": "24.21.0",
            "bench": "5.31.0",
            "mariadb": "11.8.9",
            "database_verification": verification,
            "preserved": ["complete database", "login password hashes", "encrypted credentials",
                          "site encryption key", "public and private files", "exact working trees",
                          "available Git history", "prebuilt application assets"],
            "excluded": ["macOS executable dependencies", "live MariaDB data directory",
                         "Redis queues and session cache", "node_modules", "Python virtual environments"],
            "restore_status": "Windows WSL2 installer included. Not yet executed on Windows.",
        })
        client_files = [
            Path.home() / "Downloads/K3LS_BUSINESS_MANAGEMENT_CONTROL_SYSTEM_FINAL_WITH_AUTO_IDS_LOGO_WATERMARKED.xlsx",
            Path.home() / "Downloads/images-removebg-preview.png",
        ]
        for path in client_files:
            if path.is_file():
                target = snapshot / "client-source"
                target.mkdir(exist_ok=True)
                shutil.copy2(path, target / path.name)
        print("Archiving the existing walkthrough project without rendering it...", flush=True)
        archive_sources(snapshot / "walkthrough-project.tar.gz", [(root / "videos", "videos")])
        script_root = Path(__file__).resolve().parent
        shutil.copy2(script_root / "verify-transfer.ps1", package / "verify-transfer.ps1")
        shutil.copy2(script_root / "Verify Backup.cmd", package / "Verify Backup.cmd")
        shutil.copytree(script_root / "windows", package / "windows")
        shutil.copy2(script_root / "windows/Setup K3LS.cmd", package / "Setup K3LS.cmd")
        shutil.copy2(script_root.parent / "docs/transfer-backup.md", package / "READ ME.md")
        write_json(package / "manifest.json", {
            "format": "k3ls-transfer-v1", "site": args.site,
            "created_at": datetime.now(ZoneInfo("Europe/London")).isoformat(),
            "files": [{"path": str(path.relative_to(package)), "bytes": path.stat().st_size,
                       "sha256": sha256(path)} for path in sorted(package.rglob("*")) if path.is_file()],
        })
        for path in package.rglob("*"):
            if path.is_file():
                path.chmod(0o600)
            elif path.is_dir():
                path.chmod(0o700)
        (package / "COMPLETE").write_text("Export complete. Verify files against manifest.json.\n")
        archive_path = output_dir / f"{name}.zip"
        # The large payload files are already compressed. Store them unchanged.
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=f"{name}/{path.relative_to(package).as_posix()}")
        archive_path.chmod(0o600)
        checksum = sha256(archive_path)
        (output_dir / f"{archive_path.name}.sha256").write_text(f"{checksum}  {archive_path.name}\n")
        print(json.dumps({"package": str(package), "archive": str(archive_path),
                          "sha256": checksum, "tables": verification["table_count"],
                          "users": before["record_counts"]["User"]}, indent=2), flush=True)
    finally:
        os.chdir(previous_cwd)
        # Only the temporary directory created by this invocation is removed.
        shutil.rmtree(temporary)


if __name__ == "__main__":
    main()
