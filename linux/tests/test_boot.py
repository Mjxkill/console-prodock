#!/usr/bin/env python3
"""Boot real RV32 software on QEMU virt; this is not an AE350 simulation."""
from pathlib import Path
import subprocess
p = Path(__file__).resolve().parents[1] / 'build'
cmd = ['qemu-system-riscv32', '-machine', 'virt', '-cpu', 'rv32', '-m', '256M',
       '-smp', '1', '-nographic', '-monitor', 'none', '-no-reboot',
       '-bios', str(p / 'opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin'),
       '-kernel', str(p / 'kernel/arch/riscv/boot/Image'),
       '-append', 'console=ttyS0 earlycon=sbi panic=1 kunit.enable=1 prodock.selftest=1']
try:
    r = subprocess.run(cmd, capture_output=True, timeout=90)
    log = r.stdout + r.stderr
except subprocess.TimeoutExpired as e:
    (p / 'qemu-boot.log').write_bytes((e.stdout or b'') + (e.stderr or b''))
    raise
(p / 'qemu-boot.log').write_bytes(log)
required = [b'PRODOCK_USERSPACE_SELFTEST_OK', b'PRODOCK_LINUX_BOOT_OK',
            b'PRODOCK_RUNTIME_OK',
            b'pass:6 fail:0 skip:0 total:6']
if r.returncode or any(x not in log for x in required) or any(x in log for x in [b'not ok', b'Kernel panic', b'BUG:']):
    raise SystemExit(log[-10000:].decode(errors='replace'))
print('PASS: Linux RV32, BusyBox, userspace ABI and six kernel GPU boundary tests')
