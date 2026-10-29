"""Fixed sandbox-compatible assembler; outputs only to an explicit fresh dir."""
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent

def build(out):
    out=Path(out);out.mkdir()
    elf=out/'microdma.elf';binary=out/'microdma.bin'
    command=['/usr/bin/riscv64-unknown-elf-gcc','-march=rv32im_zicsr_zifencei','-mabi=ilp32',
             '-nostdlib','-nostartfiles','-Wl,--no-relax','-Wl,--build-id=none',
             '-Wl,-Ttext=0xa0004000',str(HERE/'microdma.S'),'-o',str(elf)]
    subprocess.run(command,check=True,capture_output=True,timeout=20)
    subprocess.run(['/usr/bin/riscv64-unknown-elf-objcopy','-O','binary',str(elf),str(binary)],
                   check=True,capture_output=True,timeout=10)
    listing=subprocess.run(['/usr/bin/riscv64-unknown-elf-objdump','-d','-s',str(elf)],
                           check=True,capture_output=True,text=True,timeout=10).stdout
    (out/'listing.txt').write_text(listing)
    assert 0<len(binary.read_bytes())<=4096
    assert 0xa0004000+len(binary.read_bytes())<=0xa0005000<0xa0006000
    return binary
