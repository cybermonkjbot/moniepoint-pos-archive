"""Apply a checked, code-only patch to the existing K3LS Windows installation."""

import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

ROOT = Path('/opt/k3ls')
BENCH = ROOT / 'project/bench'
APP = BENCH / 'apps/moniepoint_pos'
SITE = 'development.localhost'
PACKAGE_ID = '519533ad061c79bde49e2782f63f564952955574aafe832c095d4d93cfb42d30'


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def relative_path(value):
    path = PurePosixPath(value)
    if not value or '\\' in value or path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise RuntimeError('Invalid update file path.')
    if any(part.startswith('.') for part in path.parts):
        raise RuntimeError('Hidden files cannot be updated.')
    return path


def inside(root, value):
    relative_path(value)
    path = root / value
    # Never follow links in an app path, even when they point inside the app.
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise RuntimeError('Update path contains a symbolic link: ' + value)
    if not path.resolve().is_relative_to(root.resolve()):
        raise RuntimeError('Update path escaped its folder.')
    return path


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def clear_cache():
    run('/usr/sbin/runuser', '-u', 'k3ls', '--', '/usr/bin/env',
        'PATH=/opt/k3ls/bin:/opt/k3ls/runtime/node/bin:/usr/bin:/bin',
        '/opt/k3ls/bin/bench', '--site', SITE, 'clear-cache', cwd=BENCH)


def request(path):
    req = Request('http://127.0.0.1:8000' + path, headers={'Host': SITE, 'Accept-Encoding': 'identity'})
    with urlopen(req, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError('The shop did not return HTTP 200.')
        return response.read()


def health(manifest=None):
    last_error = None
    for attempt in range(20):
        try:
            page = request('/login')
            if b'id="login_password"' not in page:
                raise RuntimeError('The shop login did not load.')
            if manifest:
                if b'k3ls-signin-shell' not in page:
                    raise RuntimeError('The new login page did not load.')
                for entry in manifest['changes']:
                    prefix = 'moniepoint_pos/public/'
                    if entry['path'].startswith(prefix):
                        asset = request('/assets/moniepoint_pos/' + entry['path'][len(prefix):])
                        if hashlib.sha256(asset).hexdigest() != entry['sha256']:
                            raise RuntimeError('An updated login asset did not load.')
            return
        except Exception as error:
            last_error = error
            if attempt != 19:
                time.sleep(2)
    raise RuntimeError('Shop server check failed: ' + str(last_error))


def replace_file(source, target, owner):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.k3ls-update-', delete=False) as output:
        temporary = Path(output.name)
        with source.open('rb') as incoming:
            shutil.copyfileobj(incoming, output)
        output.flush()
        os.fsync(output.fileno())
    try:
        os.chmod(temporary, 0o644)
        os.chown(temporary, owner.pw_uid, owner.pw_gid)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply(package, manifest_hash):
    if os.geteuid() != 0:
        raise RuntimeError('Open Update K3LS.vbs to apply this update.')
    if not (ROOT / '.complete').is_file() or (ROOT / '.package-id').read_text().strip() != PACKAGE_ID:
        raise RuntimeError('The matching K3LS installation is not complete.')
    if APP.is_symlink() or not APP.is_dir():
        raise RuntimeError('Unexpected installed app folder.')
    manifest_path = package / 'update-manifest.json'
    if digest(manifest_path) != manifest_hash:
        raise RuntimeError('The update manifest changed during launch.')
    manifest = json.loads(manifest_path.read_text())
    if manifest['format'] != 'k3ls-app-update-v1' or manifest['backup_manifest_sha256'] != PACKAGE_ID:
        raise RuntimeError('This update does not match the installed shop.')
    release = manifest['release']
    if not re.fullmatch(r'[A-Za-z0-9-]{1,80}', release):
        raise RuntimeError('Invalid update name.')
    # This patch changes no schema or dependency and never runs migrate/build.
    if set(manifest['app_versions']) != {'frappe', 'erpnext', 'moniepoint_pos'}:
        raise RuntimeError('The update app versions are incomplete.')
    for app, version in manifest['app_versions'].items():
        if app not in ('frappe', 'erpnext', 'moniepoint_pos'):
            raise RuntimeError('Unexpected app version check.')
        source = (BENCH / 'apps' / app / app / '__init__.py').read_text()
        found = re.search(r'^__version__\s*=\s*[\'"]([^\'"]+)', source, re.MULTILINE)
        if not found or found.group(1) != version:
            raise RuntimeError('Installed app version changed: ' + app)
    owner = pwd.getpwnam('k3ls')
    checked_files = {}
    for entry in manifest['files']:
        path = inside(package, entry['path'])
        if entry['path'] in checked_files or not path.is_file() or path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise RuntimeError('Missing or changed update file: ' + entry['path'])
        checked_files[entry['path']] = entry
    changes = []
    seen = set()
    for entry in manifest['changes']:
        value = entry['path']
        if value in seen or not value.startswith(('moniepoint_pos/www/', 'moniepoint_pos/public/')):
            raise RuntimeError('This updater only accepts login-page and public-asset changes.')
        seen.add(value)
        target = inside(APP, value)
        source = inside(package, 'payload/' + value)
        listed = checked_files.get('payload/' + value)
        if not listed or listed['sha256'] != entry['sha256']:
            raise RuntimeError('Update payload does not match the manifest.')
        if target.exists() and not target.is_file():
            raise RuntimeError('App file path is a folder: ' + value)
        current = digest(target) if target.exists() else None
        if current != entry['sha256'] and current != entry['before_sha256']:
            raise RuntimeError('App file has a different local change: ' + value)
        changes.append((entry, source, target, current))
    if not changes:
        raise RuntimeError('The update contains no app files.')
    # Serialize updates and keep rollback code outside the site's data folders.
    saved_root = ROOT / 'updates'
    saved_root.mkdir(mode=0o700, exist_ok=True)
    with (saved_root / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another K3LS update is running.') from None
        # Repeat preflight under the lock before saving any current app files.
        for entry, source, target, current in changes:
            now = digest(target) if target.exists() else None
            if now != current:
                raise RuntimeError('App code changed during preflight.')
        pending = [change for change in changes if change[3] != change[0]['sha256']]
        if not pending:
            run('/usr/bin/systemctl', 'start', 'k3ls-web')
            health(manifest)
            print('This update is already installed. The login server check passed.', flush=True)
            return
        saved = Path(tempfile.mkdtemp(prefix=release + '-', dir=saved_root))
        staged = saved / 'incoming'
        originals = saved / 'previous'
        created_folders = []
        for entry, source, target, current in pending:
            parent = target.parent
            while parent != APP and not parent.exists():
                if parent not in created_folders:
                    created_folders.append(parent)
                parent = parent.parent
        for entry, source, target, current in pending:
            stage = staged / entry['path']
            stage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, stage)
            if digest(stage) != entry['sha256']:
                raise RuntimeError('The update payload changed while staging.')
            if current is not None:
                old = originals / entry['path']
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, old)
                if digest(old) != current:
                    raise RuntimeError('App code changed while saving the rollback copy.')
        shutil.copy2(manifest_path, saved / 'update-manifest.json')
        print('Old app files saved at ' + str(saved), flush=True)
        print('Applying the login update. The web server will pause briefly...', flush=True)
        applied = []
        try:
            run('/usr/bin/systemctl', 'stop', 'k3ls-web')
            for entry, source, target, current in pending:
                applied.append((entry, target, current))
                replace_file(staged / entry['path'], target, owner)
                # New folders must be readable by Frappe and public assets by Nginx.
                parent = target.parent
                while parent != APP:
                    os.chmod(parent, 0o755)
                    os.chown(parent, owner.pw_uid, owner.pw_gid)
                    parent = parent.parent
            clear_cache()
            run('/usr/bin/systemctl', 'start', 'k3ls-web')
            health(manifest)
            (saved / 'complete.json').write_text(json.dumps({'release': release, 'manifest_sha256': manifest_hash}, indent=2) + '\n')
            print('Login update complete. The server and logo checks passed.', flush=True)
        except BaseException:
            print('Update failed. Restoring the previous app files...', flush=True)
            run('/usr/bin/systemctl', 'stop', 'k3ls-web')
            for entry, target, current in reversed(applied):
                if current is None:
                    if target.is_file():
                        target.unlink()
                else:
                    replace_file(originals / entry['path'], target, owner)
            for folder in sorted(created_folders, key=lambda path: len(path.parts), reverse=True):
                # Only remove empty folders created by this patch. Preserve any
                # caches or files produced by another process during the update.
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
            # Restore availability even if a cache-clear command fails.
            try:
                clear_cache()
            finally:
                run('/usr/bin/systemctl', 'start', 'k3ls-web')
            health()
            print('Previous app code restored. Shop records were not replaced.', flush=True)
            raise


if __name__ == '__main__':
    try:
        apply(Path(sys.argv[1]).resolve(strict=True), sys.argv[2])
    except Exception as error:
        print('Update stopped: ' + str(error), file=sys.stderr, flush=True)
        sys.exit(1)
