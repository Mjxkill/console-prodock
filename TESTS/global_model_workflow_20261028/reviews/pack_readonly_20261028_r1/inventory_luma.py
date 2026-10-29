#!/usr/bin/env python3
"""Read-only, bounded inventory of Luma code-shaped files over 1000 lines.

Location is not ownership: build copies are separated from candidate sources,
and no entry is granted an archive/vendor exemption by this discovery script.
The explicit kernel build exclusion is listed in the report. No source changes.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path

EXTENSIONS = {'.c', '.h', '.cpp', '.cc', '.hpp', '.py', '.sh', '.inc',
              '.v', '.sv', '.vhd', '.vhdl', '.tcl', '.js', '.ts', '.rs', '.go'}
DATA_NAMES = {'data.c', 'surface_data.h', 'shooter_art.h', 'puzzle_art.h',
              'activity_art.h', 'hero_polish.h', 'l3_simon_art.h', 'festival_art.h',
              'sky_art.h', 'memory_art.h', 'festival_flower_art.h',
              'vegetation_art.h', 'festival_surface_art.h',
              'regenerated_baseline.c', 'regenerated_baseline_r2.c'}


def measure(path):
    """Physical CR/LF/CRLF lines including final unterminated line, plus SHA."""
    before = path.stat()
    digest = hashlib.sha256()
    count = size = 0
    last = b''
    with path.open('rb') as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
            count += chunk.count(b'\n') + chunk.count(b'\r') - chunk.count(b'\r\n')
            count -= int(last == b'\r' and chunk[:1] == b'\n')
            last = chunk[-1:]
            size += len(chunk)
    count += int(bool(last) and last not in (b'\r', b'\n'))
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns, before.st_ino) == (
        after.st_size, after.st_mtime_ns, after.st_ino), str(path) + ' changed'
    return {'lines': count, 'bytes': size, 'sha256': digest.hexdigest()}


def location(parts):
    if parts[0] == 'build' or any(p.startswith('build_') for p in parts):
        return 'build_copy_or_generated_output'
    if parts[0] in ('candidates', 'art'):
        return 'candidate_or_art_source'
    return 'working_tree_source_or_test'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = args.project
    result = {'root': str(root), 'limit': 1000,
              'extensions': sorted(EXTENSIONS), 'over_limit': [],
              'explicit_exclusions': ['build-kernel: Linux/OpenSBI/build package, separate vendor/archive review'],
              'symlinks_not_followed': [], 'summary': {}}
    scanned = collections.Counter()
    for directory, dirs, files in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in dirs[:]:
            p = current / name
            if p.is_symlink():
                result['symlinks_not_followed'].append(str(p.relative_to(root)))
                dirs.remove(name)
            elif name in ('__pycache__', '.git', 'node_modules') or (
                    current == root and name == 'build-kernel'):
                dirs.remove(name)
        for name in sorted(files):
            path = current / name
            if path.is_symlink():
                result['symlinks_not_followed'].append(str(path.relative_to(root)))
                continue
            if path.suffix not in EXTENSIONS:
                continue
            relative = path.relative_to(root)
            bucket = location(relative.parts)
            scanned[bucket] += 1
            stats = measure(path)
            if stats['lines'] > 1000:
                result['over_limit'].append(dict(path=str(relative), location=bucket,
                    kind='generated_asset_data' if name in DATA_NAMES else 'logic_or_test', **stats))
    result['over_limit'].sort(key=lambda row: row['path'])
    for bucket, count in sorted(scanned.items()):
        subset = [r for r in result['over_limit'] if r['location'] == bucket]
        result['summary'][bucket] = {'scanned': count, 'over_limit': len(subset),
            'distinct_over_limit_sha': len({r['sha256'] for r in subset}),
            'by_kind': dict(collections.Counter(r['kind'] for r in subset))}
    result['distinct_over_limit_sha'] = len({r['sha256'] for r in result['over_limit']})
    result['interpretation'] = 'Discovery only; not an ownership manifest or repository-wide PASS.'
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'summary': result['summary'],
                      'distinct_over_limit_sha': result['distinct_over_limit_sha']}, indent=2))


if __name__ == '__main__':
    main()
