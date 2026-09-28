#!/usr/bin/env python3
"""Exact G5 reference: firmware geometry, independent Python rasterization."""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from PIL import Image
from render_gpu_demo import ROOT, brace_block
sys.path.insert(0,str(ROOT/'TESTS'))
from test_gpu_accel import triangle_pixels


def render(pose,output,hardware_log=None):
    firmware=ROOT/'fw_console'
    driver=(firmware/'gpu.c').read_text()
    base=(firmware/'gpu_demo.h').read_text().split('static int gpu_accel_demo(void)',1)[0]
    demo=(firmware/'gpu_3d_demo.h').read_text()
    hud=demo[demo.index('    gpu_text(5,'):demo.index('    if(!gpu_wait())return 0;',demo.index('    gpu_text(5,'))]
    angles=re.search(r'demo3d_poses\[4\]=\{([^}]+)\}',demo)[1]
    source='''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "gpu.h"
static uint8_t pages[8][GPU_PAGE_BYTES];
#undef GPU_PAGE_ADDR
#define GPU_PAGE_ADDR(p) ((uintptr_t)pages[p])
'''+brace_block(driver,'gpu_command gpu_make_command(')+'\n'+base+'''
void gpu_submit(const gpu_command *c){reference_draw(c,pages[(c->words[0]>>20)&15]);}
'''+brace_block(driver,'void gpu_text(')+'''
#include "gpu_3d_scene.h"
int main(int argc,char **argv) {
    for(unsigned a=0;a<512;++a)for(int close=0;close<2;++close) {
        scene3d_build(6,a,close);assert(scene3d_count<96);
        for(unsigned i=1;i<scene3d_count;++i) {
            assert(scene3d_commands[i].words[0]>>24==GPU_LINE || scene3d_commands[i].words[0]>>24==GPU_TRIANGLE);
        }
    }
    gpu_vec3 crossing[4]={{-3,-2,50},{3,-2,150},{3,2,150},{-3,2,50}},out[5];
    int n=scene3d_clip(crossing,4,out,100);assert(n==4);
    for(int i=0;i<n;++i)assert(out[i].z>=100);
    n=scene3d_clip(crossing,4,out,200);assert(n==0);
    n=scene3d_clip(crossing,4,out,1);assert(n==4);
'''+hud+f'''    const unsigned angles[4]={{{angles}}};
    unsigned pose=(unsigned)atoi(argv[1]);
    scene3d_build(6,angles[pose],pose==3);
    if(pose==3)assert(scene3d_clipped>0);
    uint32_t header[3]={{scene3d_count,scene3d_triangles,scene3d_clipped}};
    fwrite(header,4,3,stdout);fwrite(scene3d_commands,32,scene3d_count,stdout);
    fwrite(pages[5],1,800*480,stdout);
    for(unsigned i=0;i<256;++i){{uint32_t color=gpu_demo_palette_color(i);fwrite(&color,4,1,stdout);}}
    return 0;
}}
'''
    with tempfile.TemporaryDirectory(prefix='gpu_3d_render_') as directory:
        work=Path(directory);(work/'scene.c').write_text(source)
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-variable',
                        '-Wno-unused-parameter','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-I',str(firmware),str(work/'scene.c'),'-o',str(work/'scene')],check=True)
        raw=subprocess.run([str(work/'scene'),str(pose)],check=True,capture_output=True).stdout
    count,triangles,clipped=struct.unpack_from('<3I',raw)
    assert len(raw)==12+count*32+800*480+1024
    indices=bytearray(800*480)
    def plot(x,y,color):
        if 0<=x<800 and 0<=y<480:indices[y*800+x]=color
    for i in range(count):
        words=struct.unpack_from('<8I',raw,12+32*i)
        op,color=words[0]>>24,(words[0]>>8)&255
        signed=lambda v: v if v<32768 else v-65536
        x,y,a,b,sx,sy=[signed((w>>shift)&65535) for w in words[1:4] for shift in (16,0)]
        if op==1:
            for yy in range(max(0,y),min(480,y+b)):
                for xx in range(max(0,x),min(800,x+a)):plot(xx,yy,color)
        elif op==5:
            dx,dy=abs(a-x),abs(b-y);ex=1 if x<a else -1;ey=1 if y<b else -1;err=dx-dy
            while True:
                plot(x,y,color)
                if (x,y)==(a,b):break
                e=err*2
                if e>-dy:err-=dy;x+=ex
                if e<dx:err+=dx;y+=ey
        elif op==10:
            for xx,yy in triangle_pixels(x,y,a,b,sx,sy):plot(xx,yy,color)
        else:raise AssertionError(f'Unexpected 3D command {op}')
    hud=raw[12+32*count:-1024]
    indices=bytes(h or c for c,h in zip(indices,hud))
    rotate=lambda v,n:((v<<(n&31))|(v>>((32-n)&31)))&0xffffffff
    checksum=0
    for offset in range(0,len(indices),32):
        block=0
        for i,word in enumerate(struct.unpack_from('<8I',indices,offset)):block^=rotate(word,i*4)
        checksum=rotate(checksum,5)^block
    if hardware_log:
        expected=re.findall(rf'THREED POSE {pose} hash=([0-9a-fA-F]+)',hardware_log.read_text())
        if not expected or any(int(v,16)!=checksum for v in expected):raise SystemExit(f'Hardware differs from {checksum:08x}')
    palette=[]
    for (rgb,) in struct.iter_unpack('<I',raw[-1024:]):
        palette.extend((((rgb>>shift)&63)*255+31)//63 for shift in (12,6,0))
    picture=Image.frombytes('P',(800,480),indices);picture.putpalette(palette)
    output.parent.mkdir(parents=True,exist_ok=True);picture.convert('RGB').save(output)
    print(f'{output}: pose {pose}, hash {checksum:08x}, commands {count}, triangles {triangles}, clipped faces {clipped}'+(', matches hardware log' if hardware_log else ', software reference'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pose',type=int,choices=range(4),default=0)
    p.add_argument('--output',type=Path)
    p.add_argument('--hardware-log',type=Path)
    a=p.parse_args();render(a.pose,a.output or ROOT/f'TESTS/images/gpu_g5_pose{a.pose}_expected.png',a.hardware_log)
