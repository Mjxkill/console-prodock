#!/usr/bin/env python3
"""Bounded Neo CPU/ILM/cache context read; no DDR, DMA, flash or CSR writes.

The CPU is expected parked after the recorded R19 restoration. A halt request
allows fresh CSR reads. This does not attest the loaded SRAM bitstream by itself.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
BIT = ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local/impl/pnr/console_neo.fs'
SHA = '1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c'
CFG = ROOT / 'tools/neo/ae350_espprog.cfg'
SCRIPT = '''riscv expose_csrs 1984,1985,1994,1996
init
halt 1000
echo "CONTEXT_PC [reg pc]"
set here [lindex [reg pc] 2]
if {$here != 0x80000000 && $here != 0x80000004} {error "CPU is not parked; stop context probe"}
echo "CONTEXT_PRIV [reg priv]"
echo "CONTEXT_SATP [reg satp]"
echo "CONTEXT_MSTATUS [reg mstatus]"
echo "CONTEXT_MIE [reg mie]"
echo "CONTEXT_ILM [reg csr1984]"
echo "CONTEXT_DLM [reg csr1985]"
echo "CONTEXT_CACHE [reg csr1994]"
echo "CONTEXT_ROM [read_memory 0x80000000 32 2]"
echo "CONTEXT_VIDEO [read_memory 0xe9000000 32 3]"
echo "CONTEXT_GPU [read_memory 0xe9001000 32 4]"
echo "CONTEXT_DONE"
shutdown
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    assert hashlib.sha256(BIT.read_bytes()).hexdigest() == SHA
    assert not args.out.exists()
    args.out.mkdir()
    script = args.out / 'context.tcl'
    script.write_text(SCRIPT)
    result = dict(hardware=args.run, bitstream_declared_sha256=SHA,
                  identity_basis='Previous R19 restoration; not physical SRAM readback',
                  csr_writes=0, ddr_accesses=0, fpga_writes=0,
                  config_sha256=hashlib.sha256(CFG.read_bytes()).hexdigest())
    command = ['/usr/local/bin/openocd', '-f', str(CFG), '-c',
               'gdb_port disabled; tcl_port disabled; telnet_port disabled', '-f', str(script.resolve())]
    if args.run:
        fd = os.open(ROOT / 'TESTS/neo_board.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            active = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader',
                                     '-C', 'gao_sh', '-C', 'gao_analyzer', '-C', 'jtagserver',
                                     '-o', 'pid=,comm='], capture_output=True, text=True, timeout=5)
            assert not active.stdout.strip(), 'Another hardware client is active'
            start = time.monotonic()
            try:
                with (args.out / 'openocd.log').open('w') as log:
                    process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=15)
                raw = (args.out / 'openocd.log').read_text()
                result.update(returncode=process.returncode,
                              completed=process.returncode == 0 and raw.splitlines().count('CONTEXT_DONE') == 1)
            except subprocess.TimeoutExpired:
                result.update(completed=False, error='Host timeout; target MMIO completion is unknown')
            result['elapsed_seconds'] = time.monotonic() - start
    (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
