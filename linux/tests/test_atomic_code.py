#!/usr/bin/env python3
"""Reject native cold atomics in the actual linked production binaries."""
import os
from pathlib import Path
import re
import subprocess
HERE = Path(__file__).resolve().parents[1]
BUILD = HERE / ('build-neo' if os.environ.get('CONSOLE_BOARD')=='neo' else 'build')
objdump = HERE / 'build' / 'riscv32-ilp32d--musl--stable-2025.08-1/bin/riscv32-buildroot-linux-musl-objdump'
files = [('kernel/vmlinux', True), ('opensbi/platform/generic/firmware/fw_payload.elf', False),
         ('busybox/busybox_unstripped', False), ('rootfs/bin/prodockctl', False),
         ('rootfs/bin/prodock-runtime', False)]
files += [('rootfs/bin/' + name, False) for name in
          ['prodock-terminal', 'prodock-game', 'prodock-text-test', 'nebula']]
if os.environ.get('CONSOLE_BOARD')!='neo':files.append(('uboot/out/u-boot',False))
total = 0
for name, kernel in files:
    # SBI's executable .payload embeds the kernel/initramfs as raw bytes;
    # disassembling that data would produce false instructions.
    extra = ['--stop-address=0x08000000'] if name.startswith('opensbi/') else []
    text = subprocess.check_output([objdump, '-d', *extra, BUILD / name], text=True)
    instructions = []
    for line in text.splitlines():
        match = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+([\w.]+)\s*(.*)', line)
        if match: instructions.append(match.groups())
    count = 0
    for i, (address, opcode, args) in enumerate(instructions):
        if not (opcode.startswith('amo') or opcode.startswith('lr.w')): continue
        if kernel: raise SystemExit('Native kernel atomic at ' + address)
        if i < 2 or instructions[i-1][1:] != ('fence', 'r,rw') or instructions[i-2][1] not in ('lw', 'lwsp'):
            raise SystemExit(f'Atomic without preload/fence: {name}:{address}')
        target = re.search(r'\((\w+)\)', args)
        load = re.search(r'\((\w+)\)', instructions[i-2][2])
        if not target or not load or target[1] != load[1]:
            raise SystemExit(f'Wrong preload target: {name}:{address}')
        count += 1
    total += count
    print(f'PASS {name}: {count} preloaded AMO/LR, no unprotected native atomic')
if total == 0: raise SystemExit('No code audited')
