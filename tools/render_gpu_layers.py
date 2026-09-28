#!/usr/bin/env python3
"""Render a G3 demo pose from firmware-created surfaces and layer descriptors."""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

from PIL import Image
from render_gpu_demo import ROOT, brace_block

W,H,SLOT=800,480,1048576


def render(pose,output,hardware_log=None,sprites=False):
    if sys.byteorder!='little':
        raise SystemExit('The firmware text reference requires a little-endian host')
    firmware=ROOT/'fw_console'
    driver=(firmware/'gpu.c').read_text()
    demo=(firmware/'gpu_demo.h').read_text().split('static int gpu_accel_demo(void)',1)[0]
    layers=(firmware/'gpu_layers_demo.h').read_text()
    initialize=layers.split('static void gpu_layers_demo(void)',1)[1]
    initialize=initialize[initialize.index('    for(unsigned i=0;i<256;'):initialize.index('    if(!gpu_wait()) {printf("LAYERS FAIL TEXT')]
    make_layer=brace_block(driver,'gpu_layer gpu_make_layer(').replace('\n{\n',
        '\n{\n    base=base-(uintptr_t)pages+0x00800000UL;\n',1)
    source='''#include <stdint.h>
#include <stdio.h>
#include "gpu.h"
static uint8_t pages[16][GPU_PAGE_BYTES];
static gpu_layer scene_layers[16];
static uint32_t registers[512];
#undef GPU_PAGE_ADDR
#define GPU_PAGE_ADDR(p) ((uintptr_t)pages[(p)])
#define GPU registers
void gpu_publish_surface(unsigned long address,unsigned long bytes) {}
void gpu_font_write(unsigned address,const uint8_t *bytes,unsigned count) {}
'''+brace_block(driver,'gpu_command gpu_make_command(')+'\n'+demo+'''
void gpu_submit(const gpu_command *cmd) {reference_draw(cmd,pages[(cmd->words[0]>>20)&15]);}
'''+brace_block(driver,'void gpu_text(')+'\n'+make_layer+'\n'+brace_block(layers,'static void gpu_layers_make_pose(')
    sprite_initialize=''
    sprite_output=''
    if sprites:
        objects=(firmware/'gpu_sprites_demo.h').read_text()
        make_sprite=brace_block(driver,'gpu_sprite gpu_make_sprite(').replace('\n{\n',
            '\n{\n    base=base-(uintptr_t)textures+0x02000000UL;\n',1)
        source+='\nstatic uint8_t textures[3][64][1024];\nstatic gpu_sprite scene_sprites[64];\n'
        source+='#define SPRITE_IMAGE_ADDR(s,frame) ((uintptr_t)textures[(frame)][(s)])\n'
        for signature in ('static unsigned sprite_demo_size(', 'static unsigned sprite_demo_pixel('):
            source+=brace_block(objects,signature)+'\n'
        source+=make_sprite+'\n'+brace_block(objects,'static void gpu_sprites_make_pose(')+'\n'
        sprite_initialize=objects.split('static void gpu_sprites_demo(void)',1)[1]
        sprite_initialize=sprite_initialize[sprite_initialize.index('    for(unsigned pose=0;pose<3;'):sprite_initialize.index('    gpu_publish_surface(SPRITE_IMAGE_ADDR')]
        sprite_initialize+=f'\n    gpu_sprites_make_pose({pose});\n'
        sprite_output='    if(fwrite(textures,1,sizeof(textures),stdout)!=sizeof(textures)) return 1;\n    if(fwrite(scene_sprites,1,sizeof(scene_sprites),stdout)!=sizeof(scene_sprites)) return 1;\n'
    source+='\nint main(void) {\n'+initialize+f'\n    gpu_layers_make_pose({pose});\n'+sprite_initialize+'''
    if(fwrite(pages,1,sizeof(pages),stdout)!=sizeof(pages)) return 1;
    if(fwrite(scene_layers,1,sizeof(scene_layers),stdout)!=sizeof(scene_layers)) return 1;
'''+sprite_output+'''    if(fwrite(&registers[0x100],4,256,stdout)!=256) return 1;
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='console_layers_render_') as directory:
        work=Path(directory);(work/'build').mkdir();(work/'render.c').write_text(source)
        subprocess.run([sys.executable,str(ROOT/'tools/gen_gpu_font.py'),str(ROOT/'tang/rtl/video/font8x16.hex'),str(work/'build/gpu_font.h')],check=True)
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-variable',
                        '-I',str(firmware),str(work/'render.c'),'-o',str(work/'render')],check=True)
        raw=subprocess.run([str(work/'render')],check=True,capture_output=True).stdout
    if len(raw)!=16*SLOT+512+1024+(196608+1024 if sprites else 0):
        raise SystemExit('Unexpected surface/descriptor/palette data size')
    # Independent host composition of the descriptors produced by the C driver.
    indices=bytearray(W*H)
    def compose_layer(layer):
        base,wh,xy,view,scroll,stride,flags,_=struct.unpack_from('<8I',raw,16*SLOT+layer*32)
        if not flags&1:return
        signed=lambda v:v if v<32768 else v-65536
        x,y=signed(xy&65535),signed(xy>>16)
        sw,sh=wh&65535,wh>>16;vw,vh=view&65535,view>>16;sx,sy=scroll&65535,scroll>>16
        left,right=max(0,x),min(W,x+vw,x+sw-sx)
        top,bottom=max(0,y),min(H,y+vh,y+sh-sy)
        if left>=right or top>=bottom:return
        if stride<sw:raise SystemExit('Invalid source stride')
        for yy in range(top,bottom):
            start=base-0x00800000+(sy+yy-y)*stride+sx+left-x
            if not 0<=start<=16*SLOT-(right-left):raise SystemExit('Source outside surface memory')
            row=raw[start:start+right-left];at=yy*W+left
            if flags&2:row=bytes(p if p else old for p,old in zip(row,indices[at:at+len(row)]))
            indices[at:at+len(row)]=row
    for layer in range(16):
        compose_layer(layer)
        if not sprites:continue
        for slot in range(64):
            base,xy,prop,_=struct.unpack_from('<4I',raw,16*SLOT+512+196608+slot*16)
            if not prop&65536 or (prop>>20)&15!=layer:continue
            signed=lambda v:v if v<32768 else v-65536
            x,y=signed(xy&65535),signed(xy>>16)
            width,height=prop&255,(prop>>8)&255
            for yy in range(max(0,y),min(H,y+height)):
                for xx in range(max(0,x),min(W,x+width)):
                    sx=width-1-(xx-x) if prop&131072 else xx-x
                    sy=height-1-(yy-y) if prop&262144 else yy-y
                    value=raw[16*SLOT+512+base-0x02000000+sy*32+sx]
                    if value:indices[yy*W+xx]=value
    rotate=lambda v,n:((v<<(n&31))|(v>>((32-n)&31)))&0xffffffff
    checksum=0
    for offset in range(0,len(indices),32):
        block=0
        for i,word in enumerate(struct.unpack_from('<8I',indices,offset)):block^=rotate(word,i*4)
        checksum=rotate(checksum,5)^block
    if hardware_log:
        label='SPRITES' if sprites else 'LAYERS'
        expected=re.findall(rf'{label} POSE {pose} hash=([0-9a-fA-F]+)',hardware_log.read_text())
        if not expected or any(int(v,16)!=checksum for v in expected):raise SystemExit(f'Hardware image differs from {checksum:08x}')
    colors=[]
    for (rgb,) in struct.iter_unpack('<I',raw[-1024:]):
        colors.extend((((rgb>>shift)&63)*255+31)//63 for shift in (12,6,0))
    picture=Image.frombytes('P',(W,H),bytes(indices));picture.putpalette(colors)
    output.parent.mkdir(parents=True,exist_ok=True);picture.convert('RGB').save(output)
    print(f'{output}: pose {pose}, hash {checksum:08x}'+(', matches hardware log' if hardware_log else ', software reference'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose',type=int,choices=(0,1,2),default=0)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--hardware-log',type=Path)
    args=parser.parse_args()
    render(args.pose,args.output or ROOT/f'TESTS/images/gpu_g3_pose{args.pose}_expected.png',args.hardware_log)
