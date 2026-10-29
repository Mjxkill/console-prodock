#!/usr/bin/env python3
"""Audit explicit code ownership and physical line counts; never edits code.

Manifest v1: {"version":1,"files":[{"path":"src/main.c",
"ownership":"project","generated":false}]}. Vendor/archive entries require
an explicit nonempty "reason" and remain in the report, even over 1000 lines.
Paths are project-relative POSIX paths. Exit0=pass,1=project violations,2=input
refused. JSON is emitted to stdout. No automatic discovery or silent exclusions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

MAX_LINES = 1000


def need(ok, message):
    if not ok:
        raise ValueError(message)


def no_symlink(path):
    """Check lexical components before resolve can hide a symlink."""
    # abspath collapses '..' before checking symlinks, which can select a
    # different file tree than the filesystem would actually resolve.
    need('..' not in Path(path).parts, 'Parent traversal refused: ' + str(path))
    p = Path(os.path.abspath(path))
    for component in [p, *p.parents]:
        need(not component.is_symlink(), 'Symlink refused: ' + str(component))
    return p


def read_measure(path):
    """Return physical CR/LF lines, size and SHA; detect replacement/modification."""
    path = no_symlink(path)
    before = path.stat()
    need(stat.S_ISREG(before.st_mode), 'Not a regular file: ' + str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        need((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
             'File changed before read: ' + str(path))
        digest = hashlib.sha256()
        lines = size = 0
        previous = b''
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            lines += chunk.count(b'\n') + chunk.count(b'\r') - chunk.count(b'\r\n')
            if previous == b'\r' and chunk.startswith(b'\n'):
                lines -= 1
            previous = chunk[-1:]
        if previous and previous not in (b'\r', b'\n'):
            lines += 1
        after = os.fstat(fd)
        current = path.stat(follow_symlinks=False)
        need(not stat.S_ISLNK(current.st_mode) and
             (after.st_dev, after.st_ino) == (current.st_dev, current.st_ino),
             'File replaced while reading: ' + str(path))
        need((opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) ==
             (after.st_size, after.st_mtime_ns, after.st_ctime_ns) and size == after.st_size,
             'File modified while reading: ' + str(path))
        return {'lines': lines, 'bytes': size, 'sha256': digest.hexdigest()}
    finally:
        os.close(fd)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate JSON key: ' + str(key))
        result[key] = value
    return result


def audit(project, manifest):
    result = {'passed': False, 'max_lines': MAX_LINES, 'files': [],
              'violations': [], 'exemptions': [], 'errors': []}
    try:
        root = no_symlink(project)
        need(root.is_dir(), 'Project directory absent: ' + str(root))
        document = no_symlink(manifest)
        result['project'] = str(root)
        measure = read_measure(document)
        result['manifest_sha256'] = measure['sha256']
        data = document.read_bytes()
        need(hashlib.sha256(data).hexdigest() == measure['sha256'], 'Manifest changed')
        spec = json.loads(data, object_pairs_hook=unique_object)
        need(type(spec) is dict and set(spec) == {'version', 'files'} and
             type(spec['version']) is int and spec['version'] == 1 and
             type(spec['files']) is list, 'Invalid manifest v1 schema')
        need(bool(spec['files']), 'Empty file list refused')
        seen = set()
        for entry in spec['files']:
            need(type(entry) is dict and {'path', 'ownership'} <= set(entry) and
                 set(entry) <= {'path', 'ownership', 'generated', 'reason'}, 'Invalid entry schema')
            name, owner = entry['path'], entry['ownership']
            need(type(name) is str and name and '\\' not in name and '\0' not in name and
                 all(part not in ('', '.', '..') for part in name.split('/')),
                 'Unsafe relative path: ' + repr(name))
            need(name not in seen, 'Duplicate path: ' + name)
            seen.add(name)
            need(owner in ('project', 'vendor', 'archive'), 'Invalid ownership: ' + str(owner))
            generated = entry.get('generated', False)
            need(type(generated) is bool, 'generated must be boolean: ' + name)
            reason = entry.get('reason', '')
            need(type(reason) is str, 'reason must be text: ' + name)
            need(owner == 'project' or bool(reason.strip()), 'Exemption requires reason: ' + name)
            path = no_symlink(root / name)
            need(path.is_relative_to(root), 'Path escapes project: ' + name)
            row = dict(path=name, ownership=owner, generated=generated,
                       exemption=owner != 'project', reason=reason, **read_measure(path))
            row['over_limit'] = row['lines'] > MAX_LINES
            result['files'].append(row)
            if row['exemption']:
                result['exemptions'].append(dict(row))
            elif row['over_limit']:
                result['violations'].append(dict(row))
        result['passed'] = not result['violations']
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result['errors'].append(str(exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.project, args.manifest)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2 if result['errors'] else 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
