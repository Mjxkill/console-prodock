#!/usr/bin/env python3
"""Follow one guarded Neo preflight with pixel comparisons; no FPGA load or boot.

Only the exact successful preflight is accepted. Existing probe_geometry guards
remain authoritative; the follower holds the board lock. A transport/CPU-state error stops the
sequence; pixel mismatches are collected without being reported as success.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CASES = ('masked_rectangles', 'solid', 'alpha', 'depth', 'textured', 'perspective')


def accepted_board(validation, build):
    status = json.loads((validation/'status.json').read_text())
    if status.get('builds') != [str(build)]:
        raise ValueError('Validation covers a different build')
    if status.get('state') in ('waiting', 'testing'):
        return None
    if status.get('state') != 'preflight_passed':
        raise ValueError('Preflight did not pass: '+str(status.get('state')))
    entries = status.get('results', [])
    if len(entries) != 1:
        raise ValueError('Ambiguous preflight result')
    entry = entries[0]
    board = validation/build.name/'board'
    if (entry.get('build') != str(build) or entry.get('state') != 'preflight_passed' or
            entry.get('out') != str(board.parent) or entry.get('cpu_left_halted') is not True):
        raise ValueError('Unexpected preflight identity or CPU state')
    result = json.loads((board/'result.json').read_text())
    q = json.loads((build/'qualification.json').read_text())
    if (not entry.get('bitstream_sha256') or entry['bitstream_sha256'] != q.get('bitstream_sha256') or
            result.get('bitstream_sha256') != entry['bitstream_sha256'] or
            result.get('passed') is not True or result.get('run_mode') != 'preflight_only' or
            result.get('cpu_left_halted') is not True or result.get('sd_written') is not False or
            result.get('flash_written') is not False):
        raise ValueError('Board result does not prove the expected parked preflight')
    return board, entry['bitstream_sha256']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--validation', type=Path, required=True)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--geometry', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--wait-seconds', type=int, default=7200)
    a = p.parse_args()
    if not 1 <= a.wait_seconds <= 14400:
        p.error('Wait must be 1..14400 seconds')
    validation = a.validation.resolve(strict=True)
    build = a.build.resolve(strict=True)
    vectors, geometry = a.vectors.resolve(strict=True), a.geometry.resolve(strict=True)
    if build.parent != ROOT/'tang/impl' or not build.name.startswith('console_neo_'):
        p.error('Expected an existing console Neo build')
    out = a.out.resolve();out.mkdir(parents=True, exist_ok=False)
    state = dict(state='waiting_preflight',build=str(build),validation=str(validation),
                 results=[],started_utc=datetime.now(timezone.utc).isoformat(),
                 scope='Parked Neo only; no FPGA load, CPU execution, scanout, Linux, SD or flash')
    def save():
        state['updated_utc'] = datetime.now(timezone.utc).isoformat()
        temp = out/'status.tmp'
        temp.write_text(json.dumps(state, indent=2)+'\n');temp.replace(out/'status.json')
    save()
    try:
        # Wait for the validator to finish, then exclude loaders and validators
        # for the whole pixel sequence. probe_geometry itself does not lock.
        with ((ROOT/'TESTS/neo_pixel_validation.lock').open('a') as lock,
              (ROOT/'TESTS/neo_pending_validation.lock').open('a') as pending_lock,
              (ROOT/'TESTS/neo_board.lock').open('a') as board_lock):
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            deadline = time.monotonic()+a.wait_seconds
            while True:
                accepted = accepted_board(validation, build)
                if accepted is not None:
                    break
                if time.monotonic() >= deadline:
                    raise ValueError('Preflight wait expired')
                time.sleep(min(5, max(0, deadline-time.monotonic())))
            while True:
                try:
                    fcntl.flock(pending_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ValueError('Validator did not release its lock')
                    time.sleep(1)
            fcntl.flock(board_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if accepted_board(validation, build) != accepted:
                raise ValueError('Preflight identity changed while acquiring locks')
            board, digest = accepted
            state.update(state='testing_pixels',board=str(board),bitstream_sha256=digest);save()
            for case in CASES+('geometry',):
                if case == 'geometry' and not all(r['passed'] for r in state['results']):
                    state['geometry_skipped'] = 'Raw pixel failure; preserve focused evidence'
                    break
                target = geometry if case == 'geometry' else vectors/case
                command = [sys.executable,str(ROOT/'tools/neo/probe_geometry.py'),
                           '--failed-load',str(board),'--vectors',str(target),'--out',str(out/case)]
                if case not in ('geometry', 'masked_rectangles'):
                    command += ['--window-bytes', '16384']
                state['active_case'] = case;save()
                print('Comparing '+case, flush=True)
                with (out/(case+'.log')).open('w') as log:
                    rc = subprocess.run(command,cwd=ROOT,stdout=log,stderr=log).returncode
                result_path = out/case/'result.json'
                result = json.loads(result_path.read_text())
                if (result.get('bitstream_sha256') != digest or result.get('sd_written') is not False or
                        result.get('flash_written') is not False or result.get('cpu_left_halted') is not True or
                        result.get('transport_error')):
                    raise ValueError('Unexpected probe identity, scope or hardware state: '+case)
                state['results'].append(dict(case=case,passed=rc==0 and result.get('passed') is True,
                                              result=str(result_path)))
                save()
            passed = len(state['results']) == len(CASES)+1 and all(r['passed'] for r in state['results'])
            state.update(state='passed' if passed else 'pixel_mismatches',active_case=None,
                         cpu_left_halted=True);save()
            return 0 if passed else 1
    except Exception as error:
        state.update(state='stopped',error=str(error));save()
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
