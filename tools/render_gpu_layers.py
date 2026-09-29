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
from gpu_compose import W,H,compose,frame_hash,palette_rgb

SLOT=1048576


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
    textures=16*SLOT+512
    def read(address,count):
        if 0x00800000<=address and address+count<=0x00800000+16*SLOT:
            return raw[address-0x00800000:address-0x00800000+count]
        if sprites and 0x02000000<=address and address+count<=0x02000000+196608:
            return raw[textures+address-0x02000000:textures+address-0x02000000+count]
        raise SystemExit('Source outside surface memory')
    layer_table=list(struct.iter_unpack('<8I',raw[16*SLOT:16*SLOT+512]))
    sprite_table=list(struct.iter_unpack('<4I',raw[textures+196608:textures+196608+1024])) if sprites else None
    indices=compose(layer_table,sprite_table,read)
    checksum=frame_hash(indices)
    if hardware_log:
        label='SPRITES' if sprites else 'LAYERS'
        expected=re.findall(rf'{label} POSE {pose} hash=([0-9a-fA-F]+)',hardware_log.read_text())
        if not expected or any(int(v,16)!=checksum for v in expected):raise SystemExit(f'Hardware image differs from {checksum:08x}')
    picture=Image.frombytes('P',(W,H),bytes(indices));picture.putpalette(palette_rgb(raw[-1024:]))
    output.parent.mkdir(parents=True,exist_ok=True);picture.convert('RGB').save(output)
    print(f'{output}: pose {pose}, hash {checksum:08x}'+(', matches hardware log' if hardware_log else ', software reference'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose',type=int,choices=(0,1,2),default=0)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--hardware-log',type=Path)
    args=parser.parse_args()
    render(args.pose,args.output or ROOT/f'TESTS/images/gpu_g3_pose{args.pose}_expected.png',args.hardware_log)
