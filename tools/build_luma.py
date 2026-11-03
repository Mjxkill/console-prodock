#!/usr/bin/env python3
"""Build the downloadable Luma firmware and bind it to the R31 FPGA/assets."""
from pathlib import Path
import hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    subprocess.run(['python3',str(ROOT/'tools/build_luma_assets.py')],check=True)
    subprocess.run(['make','-s','-C',str(ROOT/'fw_console'),'MAIN='+str(ROOT/'games/luma/src/luma_main.c'),'BUILD=build/luma','LD='+str(ROOT/'games/luma/src/luma.ld')],check=True)
    out=ROOT/'games/luma/assets/packed';binary=ROOT/'fw_console/build/luma/console_test.bin';elf=binary.with_suffix('.elf')
    nm=subprocess.check_output(['make','-s','-C',str(ROOT/'fw_console'),'print-nm'],text=True).strip()
    symbols=subprocess.check_output([nm,str(elf)],text=True)
    entry=int(next(s.split()[0] for s in symbols.splitlines() if s.endswith(' T _start')),16)
    assert 0xa0000000<=entry<0xa0010000 and binary.stat().st_size<=65536
    (out/'luma_fw.bin').write_bytes(binary.read_bytes())
    sources=['TESTS/test_luma_bloom.py','tools/build_luma.py','tools/build_luma_assets.py','tools/load_luma.py','tools/render_luma.py','tools/check_luma.py',
             'games/luma/src/luma_main.c','games/luma/src/luma_scene.h','games/luma/src/luma_fx_scene.h','games/luma/src/luma_assets.h',
             'games/luma/src/luma.ld','fw_console/gpu.c','fw_console/gpu_raster_commands.c','fw_console/gpu.h','fw_console/gpu_v1.c','fw_console/gpu_v1.h','fw_console/Makefile']
    m=dict(entry=entry,load=0xa0000000,bytes=binary.stat().st_size,sha256=sha(binary),assets_sha256=sha(out/'luma.bin'),
           fpga_sha256=json.loads((ROOT/'bitstreams/console_gpu_v1_800.validation.json').read_text())['sha256'],sources={p:sha(ROOT/p) for p in sources})
    (out/'firmware.json').write_text(json.dumps(m,indent=2)+'\n');print('Luma: downloadable ILM firmware ready')
if __name__=='__main__':main()
