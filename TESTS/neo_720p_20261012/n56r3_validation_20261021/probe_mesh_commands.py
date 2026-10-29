#!/usr/bin/env python3
"""Trace the fixed inside mesh command stream with CPU parked, scanout off.

Requires the same image's completed three-window initialization/readback.
Rechecks the vertex/face data, then replays only those exact eleven commands.
No Linux, CPU resume, SD, flash, or qualification waiver.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/neo'))
from load_linux import recovery_commands

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--anchor', type=Path, required=True)
    p.add_argument('--prior-mesh', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    guard = recovery_commands(a.anchor)[:-3]
    anchor = json.loads((a.anchor / 'result.json').read_text())
    prior = json.loads((a.prior_mesh / 'result.json').read_text())
    vectors = ROOT / 'TESTS/neo_720p_20261012/geometry_faces/inside'
    if (prior['bitstream_sha256'] != anchor['bitstream_sha256'] or
            prior['transport_error'] is not None or
            prior['completed_commands'] != 11 or
            len(prior['windows']) != 3 or
            prior['windows'][2]['mismatch_bytes'] != 0 or
            not prior['full_window_guards_checked'] or not prior['cpu_left_halted']):
        raise ValueError('Need completed matching parked mesh evidence')
    if sha(vectors / 'commands.hex') != '0615879abeac9c337e2632e060e282e86c35db030110b2d3377104de8dde5065':
        raise ValueError('Not the reviewed bounded inside mesh commands')
    for name, digest in prior['vector_sha256'].items():
        if sha(vectors / name) != digest:
            raise ValueError('Mesh vectors changed')
    initial = bytes.fromhex((vectors / 'initial.hex').read_text())
    words = [int(w, 16) for w in (vectors / 'commands.hex').read_text().split()]
    out = a.out.resolve()
    if any(c in str(out) for c in '{}\\\r\n'):
        raise ValueError('Unsafe Tcl path')
    out.mkdir(parents=True, exist_ok=False)
    checks = dict(errors=0x0c, lost=0x1c, rejected=0x34, pixels=0x3c,
                  invalid=0x4c, vertices=0x50, triangles=0x54)
    commands = [*guard, 'echo MESH_PARKED',
        'foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {',
        '  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}', '}',
        'if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU"}',
        'if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "Missing debug"}',
        'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}',
        'if {([lindex [read_memory 0xe9005008 32 1] 0]&7) != 0} {error "Partial command"}']
    for address, size in ((0x1740000, 9*32), (0x1748000, 32)):
        offset = 2*(1 << 20) + address-0x1700000
        data = initial[offset:offset+size]
        want = ' '.join(str(int.from_bytes(data[i:i+4], 'little')) for i in range(0, size, 4))
        commands += [f'set want {{{want}}}', f'set got [read_memory {address:#x} 32 {size//4}]',
            'foreach x $got y $want {if {$x != $y} {error "Mesh data changed since prior diagnostic"}}']
    commands += ['echo MESH_MEMORY_VERIFIED']
    for index in range(11):
        commands += [f'set before_{k} [lindex [read_memory {0xe9001000+off:#x} 32 1] 0]' for k, off in checks.items()]
        commands += ['set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]']
        commands += [f'write_memory 0xe9001010 32 {{{w:#x}}}' for w in words[index*8:index*8+8]]
        commands += ['set complete 0', 'for {set poll 0} {$poll < 100} {incr poll} {',
            '  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}',
            '  sleep 5', '}', f'if {{!$complete}} {{error "Fence timeout {index}"}}', 'sleep 2']
        for k, off in checks.items():
            commands += [f'set delta [expr {{([lindex [read_memory {0xe9001000+off:#x} 32 1] 0]-$before_{k})&0xffffffff}}]',
                         f'echo "MESH_COUNTER {index} {k} $delta"']
        commands += [f'echo "MESH_HEADERS {index} [read_memory 0xe9005018 32 2]"',
                     f'echo "MESH_META {index} [read_memory 0xe9005040 32 1]"']
    commands += ['if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle at exit"}',
                 'echo MESH_TRACE_COMPLETE', 'shutdown', '']
    script = out / 'probe.tcl'
    script.write_text('\n'.join(commands))
    error = None
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (out / 'openocd.log').open('w') as log:
            try:
                subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
                    '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled', '-f', str(script)],
                    stdout=log, stderr=log, check=True, timeout=60)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                error = str(e)
    raw = (out / 'openocd.log').read_text()
    observations = [dict(index=i, opcode=words[i*8]>>24, counters={}) for i in range(11)]
    for i, k, v in re.findall(r'^MESH_COUNTER (\d+) (\w+) (\d+)$', raw, re.M):
        observations[int(i)]['counters'][k] = int(v)
    for i, values in re.findall(r'^MESH_HEADERS (\d+) (.+)$', raw, re.M):
        observations[int(i)]['headers'] = [hex(int(v, 0)) for v in values.split()]
    for i, v in re.findall(r'^MESH_META (\d+) (\S+)$', raw, re.M):
        observations[int(i)]['meta'] = hex(int(v, 0))
    result = dict(capture_complete=error is None and 'MESH_TRACE_COMPLETE' in raw and
                  all(set(c['counters'])==set(checks) for c in observations),
        scope='Per-command diagnostic; existing DDR contents reused; not full memory or timing qualification',
        bitstream_sha256=anchor['bitstream_sha256'], qualification_status=anchor['qualification_status'],
        prior_mesh_result_sha256=sha(a.prior_mesh / 'result.json'), script_sha256=sha(script),
        probe_sha256=sha(Path(__file__)), error=error, observations=observations,
        cpu_left_halted=True if 'MESH_PARKED' in raw else None, sd_written=False, flash_written=False)
    (out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    if not result['capture_complete']:
        raise SystemExit('Incomplete diagnostic; evidence retained')

if __name__ == '__main__':
    main()
