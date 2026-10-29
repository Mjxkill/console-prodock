#!/usr/bin/env python3
"""Separate a GPU completion-counter failure from a missing legacy 2D write.

Stopped Neo diagnostic only. One fixed-address, one-row legacy fill, without
TARGET or dependence on its completion counter. No Linux, SD or flash access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from load_linux import recovery_commands

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x00800000  # Legacy page 0; blitter PAGE_BASE_WORDS=0x400000.
PATTERN = bytes((i * 29 + 7) & 255 for i in range(128))
EXPECTED = PATTERN[:32] + bytes([0xa6]) * 32 + PATTERN[64:]
COMMAND = (0x0100a600, 32 << 16, (32 << 16) | 1, 0, 0, 0, 0, 0)


def analyze(log, before, after):
    samples = {name: [int(v, 0) for v in values.split()]
               for name, values in re.findall(r'^LEGACY_(BEFORE|AFTER) (.+)$', log, re.M)}
    complete = 'LEGACY_COMPLETE' in log and len(before) == len(after) == 128
    seeded = before == PATTERN
    dma = seeded and after == EXPECTED
    status_ok = all(len(samples.get(k, [])) == 3 for k in ('BEFORE', 'AFTER'))
    fence = (status_ok and samples['AFTER'][0] == 0
             and (samples['AFTER'][1] & 65535) == ((samples['BEFORE'][1] + 1) & 65535)
             and samples['AFTER'][2] == samples['BEFORE'][2])
    return dict(complete=complete, seed_verified=seeded, dma_exact=dma,
                fence_passed=fence, passed=complete and dma and fence, samples=samples,
                changed_bytes=[i for i in range(min(len(before), len(after))) if before[i] != after[i]],
                cpu_left_halted=complete and 'LEGACY_BEGIN' in log)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--failed-load', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    previous = json.loads((args.failed_load/'result.json').read_text())
    guard = recovery_commands(args.failed_load)[:-3]
    out = args.out.resolve()
    if any(c in str(out) for c in '{}\\\r\n'):
        p.error('Unsafe output path')
    out.mkdir(parents=True, exist_ok=False)
    (out/'pattern.bin').write_bytes(PATTERN)
    (out/'expected.bin').write_bytes(EXPECTED)
    commands = ['riscv expose_csrs 1994,1996,2000', *guard,
                'reg priv 3', 'reg satp 0', 'reg mstatus 0', 'reg mie 0',
                'reg csr1996 6', 'reg csr1994 0',
                'if {[lindex [read_memory 0xe9001000 32 1] 0] != 0x424c5432} {error "Wrong GPU ABI"}',
                'if {[lindex [read_memory 0xe9001004 32 1] 0] != 0} {error "GPU is not idle"}',
                'if {[lindex [read_memory 0xe9000004 32 1] 0] != 0} {error "Scanout is enabled"}',
                'echo LEGACY_BEGIN',
                f'load_image {{{out}/pattern.bin}} {BASE:#x} bin',
                f'verify_image {{{out}/pattern.bin}} {BASE:#x} bin',
                f'dump_image {{{out}/before.bin}} {BASE:#x} 128',
                'echo "LEGACY_BEFORE [read_memory 0xe9001004 32 3]"']
    commands += [f'write_memory 0xe9001010 32 {{{word:#x}}}' for word in COMMAND]
    commands += ['sleep 100', 'echo "LEGACY_AFTER [read_memory 0xe9001004 32 3]"',
                 f'dump_image {{{out}/after.bin}} {BASE:#x} 128',
                 'echo LEGACY_COMPLETE', 'shutdown', '']
    script = '\n'.join(commands)
    (out/'probe.tcl').write_text(script)
    transport_error = None
    with (out/'openocd.log').open('w') as log:
        try:
            subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT/'tools/neo/ae350_espprog.cfg'),
                            '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled',
                            '-f', str(out/'probe.tcl')], stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            transport_error = str(error)
    read = lambda name: (out/name).read_bytes() if (out/name).exists() else b''
    result = analyze((out/'openocd.log').read_text(), read('before.bin'), read('after.bin'))
    result.update(bitstream_sha256=previous['bitstream_sha256'],
                  bitstream_identity='Preceding load record; no independent FPGA readback',
                  transport_error=transport_error, sd_written=False, flash_written=False,
                  requested_writes='CPU seeds volatile DDR 0x00800000..0x0080007f; one legacy GPU fill at 0x00800020..0x0080003f',
                  script_sha256=hashlib.sha256(script.encode()).hexdigest())
    result['passed'] &= transport_error is None
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit('Legacy GPU probe did not fully pass; evidence saved')


if __name__ == '__main__':
    main()
