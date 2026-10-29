#!/usr/bin/env python3
"""Build ILM-only diagnostic; never invokes a programmer or debugger."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
TC=Path('/home/michael/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    out=HERE/'build_01';out.mkdir()
    elf=out/'microdma.elf';binary=out/'microdma.bin'
    commands=[
        [str(TC/'riscv-none-elf-gcc'),'-march=rv32im_zicsr_zifencei','-mabi=ilp32',
         '-nostdlib','-nostartfiles','-Wl,--no-relax','-Wl,--build-id=none',
         '-Wl,-Ttext=0xa0004000',str(HERE/'microdma.S'),'-o',str(elf)],
        [str(TC/'riscv-none-elf-objcopy'),'-O','binary',str(elf),str(binary)],
    ]
    for command in commands:subprocess.run(command,check=True,capture_output=True,timeout=30)
    listing=subprocess.run([str(TC/'riscv-none-elf-objdump'),'-d','-s',str(elf)],
                           check=True,capture_output=True,text=True,timeout=10).stdout
    (out/'listing.txt').write_text(listing)
    assert 0<len(binary.read_bytes())<=4096
    result=dict(built=True,hardware_access=False,code_address=0xa0004000,
        code_bytes=binary.stat().st_size,journal_address=0xa0006000,journal_bytes=512,
        scratch_address=0x12000000,scratch_bytes=128,
        files={str(p.relative_to(HERE)):sha(p) for p in [HERE/'microdma.S',Path(__file__),elf,binary,out/'listing.txt']})
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
