#!/usr/bin/env python3
"""Independent 1280x720 pixel checks, including ordered delayed DDR returns."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
p.add_argument('--neo-request-queue',action='store_true',help='Include the Neo registered request path')
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
sources=['TESTS/rtl/gpu_720p_tb.sv',*[f'tang/rtl/video/{s}.v' for s in
         ['gpu_scanout','gpu_line_reader','gpu_tile_row','gpu_sprite_cache','gpu_rgb_reader']], 'tang/rtl/board/cdc_word.v',
         'tang/boards/neo/neo_scan_queue.v']
report={'passed':False,'request_queue':a.neo_request_queue,'sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'modes':[]}
with tempfile.TemporaryDirectory(prefix='neo-720p-') as tmp:
    def run(name,args):
        with (out/(name+'.log')).open('w') as f:subprocess.run(list(map(str,args)),cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
    run('build',['verilator','--binary','-j','4','--timing','-Wno-fatal','--top-module','gpu_720p_tb',
                 f'-GREQUEST_QUEUE={int(a.neo_request_queue)}','--Mdir',tmp,*sources])
    for mode in range(6):
        run(f'mode{mode}',[Path(tmp)/'Vgpu_720p_tb',f'+mode={mode}'])
        log=(out/f'mode{mode}.log').read_text()
        assert 'pixels=921600 mismatches=0 uf=0' in log,log
        report['modes'].append(log.splitlines()[0]);print(log.splitlines()[0],flush=True)
report['passed']=True;(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
