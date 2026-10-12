#!/usr/bin/env python3
"""Replay three actual NEBULA scenes through RTL and compare every LCD pixel.

The C game produces resources and descriptors. The independent Python painter
executes the game's raster commands; Verilator checks the resulting composition
against the real scanout, tile and sprite RTL. This is not a GPU speed benchmark.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    sources=['TESTS/rtl/nebula_scanout_tb.sv','tang/rtl/video/gpu_scanout.v',
             'tang/rtl/video/gpu_line_reader.v','tang/rtl/video/gpu_tile_row.v',
             'tang/rtl/video/gpu_sprite_cache.v','tang/rtl/video/gpu_rgb_reader.v',
             'tang/rtl/board/cdc_word.v']
    result={'passed':False,'scenes':[], 'sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources}}
    with tempfile.TemporaryDirectory(prefix='nebula-rtl-') as directory:
        work=Path(directory)
        def run(name,args):
            with (out/(name+'.log')).open('w') as log:
                subprocess.run(list(map(str,args)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        run('host_build',['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-DNEBULA_HOST',
                         '-I',ROOT/'linux/drivers',ROOT/'linux/userspace/nebula.c','-lm','-o',work/'game'])
        run('rtl_build',['verilator','--binary','-j','4','--timing','-Wno-fatal','--top-module',
                        'nebula_scanout_tb','--Mdir',work/'obj',*[ROOT/s for s in sources]])
        for name,pose,boss in [('wave700',700,False),('boss310',310,True),('nova5740',5740,False)]:
            capture=work/name
            run(name+'_game',[work/'game','--pose',pose,'--frames',1,'--assets',ROOT/'assets/nebula/packed/nebula.bin',
                             '--capture',capture,*(['--boss'] if boss else [])])
            run(name+'_reference',['python3',ROOT/'tools/preview_nebula.py',capture,'--scanout-inputs',work/'inputs'])
            run(name+'_rtl',[work/'obj/Vnebula_scanout_tb','+inputs='+str(work/'inputs')])
            log=(out/(name+'_rtl.log')).read_text()
            assert 'pixels=384000 mismatches=0' in log and 'underflows=0' in log,log
            reference=json.loads(capture.with_suffix('.reference.json').read_text())
            reference['preview']=str(out/(name+'.png'));result['scenes'].append(reference)
            for suffix in ['png','json']:shutil.copy2(capture.with_suffix('.'+suffix),out/(name+'.'+suffix))
            (out/(name+'.reference.json')).write_text(json.dumps(reference,indent=2)+'\n')
            print(name,reference['frame_crc32'],reference['lcd_rgb666_sum'],'384000 pixels match RTL',flush=True)
    result['passed']=True;(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
