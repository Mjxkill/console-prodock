#!/usr/bin/env python3
"""Build ASTRILLA for the qualified C37 FPGA. No FPGA synthesis or programming."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
TC=Path('/home/michael/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin/riscv-none-elf-nm')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    font=bytes(int(v,16) for v in (ROOT/'tang/rtl/video/font8x16.hex').read_text().split())[32*16:91*16]
    (ROOT/'fw_console/astrilla_hud_font.h').write_text('// Generated from the FPGA console font: ASCII 32..90.\nstatic const unsigned char as_hud_font[]={\n'+','.join(str(v) for v in font)+'\n};\n')
    subprocess.run(['python3',str(ROOT/'tools/build_astrilla_meshes.py')],check=True)
    subprocess.run(['python3',str(ROOT/'tools/build_astrilla_assets.py')],check=True)
    subprocess.run(['make','-s','-C',str(ROOT/'fw_console'),'MAIN=astrilla_main.c','BUILD=build/astrilla','CFLAGS_EXTRA=-ffp-contract=off','LD='+str(ROOT/'fw_console/astrilla.ld')],check=True)
    out=ROOT/'assets/astrilla/packed';binary=ROOT/'fw_console/build/astrilla/console_test.bin'
    symbols=subprocess.check_output([str(TC),str(binary.with_suffix('.elf'))],text=True)
    entry=int(next(s.split()[0] for s in symbols.splitlines() if s.endswith(' T _start')),16)
    if not 0xa0000000<=entry<0xa0000000+binary.stat().st_size<=0xa0010000:raise RuntimeError('ASTRILLA outside ILM')
    (out/'astrilla_fw.bin').write_bytes(binary.read_bytes())
    sources=['tools/load_astrilla.py','tools/check_astrilla.py','tools/render_astrilla.py','tools/astra_preview_model.py','tools/build_astrilla.py','tools/build_astrilla_assets.py','fw_console/astrilla_main.c','fw_console/astrilla_scene.h','fw_console/astrilla_assets.h','fw_console/astrilla.ld','fw_console/gpu.c','fw_console/gpu_raster_commands.c','fw_console/gpu.h','fw_console/gpu_v1.c','fw_console/gpu_v1.h','fw_console/Makefile']
    sources += ['fw_console/astrilla_hud.h','fw_console/astrilla_hud_font.h','tang/rtl/video/font8x16.hex','tools/build_astrilla_meshes.py','fw_console/astrilla_meshes.h','fw_console/astrilla_3d.h','fw_console/astrilla_flight.h']
    m=dict(entry=entry,load=0xa0000000,bytes=binary.stat().st_size,sha256=sha(binary),assets_sha256=sha(out/'astrilla.bin'),
           fpga_sha256='6f47a8cdab5857a0b652f791ff61fbed9a26c3c7ba7f4f30de01da95f0c076e2',sources={p:sha(ROOT/p) for p in sources})
    (out/'firmware.json').write_text(json.dumps(m,indent=2)+'\n');print('ASTRILLA ILM ready:',m['bytes'],'bytes, entry',hex(entry))
if __name__=='__main__':main()
