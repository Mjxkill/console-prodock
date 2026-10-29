#!/usr/bin/env python3
"""Install the pinned, hash-verified OSS CAD Suite locally; no system changes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Use an already downloaded archive')
    parser.add_argument('--component', choices=['suite', 'legacy-pack'], default='suite')
    args = parser.parse_args()
    legacy = args.component == 'legacy-pack'
    lock = json.loads((ROOT / ('apicula-legacy.lock.json' if legacy else 'toolchain.lock.json')).read_text())
    tools = ROOT / '.tools'
    tools.mkdir(exist_ok=True)
    target = tools / ('apicula-' + lock['version'] if legacy else 'oss-cad-suite')
    if target.exists():
        raise SystemExit('Toolchain already exists; refusing to replace it')
    archive = args.archive or tools / ('apicula-legacy.whl' if legacy else 'oss-cad-suite-' + lock['release'] + '.tgz')
    if not args.archive:
        subprocess.run(['curl', '-fL', '--retry', '2', lock['url'], '-o', str(archive)], check=True)
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if archive.stat().st_size != lock['bytes'] or digest.hexdigest() != lock['sha256']:
        raise SystemExit('Archive size/SHA-256 differs from the pinned official release')
    print('Official archive SHA-256 verified', flush=True)
    if legacy:
        with tempfile.TemporaryDirectory(prefix='install-pack-', dir=tools) as temp:
            with zipfile.ZipFile(archive) as bundle:
                for name in bundle.namelist():
                    path = Path(name)
                    if path.is_absolute() or '..' in path.parts:
                        raise SystemExit('Unsafe archive path')
                bundle.extractall(temp)
            Path(temp).rename(target)
        (tools/'installed-apicula-legacy.json').write_text(json.dumps(lock, indent=2)+'\n')
        print(target)
        return
    with tempfile.TemporaryDirectory(prefix='install-', dir=tools) as temp:
        with tarfile.open(archive, 'r:gz') as bundle:
            members = bundle.getmembers()
            if any(Path(m.name).parts[0] != 'oss-cad-suite' for m in members):
                raise SystemExit('Unexpected archive root')
            # The data filter rejects traversal, devices and escaping links.
            bundle.extractall(temp, members=members, filter='data')
        (Path(temp) / 'oss-cad-suite').rename(target)
    (tools / 'installed.json').write_text(json.dumps(lock, indent=2) + '\n')
    print(target)


if __name__ == '__main__':
    main()
