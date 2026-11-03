#!/usr/bin/env python3
"""Render actual firmware commands with an independent pixel reference; UBSan model tests."""
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


def render(pose, output, hardware_log=None, cached=False):
    fw=ROOT/'fw_console'
    driver=(fw/'gpu.c').read_text()
    source='''#include <assert.h>
#include <stdlib.h>
#include "racer_scene.h"
'''+brace_block(driver,'gpu_command gpu_make_command(')+'\n'+brace_block(driver,'gpu_command gpu_make_zoom(')+'\n'+brace_block((ROOT/'games/racer/src/racer_demo.h').read_text(),'static void racer_pose(')+'''
int main(int argc,char **argv){
    racer_state s;
    race_original=argc<3 || strcmp(argv[2],"cached")!=0;
    racer_reset(&s);for(int i=0;i<300;++i)racer_step(&s,R_ACCEL);
    assert(s.phase==0 && s.speed==0 && s.distance==0);
    racer_step(&s,R_START);assert(s.phase==1);
    for(int i=0;i<250;++i)racer_step(&s,R_ACCEL);
    assert(s.speed==500 && s.distance>0);
    int before=s.speed;for(int i=0;i<20;++i)racer_step(&s,R_BRAKE);assert(s.speed<before);
    s.x=120;before=s.speed;for(int i=0;i<20;++i)racer_step(&s,R_ACCEL);assert(s.speed<before);
    s.x=-45;s.speed=500;s.traffic[0]=106;s.crash_ticks=0;
    racer_step(&s,R_ACCEL);assert(s.hits==1 && s.speed<130 && s.crash_ticks>0);
    for(int i=0;i<10;++i){racer_step(&s,R_ACCEL);}assert(s.hits==1);
    racer_step(&s,R_START);assert(s.distance==0 && s.hits==0 && s.phase==1);
    racer_step(&s,0);s.distance=RACE_FINISH-1;s.speed=500;
    racer_step(&s,R_ACCEL);assert(s.phase==2 && s.speed==0);
    // Complete a 6 km run while following the right lane through all bends.
    racer_reset(&s);racer_step(&s,R_START);
    for(int tick=0;tick<20000 && s.phase==1;++tick){
        unsigned keys=R_ACCEL;if(s.x<43)keys|=R_RIGHT;if(s.x>47)keys|=R_LEFT;
        racer_step(&s,keys);
    }
    assert(s.phase==2 && s.distance>=RACE_FINISH && s.hits==0);
    // All road positions, steering extremes, traffic and clipping under UBSan.
    for(int d=0;d<60000;d+=83){
        racer_pose(&s,1);s.distance=d;s.x=(d%321)-160;
        racer_build(&s,6);assert(!race_overflow && race_count<RACE_COMMANDS);
    }
    racer_background(9);fwrite(&race_count,4,1,stdout);fwrite(race_commands,32,race_count,stdout);
    racer_pose(&s,(unsigned)atoi(argv[1]));racer_build(&s,6);
    fwrite(&race_count,4,1,stdout);fwrite(race_commands,32,race_count,stdout);
    static uint8_t atlas[800*480];racer_make_atlas(atlas);fwrite(atlas,1,sizeof(atlas),stdout);
    for(unsigned i=0;i<256;++i){uint32_t color=racer_palette(i);fwrite(&color,4,1,stdout);}
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='racer_render_') as directory:
        work=Path(directory);(work/'scene.c').write_text(source)
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-parameter',
                        '-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(fw),'-I',str(ROOT/'games/racer/src'),str(work/'scene.c'),'-o',str(work/'scene')],check=True)
        raw=subprocess.run([str(work/'scene'),str(pose),'cached' if cached else 'original'],check=True,capture_output=True).stdout
    bg_count,=struct.unpack_from('<I',raw)
    scene_offset=4+bg_count*32
    count,=struct.unpack_from('<I',raw,scene_offset)
    atlas=raw[scene_offset+4+count*32:-1024]
    assert len(atlas)==800*480
    pixels=bytearray([0xa5])*(800*480)
    font=[int(v,16) for v in (ROOT/'tang/rtl/video/font8x16.hex').read_text().split()]
    def plot(x,y,c):
        if 0<=x<800 and 0<=y<480:pixels[y*800+x]=c
    backdrop=bytearray(800*480)
    for draw_count,offset in ((bg_count,4),(count,scene_offset+4)):
        for i in range(draw_count):
            words=struct.unpack_from('<8I',raw,offset+i*32)
            op,c,bg=words[0]>>24,(words[0]>>8)&255,words[0]&255
            signed=lambda v:v if v<32768 else v-65536
            x,y,a,b,sx,sy=[signed((w>>s)&65535) for w in words[1:4] for s in (16,0)]
            if op in (1,3):
                step=65536//(b-1) if b>1 else 65536
                for yy in range(max(0,y),min(480,y+b)):
                    color=c if op==1 else c+(bg-c)*((yy-y)*step)//65536
                    for xx in range(max(0,x),min(800,x+a)):plot(xx,yy,color)
            elif op==8:
                for yy in range(max(0,y),min(480,y+b)):
                    for xx in range(max(0,x),min(800,x+a)):
                        plot(xx,yy,backdrop[(sy+yy-y)*800+sx+xx-x])
            elif op==10:
                for xx,yy in triangle_pixels(x,y,a,b,sx,sy):plot(xx,yy,c)
            elif op==11:
                for yy in range(max(0,y),min(480,y+b)):
                    v=((yy-y)*words[6])>>16
                    for xx in range(max(0,x),min(800,x+a)):
                        u=((xx-x)*words[5])>>16
                        color=atlas[(sy+v)*800+sx+u]
                        if color:plot(xx,yy,color)
            elif op==9:
                text=struct.pack('<4I',*words[4:])[:a]
                for n,ch in enumerate(text):
                    for row in range(16):
                        for col in range(8):
                            if font[ch*16+row]&(128>>col):
                                for dy in range(b):
                                    for dx in range(b):plot(x+(n*8+col)*b+dx,y+row*b+dy,c)
            else:raise AssertionError(op)
        if offset==4:
            backdrop=pixels[:];pixels=bytearray([0xa5])*(800*480)
    assert 0xa5 not in pixels, 'Scene must cover every framebuffer pixel'
    rotate=lambda v,n:((v<<(n&31))|(v>>((32-n)&31)))&0xffffffff
    checksum=0
    for offset in range(0,len(pixels),32):
        block=0
        for i,word in enumerate(struct.unpack_from('<8I',pixels,offset)):block^=rotate(word,i*4)
        checksum=rotate(checksum,5)^block
    if hardware_log:
        hashes=re.findall(rf'RACE POSE {pose} hash=([0-9a-fA-F]+)',hardware_log.read_text())
        assert hashes and all(int(h,16)==checksum for h in hashes),f'Hardware differs from {checksum:08x}'
    palette=[]
    for (rgb,) in struct.iter_unpack('<I',raw[-1024:]):
        palette.extend((((rgb>>shift)&63)*255+31)//63 for shift in (12,6,0))
    picture=Image.frombytes('P',(800,480),bytes(pixels));picture.putpalette(palette)
    output.parent.mkdir(parents=True,exist_ok=True);picture.convert('RGB').save(output)
    print(f'PASS model/UBSan + scene {pose}: hash={checksum:08x}, commands={count}, {output}')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pose',type=int,choices=range(4),default=1)
    p.add_argument('--output',type=Path)
    p.add_argument('--cached',action='store_true',help='Render the earlier cached panorama variant')
    p.add_argument('--hardware-log',type=Path)
    a=p.parse_args();render(a.pose,a.output or ROOT/f'TESTS/images/racer_{"cached" if a.cached else "fast"}_pose{a.pose}.png',a.hardware_log,a.cached)
