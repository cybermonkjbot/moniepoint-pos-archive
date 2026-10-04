"""Export a code-only login update for the installed Windows K3LS shop."""

import argparse
import hashlib
import json
import re
import shutil
import tarfile
import zipfile
from pathlib import Path

BACKUP_ID = '519533ad061c79bde49e2782f63f564952955574aafe832c095d4d93cfb42d30'
RELEASE = 'K3LS-Shop-Update-20261004-v4'
APP_FILES = (
    'moniepoint_pos/www/__init__.py',
    'moniepoint_pos/www/login.py',
    'moniepoint_pos/www/login.html',
    'moniepoint_pos/public/css/k3ls_login.css',
    'moniepoint_pos/public/js/k3ls_login.js',
    'moniepoint_pos/public/images/k3ls-loading-logo.png',
    'moniepoint_pos/hooks.py',
    'moniepoint_pos/security.py',
    'moniepoint_pos/user_security.py',
    'moniepoint_pos/shop_ui.py',
    'moniepoint_pos/list_search.py',
    'moniepoint_pos/public/js/k3ls_security.js',
    'moniepoint_pos/public/js/k3ls_shop_ui.js',
    'moniepoint_pos/public/js/k3ls_list.js',
    'moniepoint_pos/public/css/k3ls_shop_ui.css',
    'moniepoint_pos/moniepoint_pos/page/shop_accounts/shop_accounts.js',
    'moniepoint_pos/moniepoint_pos/page/shop_profit/shop_profit.js',
    'moniepoint_pos/www/update-password.html',
    'moniepoint_pos/www/update_password.py',
    'moniepoint_pos/moniepoint_pos/doctype/k3ls_recovery_code/__init__.py',
    'moniepoint_pos/moniepoint_pos/doctype/k3ls_recovery_code/k3ls_recovery_code.py',
    'moniepoint_pos/moniepoint_pos/doctype/k3ls_recovery_code/k3ls_recovery_code.json',
)


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    backup = args.package_root.resolve(strict=True)
    if digest(backup / 'manifest.json') != BACKUP_ID:
        raise SystemExit('This update requires the matching 20261003-174403 backup.')
    backup_manifest = json.loads((backup / 'manifest.json').read_text())
    archive_file = backup / 'snapshot/project-source.tar.gz'
    entry = next(item for item in backup_manifest['files'] if item['path'] == 'snapshot/project-source.tar.gz')
    if archive_file.stat().st_size != entry['bytes'] or digest(archive_file) != entry['sha256']:
        raise SystemExit('The original source archive changed.')
    script_root = Path(__file__).resolve().parent
    app = script_root.parent
    before = {path: None for path in APP_FILES}
    versions = {}
    app_prefix = 'bench/apps/moniepoint_pos/'
    version_paths = {f'bench/apps/{name}/{name}/__init__.py': name for name in ('frappe', 'erpnext', 'moniepoint_pos')}
    # Read exact original file hashes without extracting the original source tree.
    with tarfile.open(archive_file, 'r|gz') as source:
        for member in source:
            name = member.name
            relative = name[len(app_prefix):] if name.startswith(app_prefix) else None
            if name not in version_paths and relative not in before:
                continue
            if not member.isfile():
                raise SystemExit('Unexpected source archive file type: ' + name)
            data = source.extractfile(member).read()
            if relative in before:
                before[relative] = hashlib.sha256(data).hexdigest()
            if name in version_paths:
                match = re.search(r'^__version__\s*=\s*[\'"]([^\'"]+)', data.decode(), re.MULTILINE)
                if not match:
                    raise SystemExit('Could not read original app version.')
                versions[version_paths[name]] = match.group(1)
    if set(versions) != {'frappe', 'erpnext', 'moniepoint_pos'}:
        raise SystemExit('Original app versions are incomplete.')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / RELEASE
    zip_path = output / (RELEASE + '.zip')
    if destination.exists() or zip_path.exists():
        raise SystemExit('This release already exists. Existing packages were preserved.')
    destination.mkdir(mode=0o700)
    for file in (script_root / 'app-update').iterdir():
        if file.is_file():
            shutil.copy2(file, destination / file.name)
    changes = []
    for path in APP_FILES:
        source = app / path
        target = destination / 'payload' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        allowed_before = [before[path]]
        for previous_release in ('K3LS-Login-Update-20261004-v1', 'K3LS-Account-Update-20261004-v2', 'K3LS-Account-Update-20261004-v3'):
            previous = output / previous_release / 'payload' / path
            if previous.is_file() and digest(previous) not in allowed_before:
                allowed_before.append(digest(previous))
        changes.append({'path': path, 'before_sha256': before[path], 'allowed_before_sha256': allowed_before, 'sha256': digest(target)})
    manifest = {
        'format': 'k3ls-app-update-v1',
        'release': RELEASE,
        'backup_manifest_sha256': BACKUP_ID,
        'app_versions': versions,
        'configure_security': True,
        'changes': changes,
        'files': [
            {'path': path.relative_to(destination).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)}
            for path in sorted(destination.rglob('*')) if path.is_file()
        ],
    }
    (destination / 'update-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                archive.write(path, RELEASE + '/' + path.relative_to(destination).as_posix())
    zip_path.chmod(0o600)
    # Archive integrity is part of export, not a code build or test run.
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise SystemExit('The update ZIP failed its integrity check.')
    checksum = digest(zip_path)
    zip_path.with_suffix('.zip.sha256').write_text(checksum + '  ' + zip_path.name + '\n')
    print(json.dumps({'archive': str(zip_path), 'bytes': zip_path.stat().st_size, 'sha256': checksum}, indent=2))


if __name__ == '__main__':
    main()
