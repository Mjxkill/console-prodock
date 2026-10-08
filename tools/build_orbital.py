#!/usr/bin/env python3
"""Build the downloadable Orbital firmware and bind it to the R31 FPGA/assets."""
from pathlib import Path
import hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
TC=Path('/home/michael/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin/riscv-none-elf-nm')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    subprocess.run(['python3',str(ROOT/'tools/build_orbital_assets.py')],check=True)
    subprocess.run(['make','-s','-C',str(ROOT/'fw_console'),'MAIN=orbital_main.c','BUILD=build/orbital','LD='+str(ROOT/'fw_console/orbital.ld')],check=True)
    out=ROOT/'assets/orbital/packed';binary=ROOT/'fw_console/build/orbital/console_test.bin';elf=binary.with_suffix('.elf')
    symbols=subprocess.check_output([str(TC),str(elf)],text=True)
    entry=int(next(s.split()[0] for s in symbols.splitlines() if s.endswith(' T _start')),16)
    assert 0xa0000000<=entry<0xa0010000 and binary.stat().st_size<=65536
    (out/'orbital_fw.bin').write_bytes(binary.read_bytes())
    sources=['tools/build_orbital.py','tools/build_orbital_assets.py','tools/load_orbital.py','tools/render_orbital.py','tools/check_orbital.py',
             'fw_console/orbital_main.c','fw_console/orbital_scene.h','fw_console/orbital_assets.h',
             'fw_console/orbital.ld','fw_console/gpu.c','fw_console/gpu.h','fw_console/gpu_v1.c','fw_console/gpu_v1.h','fw_console/Makefile']
    m=dict(entry=entry,load=0xa0000000,bytes=binary.stat().st_size,sha256=sha(binary),assets_sha256=sha(out/'orbital.bin'),
           fpga_sha256=sha(ROOT/'bitstreams/console_gpu_v1_800.fs'),sources={p:sha(ROOT/p) for p in sources})
    (out/'firmware.json').write_text(json.dumps(m,indent=2)+'\n');print('Orbital: downloadable ILM firmware ready')
if __name__=='__main__':main()
