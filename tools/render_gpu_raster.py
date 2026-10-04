#!/usr/bin/env python3
"""Render the portable RGB565/Z reference and export actual firmware commands."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--angle',type=int,default=0)
    p.add_argument('--reverse',type=int,choices=[0,1],default=0)
    p.add_argument('--perspective',action='store_true')
    p.add_argument('--overlay',action='store_true',help='perspective scene with indexed HUD, sprite and tile strip')
    p.add_argument('--sweep',action='store_true')
    p.add_argument('--animation',action='store_true',help='export the full 512-phase loop as lossless animated WebP')
    args=p.parse_args();args.perspective |= args.overlay;out=args.out;out.mkdir(parents=True,exist_ok=True)
    source=out/'render.c'
    source.write_text('''#include <stdio.h>
#include <assert.h>
#include <stdlib.h>
#include "gpu_raster_reference.h"
#include "gpu_rgb_overlay_scene.h"
#include "build/gpu_font.h"
#ifndef RASTER_OVERLAY
#define RASTER_OVERLAY 0
#endif
#ifndef RASTER_PERSPECTIVE
#define RASTER_PERSPECTIVE 0
#endif
#define raster_scene(p,a,r,e) raster_scene_mode(p,a,r,e,RASTER_PERSPECTIVE)
static uint16_t color[800*480],depth[800*480];
static FILE *commands;
static void emit(const gpu_command *c) {
    raster_reference(c);
    if(commands)fwrite(c->words,4,8,commands);
}
int main(int argc,char **argv) {
    raster_reference_color=color;raster_reference_depth=depth;
    if(argc==2) {
        for(unsigned a=0;a<512;++a)assert(raster_scene(0,a,0,emit));
        return 0;
    }
    commands=fopen(argv[3],"wb");if(!commands)return 2;
    assert(raster_scene(0,atoi(argv[1]),atoi(argv[2]),emit));fclose(commands);
    FILE *f=fopen(argv[4],"wb");if(!f)return 2;fwrite(color,2,800*480,f);fclose(f);
    f=fopen(argv[5],"wb");if(!f)return 2;fwrite(depth,2,800*480,f);fclose(f);
    f=fopen(argv[6],"wb");if(!f)return 2;
    for(unsigned y=0;y<480;++y)for(unsigned x=0;x<800;++x) {
        unsigned c=color[y*800+x];int ix=RASTER_OVERLAY ? overlay_sample(x,y,atoi(argv[1]),gpu_font):-1;
        uint32_t rgb=ix>=0 ? overlay_palette((unsigned)ix):
            (((c>>11)*2+(c>>15))<<12)|(((c>>5)&63)<<6)|((c&31)*2+((c>>4)&1));
        fwrite(&rgb,4,1,f);
    }
    fclose(f);return 0;
}
''')
    exe=out/'render'
    subprocess.run(['cc','-O2','-std=c11','-fsanitize=undefined','-fno-sanitize-recover=all',
        f'-DRASTER_PERSPECTIVE={int(args.perspective)}',f'-DRASTER_OVERLAY={int(args.overlay)}','-I',str(ROOT/'fw_console'),str(source),'-o',str(exe)],check=True)
    if args.sweep:subprocess.run([str(exe),'sweep'],check=True)
    subprocess.run([str(exe),str(args.angle),str(args.reverse),str(out/'commands.bin'),str(out/'color.bin'),str(out/'depth.bin'),str(out/'lcd.bin')],check=True)
    pixels=(out/'color.bin').read_bytes();rgb=bytearray()
    for i in range(0,len(pixels),2):
        c=int.from_bytes(pixels[i:i+2],'little');r=(c>>11)&31;g=(c>>5)&63;b=c&31
        rgb.extend(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
    lcd=(out/'lcd.bin').read_bytes()
    if args.overlay:
        rgb=bytearray()
        for i in range(0,len(lcd),4):
            c=int.from_bytes(lcd[i:i+4],'little')
            for shift in (12,6,0):
                component=(c>>shift)&63;rgb.append((component<<2)|(component>>4))
    Image.frombytes('RGB',(800,480),bytes(rgb)).save(out/'expected.png')
    if args.animation:
        frames=[]
        with tempfile.TemporaryDirectory(prefix='raster_frames_') as temp:
            work=Path(temp)
            for angle in range(0,512,4):
                subprocess.run([str(exe),str(angle),'0',str(work/'commands.bin'),
                    str(work/'color.bin'),str(work/'depth.bin'),str(work/'lcd.bin')],check=True)
                if args.overlay:
                    data=(work/'lcd.bin').read_bytes();frame_rgb=bytearray()
                    for at in range(0,len(data),4):
                        color=int.from_bytes(data[at:at+4],'little')
                        for shift in (12,6,0):
                            component=(color>>shift)&63;frame_rgb.append((component<<2)|(component>>4))
                    frames.append(Image.frombytes('RGB',(800,480),bytes(frame_rgb)))
                else:
                    frames.append(Image.frombytes('RGB',(800,480),(work/'color.bin').read_bytes(),'raw','BGR;16'))
        frames[0].save(out/'expected_animation.webp',save_all=True,
            append_images=frames[1:],duration=73,loop=0,lossless=True)
    result={'perspective':args.perspective,'overlay':args.overlay,
        'lcd_sum':f'{sum(int.from_bytes(lcd[i:i+4],"little") for i in range(0,len(lcd),4))&0xffffffff:08x}','angle':args.angle,'reverse':args.reverse,'commands':len((out/'commands.bin').read_bytes())//32,
        'color_sum':f'{sum(int.from_bytes(pixels[i:i+4],"little") for i in range(0,len(pixels),4))&0xffffffff:08x}',
        'sweep_512_pass':args.sweep,'animation_frames':128 if args.animation else 0}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
