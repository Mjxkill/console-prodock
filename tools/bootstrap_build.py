#!/usr/bin/env python3
"""Restore hash-pinned build/test inputs shipped with the public source tree.

This only installs immutable historical inputs. It never overwrites different
files, changes a protected reference, runs a compiler or accesses a board.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'releases/build-inputs-20261104'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def destination(root, name):
    """Accept only relative regular-file destinations within the checkout."""
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Unsafe archive path: ' + name)
    target = root / relative
    if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Symlinked destination: ' + name)
    return target


def install_archive(archive, entries, root, prefix=''):
    """Verify all members and conflicts before writing any selected member."""
    with tarfile.open(archive) as source:
        members = {m.name: m for m in source.getmembers()}
        if len(members) != len(source.getmembers()):
            raise ValueError('Duplicate archive members')
        pending = []
        for name, expected in entries.items():
            member = members.get(name)
            if member is None or not member.isfile():
                raise ValueError('Missing/nonregular archive member: ' + name)
            target = destination(root, prefix + name)
            data = source.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Archive member SHA-256 mismatch: ' + name)
            if target.exists():
                if not target.is_file() or sha(target) != expected:
                    raise ValueError('Existing input differs; preserving it: ' + str(target))
            else:
                pending.append((target, data, member.mode & 0o777))
        for target, data, mode in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also protects against a concurrent installer.
            with target.open('xb') as output:
                output.write(data)
            target.chmod(mode)
        return len(pending)


def bootstrap(root=ROOT, package=PACKAGE):
    record = json.loads((package / 'MANIFEST.json').read_text())
    archive = package / record['archive']
    if sha(archive) != record['archive_sha256']:
        raise ValueError('Build-input archive SHA-256 mismatch')
    added = install_archive(archive, record['files'], root)
    # G22 is an existing protected archive. Extract only the inputs required by
    # the reference checker; its original archive bytes remain unchanged.
    reference = json.loads((root / 'tang/boards/prodock/reference.json').read_text())
    selected = {name.removeprefix('tang/impl/'): digest
                for name, digest in reference['protected_files'].items()
                if name.startswith('tang/impl/gpu_geometry_g22r0/')}
    added += install_archive(root / 'bitstreams/prodock_g22r0_reference_20261021.tar.gz',
                             selected, root, prefix='tang/impl/')
    print(f'Build inputs verified; {added} files installed. No hardware accessed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    bootstrap()


if __name__ == '__main__':
    main()
