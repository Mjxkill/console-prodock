#!/usr/bin/env python3
"""L12: real firmware commands/assets, independent Python affine reference."""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from PIL import Image
from render_gpu_demo import ROOT, brace_block


def render(pose, output, hardware_log=None):
    firmware=ROOT/'fw_console'
    driver=(firmware/'gpu.c').read_text()
    base=(firmware/'gpu_demo.h').read_text().split('static int gpu_accel_demo(void)',1)[0]
    demo=(firmware/'gpu_affine_demo.h').read_text()
    hud=demo[demo.index('    gpu_text(5,'):demo.index('    if(!gpu_wait())return 0;',demo.index('    gpu_text(5,'))]
    source='''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "gpu.h"
static uint8_t pages[8][GPU_PAGE_BYTES];
#undef GPU_PAGE_ADDR
#define GPU_PAGE_ADDR(p) ((uintptr_t)pages[p])
'''+''.join(brace_block(driver,'gpu_command '+name+'(')+'\n' for name in
            ('gpu_make_command','gpu_make_affine_setup','gpu_make_affine'))+base+'''
void gpu_submit(const gpu_command *c){reference_draw(c,pages[(c->words[0]>>20)&15]);}
'''+brace_block(driver,'void gpu_text(')+'''
#include "gpu_affine_scene.h"
static gpu_command commands[32];
static unsigned count;
static void capture(const gpu_command *c){assert(count<32);commands[count++]=*c;}
int main(int argc,char **argv){
    for(unsigned angle=0;angle<256;++angle){
        count=0;affine_scene(6,angle,capture);assert(count==13);
    }
    gpu_command invalid=gpu_make_affine(6,15,32768,0,128,128,0,0,128,128);
    assert(invalid.words[2]==0);
    invalid=gpu_make_affine(6,15,0,0,128,128,799,479,2,2);assert(invalid.words[2]==0);
'''+hud+'''
    count=0;affine_scene(6,affine_poses[atoi(argv[1])],capture);
    fwrite(&count,4,1,stdout);fwrite(commands,32,count,stdout);
    for(unsigned y=0;y<128;++y)for(unsigned x=0;x<128;++x)putchar(affine_asset(x,y));
    fwrite(pages[5],1,800*480,stdout);
    for(unsigned i=0;i<256;++i){uint32_t c=gpu_demo_palette_color(i);fwrite(&c,4,1,stdout);}
}
'''
    with tempfile.TemporaryDirectory(prefix='gpu_affine_render_') as directory:
        work=Path(directory);(work/'scene.c').write_text(source)
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Wno-unused-function',
                        '-Wno-unused-variable','-Wno-unused-parameter','-fsanitize=undefined',
                        '-fno-sanitize-recover=all','-I',str(firmware),str(work/'scene.c'),
                        '-o',str(work/'scene')],check=True)
        raw=subprocess.run([str(work/'scene'),str(pose)],check=True,capture_output=True).stdout
    count,=struct.unpack_from('<I',raw)
    assert len(raw)==4+count*32+128*128+800*480+1024
    asset=raw[4+count*32:4+count*32+128*128]
    indices=bytearray(800*480)
    matrix=None
    for i in range(count):
        w=struct.unpack_from('<8I',raw,4+32*i)
        op=w[0]>>24
        if op==12:
            matrix=struct.unpack('<6i',struct.pack('<6I',*w[1:7]));continue
        signed=lambda v:v if v<32768 else v-65536
        x,y,width,height=[signed((v>>shift)&65535) for v in w[1:3] for shift in (16,0)]
        for yy in range(max(y,0),min(y+height,480)):
            for xx in range(max(x,0),min(x+width,800)):
                if op==1:indices[yy*800+xx]=(w[0]>>8)&255
                elif op==13:
                    u0,v0,ux,vx,uy,vy=matrix
                    u=(u0+(xx-x)*ux+(yy-y)*uy)//65536
                    v=(v0+(xx-x)*vx+(yy-y)*vy)//65536
                    if 0<=u<128 and 0<=v<128 and asset[v*128+u]:indices[yy*800+xx]=asset[v*128+u]
                else:raise AssertionError(op)
    hud=raw[-1024-800*480:-1024]
    indices=bytes(h or c for h,c in zip(hud,indices))
    rotate=lambda v,n:((v<<(n&31))|(v>>((32-n)&31)))&0xffffffff
    checksum=0
    for offset in range(0,len(indices),32):
        block=0
        for i,word in enumerate(struct.unpack_from('<8I',indices,offset)):block^=rotate(word,i*4)
        checksum=rotate(checksum,5)^block
    if hardware_log:
        found=re.findall(rf'AFFINE POSE {pose} hash=([0-9a-fA-F]+)',hardware_log.read_text())
        if not found or any(int(h,16)!=checksum for h in found):raise SystemExit(f'Hardware differs from {checksum:08x}')
    palette=[]
    for (color,) in struct.iter_unpack('<I',raw[-1024:]):
        palette.extend((((color>>shift)&63)*255+31)//63 for shift in (12,6,0))
    picture=Image.frombytes('P',(800,480),indices);picture.putpalette(palette)
    output.parent.mkdir(parents=True,exist_ok=True);picture.convert('RGB').save(output)
    print(f'{output}: pose {pose}, hash {checksum:08x}, commands {count}'+(', matches hardware log' if hardware_log else ', software reference'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pose',type=int,choices=range(4),default=0)
    p.add_argument('--output',type=Path)
    p.add_argument('--hardware-log',type=Path)
    a=p.parse_args();render(a.pose,a.output or ROOT/f'TESTS/images/gpu_l12_pose{a.pose}_expected.png',a.hardware_log)
