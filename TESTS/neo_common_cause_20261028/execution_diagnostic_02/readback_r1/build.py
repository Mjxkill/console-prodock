#!/usr/bin/env python3
"""Build CPU read-only followup; no programmer/debugger invocation."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
TC = Path('/home/michael/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin')


def main():
    out = HERE / 'build_01'
    out.mkdir()
    elf, binary = out / 'readback.elf', out / 'readback.bin'
    subprocess.run([str(TC/'riscv-none-elf-gcc'), '-march=rv32im_zicsr_zifencei', '-mabi=ilp32',
                    '-nostdlib', '-nostartfiles', '-Wl,--no-relax', '-Wl,--build-id=none',
                    '-Wl,-Ttext=0xa0005000', str(HERE/'readback.S'), '-o', str(elf)],
                   check=True, capture_output=True, timeout=30)
    subprocess.run([str(TC/'riscv-none-elf-objcopy'), '-O', 'binary', str(elf), str(binary)],
                   check=True, capture_output=True, timeout=10)
    listing = subprocess.run([str(TC/'riscv-none-elf-objdump'), '-d', '-s', str(elf)],
                             check=True, capture_output=True, text=True, timeout=10).stdout
    (out/'listing.txt').write_text(listing)
    assert 0 < binary.stat().st_size <= 4096
    result = {'built': True, 'hardware_access': False, 'code_address': 0xa0005000,
              'code_bytes': binary.stat().st_size, 'journal_address': 0xa0006400,
              'journal_bytes': 256, 'scratch_read_address': 0x12000000,
              'scratch_read_bytes': 128, 'ddr_writes': 0, 'gpu_commands': 0,
              'files': {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [Path(__file__), HERE/'readback.S', elf, binary, out/'listing.txt']}}
    (out/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
