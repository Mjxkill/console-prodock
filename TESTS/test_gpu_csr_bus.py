#!/usr/bin/env python3
"""AHB pipelined CSR reads/writes, reset abort, all address holes and bus stage."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    sources=['TESTS/rtl/gpu_csr_bus_tb.sv']+['tang/rtl/video/'+s+'.v' for s in
      ['gpu_accel','video_bus_stage','gpu_geometry','gpu_geom_div','blitter','gpu_raster','gpu_v1',
       'gpu_texture_cache','gpu_copy565','gpu_perspective','gpu_triangle','gpu_blit_dma','font_ram']]
    sources+=['tang/rtl/board/'+s+'.v' for s in ['ddr_dcfifo','cdc_word']]
    report=dict(status='FAIL',cases=[],sources={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources})
    try:
        for staged in (0,1):
            work=out/str(staged);work.mkdir()
            shutil.copyfile(ROOT/'tang/rtl/video/font8x16.hex',work/'font8x16.hex')
            with (work/'build.log').open('w') as log:
                subprocess.run(['verilator','--binary','-j','4','--timing','-Wno-fatal','--top-module','gpu_csr_bus_tb',
                  f'-GSTAGED={staged}','--Mdir',str(work/'obj'),*[str(ROOT/s) for s in sources]],stdout=log,stderr=log,check=True)
            with (work/'simulation.log').open('w') as log:
                subprocess.run([str(work/'obj/Vgpu_csr_bus_tb')],cwd=work,stdout=log,stderr=log,check=True,timeout=60)
            text=(work/'simulation.log').read_text();assert 'PASS CSR' in text
            report['cases'].append(dict(staged=staged,log=text));print(text,flush=True)
        report['status']='PASS'
    finally:(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
