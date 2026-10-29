#!/usr/bin/env python3
"""Check actual GPU command reuse of the sky on both framebuffer pages.

The first frame generates the gradient into scratch; the next uses COPY
without regeneration. Both are executed sequentially by the integer oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
GAME = ROOT/'games/luma3d'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out/'capture_two.c'
    source.write_text(r'''
#include "luma3d_render.h"
#include <stdlib.h>
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    L3World world;L3Game game;L3Render render;l3_world_init(&world);
    if(!l3_game_init(&game,&world,1)||!l3_render_open(&render,1,0))return 1;
    unsigned steps=(unsigned)strtoul(argv[2],NULL,10);
    for(unsigned i=0;i<steps;i++)l3_game_step(&game,NULL,1.0f/60);
    char path[2048];snprintf(path,sizeof(path),"%s.commands",argv[1]);
    render.capture=fopen(path,"wb");if(!render.capture)return 1;
    int ok=l3_render_frame(&render,&game)&&l3_render_frame(&render,&game);
    if(fclose(render.capture))ok=0;render.capture=NULL;
    if(!l3_render_dump(&render,argv[1]))ok=0;
    if(!l3_render_close(&render))ok=0;
    return !ok;
}
''')
    files = [GAME/'src/game.c',GAME/'src/world.c',GAME/'src/render.c',
             GAME/'world/data.c',ROOT/'fw_console/gpu_v1.c',ROOT/'fw_console/gpu_geometry.c']
    command = ['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
               '-ffunction-sections','-fdata-sections','-ffp-contract=off',
               *['-I'+str(x) for x in [GAME/'include',GAME/'world',ROOT/'fw_console',ROOT/'linux/drivers']],
               str(source),*[str(f) for f in files],'-Wl,--gc-sections','-lm','-o',str(out/'capture_two')]
    subprocess.run(command,check=True)
    records=[]
    for pose in (0,700,1600,2200):
        prefix=out/f'pose_{pose}'
        subprocess.run([str(out/'capture_two'),str(prefix),str(pose)],check=True,stdout=subprocess.DEVNULL)
        raw=Path(str(prefix)+'.commands').read_bytes()
        words=list(struct.iter_unpack('<8I',raw))
        assert sum(c[0]>>24==22 and c[1]==0x00e00000 for c in words)==1
        assert sum(c[0]>>24==29 for c in words)==2
        assert sum(c[0]>>24==27 for c in words)==2 # only initial Gouraud sky
        metadata=Path(str(prefix)+'.json');info=json.loads(metadata.read_text())
        assert info['page']==1
        info['commands']=len(words);metadata.write_text(json.dumps(info)+'\n')
        subprocess.run(['python3',str(GAME/'tools/render_reference.py'),str(prefix)],check=True,stdout=subprocess.DEVNULL)
        rendered=Path(str(prefix)+'.rgb565').read_bytes()
        expected=(GAME/'build/frozen_20261024_r1'/f'frame_{pose}.rgb565').read_bytes()
        differences=sum(rendered[i:i+2]!=expected[i:i+2] for i in range(0,len(expected),2))
        records.append(dict(pose=pose,page=1,commands=len(words),different_pixels=differences))
        assert differences==0
    result=dict(passed=True,hardware_validation=False,records=records,
                input_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
