#!/usr/bin/env python3
"""Replay the independently checked geometry scene on a parked Neo via JTAG.

No CPU execution, Linux, scanout, SD or flash access. Three volatile DDR
windows are initialized and compared byte-for-byte, including unused guards.
This is a diagnostic, not a waiver of failed static timing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from load_linux import recovery_commands

ROOT = Path(__file__).resolve().parents[2]
WINDOWS = (0x00800000, 0x00900000, 0x01700000)
SIZE = 1 << 20


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_small_windows(words, initial, expected, size):
    """Bound the simple pixel-only diagnostic; full geometry keeps 1-MiB windows."""
    if not 4096 <= size <= SIZE or size % 4096:
        raise ValueError('Window must be a positive multiple of 4 KiB, at most 1 MiB')
    for i in range(3):
        if initial[i*SIZE+size:(i+1)*SIZE] != expected[i*SIZE+size:(i+1)*SIZE]:
            raise ValueError('Expected writes exceed the requested diagnostic windows')
    target_seen = False
    for index in range(0, len(words), 8):
        w = words[index:index+8]
        op = w[0] >> 24
        if op not in (22, 23, 24, 25, 26, 27, 28, 30):
            raise ValueError('Small windows accept only bounded pixel commands')
        if op == 22:
            width, height = w[3] >> 16, w[3] & 65535
            strides = (w[4] >> 16, w[4] & 65535)
            if (w[1:3] != list(WINDOWS[:2]) or not width or not height or
                    any(width*2 > stride or (height-1)*stride+width*2 > size for stride in strides)):
                raise ValueError('Target surface exceeds the requested diagnostic windows')
            target_seen = True
        elif op == 24:
            width, height, stride = w[2] >> 16, w[2] & 65535, w[3] & 65535
            if (w[1] != WINDOWS[2] or not width or not height or width*2 > stride or
                    (height-1)*stride+width*2 > size):
                raise ValueError('Texture exceeds the requested diagnostic window')
        elif op in (27, 28) and not target_seen:
            raise ValueError('Draw requires an explicitly bounded target')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--failed-load', type=Path, required=True)
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--window-bytes', type=int, default=SIZE,
                   help='Default: full 1-MiB windows. Smaller 4-KiB multiples require bounded pixel-only commands; no mesh/copy')
    a = p.parse_args()
    guard = recovery_commands(a.failed_load)[:-3]
    ref = json.loads((a.vectors/'result.json').read_text())
    if ref['status'] != 'PASS' or ref['world'] or ref['bytes_compared'] != 3*SIZE:
        raise ValueError('Expected a passing three-window diagnostic scene')
    initial = bytes.fromhex((a.vectors/'initial.hex').read_text())
    expected = bytes.fromhex((a.vectors/'expected.hex').read_text())
    words = [int(w, 16) for w in (a.vectors/'commands.hex').read_text().split()]
    if len(initial) != 3*SIZE or len(expected) != 3*SIZE or len(words) != ref['input_commands']*8:
        raise ValueError('Incomplete diagnostic vectors')
    if any(not 0 <= w <= 0xffffffff for w in words):
        raise ValueError('Command word outside 32 bits')
    if a.window_bytes != SIZE:
        check_small_windows(words, initial, expected, a.window_bytes)
    size = a.window_bytes
    out = a.out.resolve()
    if any(c in str(out) for c in '{}\\\r\n'):
        raise ValueError('Unsafe Tcl output path')
    out.mkdir(parents=True, exist_ok=False)
    prior = json.loads((a.failed_load/'result.json').read_text())
    result = dict(passed=False, prepared_only=a.prepare_only,
                  bitstream_sha256=prior['bitstream_sha256'],
                  qualification_status=prior['qualification_status'],
                  scope='Parked CPU; GPU geometry diagnostic only; static timing still required',
                  bytes_per_window=size,full_window_guards_checked=(size==SIZE),
                  sd_written=False, flash_written=False, commands=len(words)//8,
                  vector_sha256={n: sha((a.vectors/n).read_bytes()) for n in
                                 ('initial.hex', 'expected.hex', 'commands.hex', 'result.json')},
                  windows=[], transport_error=None,cpu_left_halted=None)
    checks = [('errors', 0x0c, 0), ('lost', 0x1c, 0),
              ('v1_rejected', 0x34, ref['invalid_commands']+ref['shader_rejected'])]
    checks += [(key, offset, ref[key]) for key, offset in
               [('invalid_commands', 0x4c), ('vertices', 0x50), ('triangles', 0x54),
                ('culled', 0x58), ('clipped', 0x5c), ('slivers', 0x60)]]
    if 'passed_pixels' in ref:
        checks.append(('passed_pixels', 0x3c, ref['passed_pixels']))
    commands = ['riscv expose_csrs 1994,1996,2000', *guard,
                'echo GEOM_PARKED',
                'reg satp 0', 'reg mstatus 0', 'reg mie 0', 'reg csr1996 6', 'reg csr1994 0',
                'if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU ABI"}',
                'if {[lindex [read_memory 0xe9001048 32 1] 0] != 0x47334431} {error "Missing G3D1"}',
                'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU not idle"}',
                'foreach address {0xe900000c 0xe9000014 0xe9000034 0xe9000044} {',
                '  if {[lindex [read_memory $address 32 1] 0] != 0} {error "Scanout must be idle and disabled"}',
                '}']
    for key, offset, wanted in checks:
        commands.append(f'set before_{key} [lindex [read_memory {0xe9001000+offset:#x} 32 1] 0]')
    for i, address in enumerate(WINDOWS):
        data = initial[i*SIZE:i*SIZE+size]
        path = out/f'initial_{i}.bin'
        path.write_bytes(data)
        (out/f'expected_{i}.bin').write_bytes(expected[i*SIZE:i*SIZE+size])
        commands += [f'load_image {{{path}}} {address:#x} bin',
                     f'verify_image {{{path}}} {address:#x} bin', f'echo "GEOM_INITIAL_OK {i}"']
    # Match the simulation's programmable glyph used by mixed legacy commands.
    commands += ['set saved_font_address [lindex [read_memory 0xe9001014 32 1] 0]',
                 'write_memory 0xe9001014 32 {0x800}']
    commands += [f'write_memory 0xe9001018 32 {{{0xa5 if row%2 else 0x5a}}}' for row in range(16)]
    commands += ['set expected_done [expr {[lindex [read_memory 0xe9001008 32 1] 0] & 0xffff}]']
    for index in range(len(words)//8):
        commands += [f'write_memory 0xe9001010 32 {{{w:#x}}}' for w in words[index*8:index*8+8]]
        commands += ['set expected_done [expr {($expected_done+1)&0xffff}]',
                     'set complete 0',
                     'for {set poll 0} {$poll < 100} {incr poll} {',
                     '  if {([lindex [read_memory 0xe9001008 32 1] 0] & 0xffff) == $expected_done} {set complete 1; break}',
                     '  sleep 5', '}',
                     f'if {{!$complete}} {{error "GPU fence timeout at command {index}"}}',
                     f'echo "GEOM_COMMAND_OK {index}"']
    for key, offset, wanted in checks:
        commands += [f'set delta [expr {{([lindex [read_memory {0xe9001000+offset:#x} 32 1] 0]-$before_{key})&0xffffffff}}]',
                     f'echo "GEOM_COUNTER {key} $delta"']
    # Every command fence completed. Preserve read-only image evidence even
    # if a statistic differs; the host verdict below still fails closed.
    for i, address in enumerate(WINDOWS):
        commands += [f'dump_image {{{out/f"actual_{i}.bin"}}} {address:#x} {size}']
    font = bytes.fromhex((ROOT/'tang/rtl/video/font8x16.hex').read_text())
    commands += ['write_memory 0xe9001014 32 {0x800}']
    commands += [f'write_memory 0xe9001018 32 {{{b}}}' for b in font[0x800:0x810]]
    commands += ['write_memory 0xe9001014 32 [list $saved_font_address]',
                 'echo GEOM_COMPLETE', 'shutdown', '']
    script = out/'probe.tcl'
    script.write_text('\n'.join(commands))
    result['script_sha256'] = sha(script.read_bytes())
    report = out/'result.json'
    report.write_text(json.dumps(result, indent=2)+'\n')
    if a.prepare_only:
        print('Prepared only; no board access: '+str(out))
        return
    try:
        with (out/'openocd.log').open('w') as log:
            subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT/'tools/neo/ae350_espprog.cfg'),
                            '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled',
                            '-f', str(script)], stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=480)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        result['transport_error'] = str(error)
    log = (out/'openocd.log').read_text()
    result['completed_commands'] = len(re.findall(r'^GEOM_COMMAND_OK \d+$', log, re.M))
    result['counters'] = {k: int(v) for k, v in re.findall(r'^GEOM_COUNTER (\w+) (\d+)$', log, re.M)}
    result['counter_mismatches']={key:dict(expected=wanted,actual=result['counters'].get(key))
                                  for key,offset,wanted in checks if result['counters'].get(key)!=wanted}
    result['cpu_left_halted']=True if 'GEOM_PARKED' in log else None
    for i, address in enumerate(WINDOWS):
        actual = out/f'actual_{i}.bin'
        if actual.exists():
            data = actual.read_bytes()
            want = expected[i*SIZE:i*SIZE+size]
            differences = [n for n, (x, y) in enumerate(zip(data, want)) if x != y]
            result['windows'].append(dict(address=address, bytes=len(data),
                mismatch_bytes=len(differences)+abs(len(data)-len(want)),
                first_mismatches=[dict(address=address+n, got=data[n], expected=want[n]) for n in differences[:16]],
                actual_sha256=sha(data), expected_sha256=sha(want)))
    result['passed'] = (result['transport_error'] is None and 'GEOM_COMPLETE' in log
                        and len(result['windows']) == 3
                        and not result['counter_mismatches']
                        and all(w['mismatch_bytes'] == 0 for w in result['windows']))
    report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit('Geometry diagnostic incomplete or mismatched; partial evidence saved')


if __name__ == '__main__':
    main()
