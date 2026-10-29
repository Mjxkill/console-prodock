#!/usr/bin/env python3
"""Apply the reviewed allowlist only; preserve snapshots, references and proofs."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import board_contract

EXPECTED = 'f80ff6cd4c7aaca64477c88b618efa5f117f55f8e4f7311f0aba4b4f7f1fec7e'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def idle():
    text = subprocess.check_output(['ps', '-eo', 'pid=,comm=,args='], text=True)
    busy = []
    for line in text.splitlines():
        words = line.split(None, 2)
        if len(words) > 1 and words[1] in {'gw_sh', 'gw_pnr', 'gw_syn', 'synplify_pro', 'openFPGALoader'}:
            busy.append(line)
    if busy:
        raise RuntimeError('Active compiler/programmer: ' + '\n'.join(busy))


def same_file(row):
    path = ROOT / row['path']
    if not path.is_relative_to(ROOT / 'tang/impl') or path.resolve() != path:
        raise ValueError('Outside scope or symlink: ' + row['path'])
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Not a regular file: ' + row['path'])
    actual = (info.st_size, info.st_mtime_ns, info.st_ino, info.st_nlink)
    expected = tuple(row[k] for k in ('size', 'mtime_ns', 'inode', 'links'))
    if actual != expected:
        raise ValueError('File changed since inventory: ' + row['path'])
    return path


def preflight(manifest):
    idle()
    before = board_contract.regression_inputs()
    board_contract.reference_check()
    local_proof = board_contract.require_local_regressions()
    for name, digest in manifest['input_sha256'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('Inventory input changed: ' + name)
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
    paths = set()
    builds = set()
    for row in manifest['files']:
        name = row['path']
        if name in paths or name in tracked or row['build'] in manifest['protected_builds']:
            raise ValueError('Duplicate/tracked/protected candidate: ' + name)
        path = same_file(row)
        build = ROOT / 'tang/impl' / row['build']
        if path.parent != build / 'impl/pnr':
            raise ValueError('Unexpected candidate location: ' + name)
        suffix = path.suffix
        if suffix in ('.bin', '.binx'):
            if not path.with_suffix('.fs').is_file():
                raise ValueError('Missing canonical FS: ' + name)
        elif suffix == '.html':
            if not (path.with_suffix('.txt').is_file() or path.with_suffix('').is_file()):
                raise ValueError('Missing plain report: ' + name)
        elif suffix not in ('.p', '.pr', '.db'):
            raise ValueError('Unsupported deletion type: ' + name)
        paths.add(name)
        builds.add(build)
    snapshots = {}
    retained = {}
    for build in sorted(builds):
        p = build / 'sources.json'
        sources = json.loads(p.read_text())
        if not isinstance(sources, dict) or not sources:
            raise ValueError('Missing snapshot manifest: ' + str(build))
        for name, digest in sources.items():
            f = build / 'source' / name
            if not f.is_relative_to(build / 'source') or '..' in Path(name).parts or sha(f) != digest:
                raise ValueError('Snapshot mismatch: ' + str(f))
        snapshots[str(p.relative_to(ROOT))] = sha(p)
    bitstreams = json.loads((HERE / 'bitstreams.json').read_text())
    for row in bitstreams['files']:
        path = ROOT / row['path']
        if sha(path) != row['digest']:
            raise ValueError('Retained bitstream changed: ' + row['path'])
        retained[row['path']] = row['digest']
    return dict(inputs=before, local_proof=local_proof, snapshots=snapshots, retained_bitstreams=retained)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    manifest_path = HERE / 'deletion_candidates.json'
    if sha(manifest_path) != EXPECTED:
        raise ValueError('Unreviewed deletion manifest')
    manifest = json.loads(manifest_path.read_text())
    with (HERE / 'cleanup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        proof = preflight(manifest)
        print(json.dumps(dict(verified=True, files=len(manifest['files']),
            bytes=sum(r['size'] for r in manifest['files']), apply=args.apply)), flush=True)
        if not args.apply:
            return
        out = HERE / ('applied_' + time.strftime('%Y%m%d_%H%M%S'))
        out.mkdir()
        (out / 'preflight.json').write_text(json.dumps(proof, indent=2) + '\n')
        result = dict(status='APPLYING', started_unix=time.time(), manifest_sha256=EXPECTED,
                      files_removed=0, logical_bytes_removed=0, allocated_bytes_removed=0,
                      source_inputs_modified=False, bitstreams_removed=0)

        def save():
            (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')

        save()
        try:
            # Hash and revalidate the entire allowlist before the first unlink.
            prepared = []
            for row in manifest['files']:
                path = same_file(row)
                prepared.append(dict(row, sha256=sha(path)))
            (out / 'deleted_manifest.json').write_text(json.dumps(prepared, indent=2) + '\n')
            idle()
            with (out / 'journal.jsonl').open('x') as log:
                for row in prepared:
                    path = same_file(row)
                    path.unlink()
                    result['files_removed'] += 1
                    result['logical_bytes_removed'] += row['size']
                    if row['links'] == 1:
                        result['allocated_bytes_removed'] += row['allocated']
                    log.write(json.dumps(dict(path=row['path'], sha256=row['sha256'])) + '\n')
                    log.flush()
                os.fsync(log.fileno())
            board_contract.reference_check()
            if board_contract.regression_inputs() != proof['inputs']:
                raise RuntimeError('Regression inputs changed during cleanup')
            for name, digest in proof['retained_bitstreams'].items():
                if sha(ROOT / name) != digest:
                    raise RuntimeError('Retained bitstream changed during cleanup: ' + name)
            result.update(status='COMPLETED', references_preserved=True,
                          retained_bitstreams_verified=len(proof['retained_bitstreams']),
                          regression_inputs_unchanged=True)
        except BaseException as exc:
            result.update(status='FAILED_OR_INCOMPLETE', error=repr(exc))
            raise
        finally:
            result['finished_unix'] = time.time()
            save()
            print(json.dumps(dict(output=str(out), **result)), flush=True)


if __name__ == '__main__':
    main()
