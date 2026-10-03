"""Package corrected installer scripts for the unchanged 174403 transfer."""

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    original = args.package_root.resolve(strict=True)
    expected_manifest = "519533ad061c79bde49e2782f63f564952955574aafe832c095d4d93cfb42d30"
    expected_verifier = "ef7a26396520587ff5485680d7ff16903f05ae1b7a398da6f72d1d163f7cdee8"
    if sha256(original / "manifest.json") != expected_manifest or sha256(original / "verify-transfer.ps1") != expected_verifier:
        raise SystemExit("This update requires the unchanged 20261003-174403 backup.")
    manifest = json.loads((original / "manifest.json").read_text())
    for entry in manifest["files"]:
        path = (original / entry["path"]).resolve(strict=True)
        if not path.is_relative_to(original) or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise SystemExit(f"Original backup file changed: {entry['path']}")
    scripts = Path(__file__).resolve().parent
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    name = "K3LS-Installer-Update-20261003"
    destination = output / name
    archive_path = output / f"{name}.zip"
    if destination.exists() or archive_path.exists():
        raise SystemExit("Installer update already exists. Existing files were preserved.")
    destination.mkdir(mode=0o700)
    shutil.copytree(scripts / "windows", destination / "windows")
    for source in (scripts / "windows-update").iterdir():
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    update_manifest = {
        "format": "k3ls-installer-update-v1",
        "backup_folder": original.name,
        "backup_manifest_sha256": expected_manifest,
        "backup_verifier_sha256": expected_verifier,
        "files": [
            {"path": path.relative_to(destination).as_posix(),
             "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(destination.rglob("*")) if path.is_file()
        ],
    }
    (destination / "update-manifest.json").write_text(json.dumps(update_manifest, indent=2) + "\n")
    for path in destination.rglob("*"):
        path.chmod(0o600 if path.is_file() else 0o700)
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                archive.write(path, f"{name}/{path.relative_to(destination).as_posix()}")
    archive_path.chmod(0o600)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise SystemExit("Installer update ZIP integrity check failed.")
    checksum = sha256(archive_path)
    archive_path.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive_path.name}\n")
    print(json.dumps({"archive": str(archive_path), "bytes": archive_path.stat().st_size,
                      "sha256": checksum}, indent=2))


if __name__ == "__main__":
    main()
