#!/usr/bin/env python3
"""Build ASTRA for the qualified C37 FPGA. No FPGA synthesis or programming."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
TC=Path('/home/michael/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin/riscv-none-elf-nm')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    subprocess.run(['python3',str(ROOT/'tools/build_astra_assets.py')],check=True)
    subprocess.run(['make','-s','-C',str(ROOT/'fw_console'),'MAIN=astra_main.c','BUILD=build/astra','LD='+str(ROOT/'fw_console/astra.ld')],check=True)
    out=ROOT/'assets/astra/packed';binary=ROOT/'fw_console/build/astra/console_test.bin'
    symbols=subprocess.check_output([str(TC),str(binary.with_suffix('.elf'))],text=True)
    entry=int(next(s.split()[0] for s in symbols.splitlines() if s.endswith(' T _start')),16)
    if not 0xa0000000<=entry<0xa0000000+binary.stat().st_size<=0xa0010000:raise RuntimeError('ASTRA outside ILM')
    (out/'astra_fw.bin').write_bytes(binary.read_bytes())
    sources=['tools/build_astra.py','tools/build_astra_assets.py','fw_console/astra_main.c','fw_console/astra_scene.h','fw_console/astra_assets.h','fw_console/astra.ld','fw_console/gpu.c','fw_console/gpu.h','fw_console/gpu_v1.c','fw_console/gpu_v1.h','fw_console/Makefile']
    m=dict(entry=entry,load=0xa0000000,bytes=binary.stat().st_size,sha256=sha(binary),assets_sha256=sha(out/'astra.bin'),
           fpga_sha256='6f47a8cdab5857a0b652f791ff61fbed9a26c3c7ba7f4f30de01da95f0c076e2',sources={p:sha(ROOT/p) for p in sources})
    (out/'firmware.json').write_text(json.dumps(m,indent=2)+'\n');print('ASTRA ILM ready:',m['bytes'],'bytes, entry',hex(entry))
if __name__=='__main__':main()
