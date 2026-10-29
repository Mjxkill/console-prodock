#!/usr/bin/env python3
"""Probe Neo register-only GPU commands without depending on diagnostic CDC.

No DMA opcodes, CPU resume, FPGA load, SD or flash access. This is a bounded
diagnostic observation, not a replacement for coherent GPU qualification.
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
sys.path.insert(0, str(ROOT/'tools/neo'))
from load_linux import recovery_commands
from probe_gpu_debug import target_cases, control_cases


def cases():
    result = target_cases() + control_cases()
    # Repeat identical valid descriptors to expose previous-packet effects.
    for n in range(4):
        result.append(dict(name=f'repeat_preflight_{n}', words=[
            0x16000000, 0x12000000, 0x12001000, 0x00200040,
            0x00400040, 0, 0, 0], accepted=True))
    for width in (1, 2, 4, 8, 16, 32):
        for height in (1, 2, 4, 8, 16, 32):
            result.append(dict(name=f'tiny_{width}x{height}', words=[
                0x16000000, 0x00800000, 0x00900000,
                width << 16 | height, 64 << 16 | 64, 0, 0, 0], accepted=True))
    if len({c['name'] for c in result}) != len(result):
        raise ValueError('Duplicate case name')
    for case in result:
        if len(case['words']) != 8 or case['words'][0] >> 24 not in (22, 24, 25, 26, 30, 31, 33):
            raise ValueError('Not an eight-word register-only command')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--failed-load', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    guard = recovery_commands(a.failed_load)[:-3]
    out = a.out.resolve()
    if any(c in str(out) for c in '{}\\\r\n'):
        p.error('Unsafe output path')
    out.mkdir(parents=True, exist_ok=False)
    suite = cases()
    commands = [*guard,
        'foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {',
        '  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be disabled"}', '}',
        'if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU port"}',
        'if {[lindex [read_memory 0xe9005000 32 1] 0] != 0x4e474442} {error "Debug instrument absent"}',
        'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}',
        'echo "GPU_RAW before [read_memory 0xe9005000 32 16]"',
        'set initial_errors [lindex [read_memory 0xe900100c 32 1] 0]',
        'set initial_lost [lindex [read_memory 0xe900101c 32 1] 0]',
        'set initial_host [lindex [read_memory 0xe9005008 32 1] 0]',
        'if {($initial_host & 7) != 0} {error "Partial host command"}',
        'set status [lindex [read_memory 0xe9005004 32 1] 0]',
        'if {($status & 5) == 4} {write_memory 0xe9005004 32 {1}}',
        'sleep 10',
        'echo "GPU_RAW requested [read_memory 0xe9005000 32 16]"']
    for case in suite:
        commands += [
            'set before_rejected [lindex [read_memory 0xe9001034 32 1] 0]',
            'set before_geometry [lindex [read_memory 0xe900104c 32 1] 0]',
            'set expected_done [expr {([lindex [read_memory 0xe9001008 32 1] 0]+1)&0xffff}]',
            *[f'write_memory 0xe9001010 32 {{{word:#x}}}' for word in case['words']],
            'set complete 0',
            'for {set i 0} {$i < 100} {incr i} {',
            '  if {([lindex [read_memory 0xe9001008 32 1] 0]&0xffff) == $expected_done} {set complete 1; break}',
            '  sleep 1', '}',
            'if {!$complete} {error "Configuration fence timeout"}',
            'sleep 2',
            'set delta [expr {([lindex [read_memory 0xe9001034 32 1] 0]-$before_rejected)&0xffffffff}]',
            'set geometry_delta [expr {([lindex [read_memory 0xe900104c 32 1] 0]-$before_geometry)&0xffffffff}]',
            f'echo "GPU_CONFIG {case["name"]} $delta $geometry_delta"']
    commands += [
        'echo "GPU_RAW after [read_memory 0xe9005000 32 16]"',
        'echo "GPU_STATUS after [read_memory 0xe9001000 32 26]"',
        'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle at exit"}',
        'if {[lindex [read_memory 0xe900100c 32 1] 0] != $initial_errors || [lindex [read_memory 0xe900101c 32 1] 0] != $initial_lost} {error "Transport error counters changed"}',
        f'if {{(([lindex [read_memory 0xe9005008 32 1] 0]-$initial_host)&0xffffffff) != {len(suite)*8}}} {{error "Host word delta differs"}}',
        'echo "GPU_CONFIG_COMPLETE [reg pc]"', 'shutdown', '']
    script = out / 'probe.tcl'
    script.write_text('\n'.join(commands))
    error = None
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (out/'openocd.log').open('w') as log:
            try:
                subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT/'tools/neo/ae350_espprog.cfg'),
                    '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled', '-f', str(script)],
                    stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                error = str(e)
    text = (out/'openocd.log').read_text()
    observations = re.findall(r'^GPU_CONFIG (\w+) (\d+) (\d+)$', text, re.M)
    complete = error is None and 'GPU_CONFIG_COMPLETE' in text and [n for n, _, _ in observations] == [c['name'] for c in suite]
    result = dict(scope='Configuration-only observations; no DMA, not complete GPU qualification',
        bitstream_sha256=json.loads((a.failed_load/'result.json').read_text())['bitstream_sha256'],
        capture_complete=complete, cpu_left_halted=True if complete else None,
        transport_error=error, sd_written=False, flash_written=False,
        cases=[dict(c, rejected_delta=int(d), geometry_rejected_delta=int(g),
            matches=int(d)==int(not c['accepted']) and int(g)==int(not c['accepted'] and c['words'][0]>>24>=31))
            for c, (_, d, g) in zip(suite, observations)],
        raw={label: [int(w, 0) for w in words.split()] for label, words in re.findall(r'^GPU_RAW (\w+) (.+)$', text, re.M)},
        script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    result['all_expectations_match'] = complete and all(c['matches'] for c in result['cases'])
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(capture_complete=complete, all_expectations_match=result['all_expectations_match'],
        observations=len(observations), mismatches=[{k:v for k,v in c.items() if k!='words'} for c in result['cases'] if not c['matches']],
        raw=result['raw'], transport_error=error), indent=2))
    if not complete:
        raise SystemExit('Incomplete diagnostic; evidence saved')


if __name__ == '__main__':
    main()
