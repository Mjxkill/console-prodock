#!/usr/bin/env python3
"""One-off, explicit cleanup of obsolete Gowin outputs; inputs/reports stay intact."""
import argparse
import collections
import datetime
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILDS = ROOT / 'tang/impl'
PLAN = HERE / 'plan.json'


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def plan():
    refs = json.loads((HERE / 'references.json').read_text())
    inventory = json.loads((HERE / 'inventory.json').read_text())
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', 'tang/impl'], cwd=ROOT, text=True).splitlines())
    protected = {Path(p).parts[2] for p in tracked}
    protected.update(name for name, paths in refs.items()
                     if any(p.endswith(('.py', '.sh', '.tcl')) for p in paths))
    protected.update({'gpu_geometry_g22r0', 'gpu_sdusb_c37', 'gpu_sdusb_c28',
                      'gpu_v1_r31', 'console_neo_n50r2', 'console_neo_n50r4',
                      'console_neo_n52r1'})
    # Keep the entire current DDR 6.0/400 MHz investigation and IP generators.
    for p in BUILDS.iterdir():
        match = re.match(r'console_neo_n(\d+)', p.name)
        if (match and int(match[1]) >= 38) or p.name.startswith('neo_ddr'):
            protected.add(p.name)
    # Explicit cross-build inputs are never cleanup candidates, even old caches.
    input_paths = set()
    for build in BUILDS.iterdir():
        if not build.is_dir() or build.is_symlink():
            continue
        for f in [*build.glob('*.tcl'), build / 'impl/pnr/cmd.do']:
            if not f.is_file():
                continue
            text = f.read_text(errors='replace')
            for path in re.findall(re.escape(str(BUILDS)) + r'/[^\s{}";]+', text):
                input_paths.add(path)
    files = []
    skipped = {}
    cutoff = time.time() - 86400
    for item in inventory:
        name = item['name']
        build = BUILDS / name
        if name in protected or not item['complete'] or build.is_symlink():
            skipped[name] = 'protected reference, recent experiment, or unfinished build'
            continue
        # Check actual output age, not the parent directory timestamp.
        logs = [p for p in [build / 'build.log', build / 'impl/pnr/cmd.do'] if p.exists()]
        if not logs or any(p.stat().st_mtime > cutoff for p in logs):
            skipped[name] = 'recent build'
            continue
        pnr = build / 'impl/pnr'
        if not pnr.is_dir() or pnr.is_symlink():
            continue
        # Private work files are reproducible. Referenced historical results retain
        # their bitstreams, routed netlists and SDF for diagnosis/reproduction.
        suffixes = {'.pr', '.p', '.db'}
        if name not in refs:
            suffixes |= {'.sdf', '.fs', '.bin', '.binx', '.vo'}
        for f in sorted(pnr.iterdir()):
            rel = str(f.relative_to(ROOT))
            if (not f.is_file() or f.is_symlink() or f.suffix not in suffixes
                    or rel in tracked or str(f) in input_paths):
                continue
            if f.resolve() != f or f.stat().st_mtime > cutoff:
                continue
            s = f.stat()
            files.append(dict(path=rel, size=s.st_size, allocated=s.st_blocks * 512,
                              mtime_ns=s.st_mtime_ns, inode=s.st_ino, links=s.st_nlink,
                              build=name, kind='obsolete routed outputs' if name not in refs
                              else 'obsolete private router cache'))
    result = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  protected=sorted(protected), skipped=skipped, files=files,
                  bytes=sum(f['size'] for f in files),
                  allocated_bytes=sum(f['allocated'] for f in files if f['links'] == 1),
                  affected_builds=len({f['build'] for f in files}))
    save(PLAN, result)
    print(json.dumps({k: result[k] for k in ['bytes', 'allocated_bytes', 'affected_builds']}))
    print('Files:', len(files), 'Extensions:', dict(collections.Counter(Path(f['path']).suffix for f in files)))


def apply():
    data = json.loads(PLAN.read_text())
    # Validate the entire allowlist before unlinking anything.
    for item in data['files']:
        p = ROOT / item['path']
        assert p.resolve() == p and p.is_relative_to(BUILDS)
        assert p.parts[-3:-1] == ('impl', 'pnr')
        assert p.relative_to(BUILDS).parts[0] not in data['protected']
        s = p.stat()
        assert (s.st_size, s.st_mtime_ns, s.st_ino) == (
            item['size'], item['mtime_ns'], item['inode']), str(p)
    result = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  removed=0, bytes=0, allocated_bytes=0)
    with (HERE / 'removed.jsonl').open('x') as log:
        for item in data['files']:
            (ROOT / item['path']).unlink()
            log.write(json.dumps(item) + '\n')
            log.flush()
            result['removed'] += 1
            result['bytes'] += item['size']
            if item['links'] == 1:
                result['allocated_bytes'] += item['allocated']
    result['affected_builds'] = data['affected_builds']
    result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(HERE / 'result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    apply() if args.apply else plan()
