#!/usr/bin/env python3
"""Check closed cube silhouettes independently of the submitted triangles.

Every pixel safely inside the convex hull of the eight projected corners
must receive depth. A one-pixel boundary margin allows viewport rounding.
Also reject dropped planes and discontinuities across the animation loop.
"""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--perspective',action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    source = args.out / 'geometry.c'
    source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "gpu_raster_reference.h"
#ifndef PERSPECTIVE
#define PERSPECTIVE 0
#endif
#define raster_scene(p,a,r,e) raster_scene_mode(p,a,r,e,PERSPECTIVE)
static uint16_t color[800*480],depth[800*480];
static uint64_t command_hash;
static unsigned covered;
static void emit(const gpu_command *c) {
    for(unsigned i=0;i<8;++i)command_hash=(command_hash^c->words[i])*1099511628211ULL;
    raster_reference(c);
}
typedef struct { int x,y; } point;
static int cross(point a,point b,point c) {
    return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
}
static void silhouette(unsigned angle,unsigned object) {
    point p[8],h[16];int count=0;
    for(unsigned i=0;i<8;++i) {
        gpu_vec3 v={(i&1)?58:-58,(i&2)?58:-58,(i&4)?58:-58};
        v=scene3d_transform(v,angle+object*53,410);
        p[i]=(point){(object?565:235)+v.x*440/v.z,162-v.y*440/v.z};
    }
    for(int i=1;i<8;++i) {
        point v=p[i];int j=i;
        while(j && (p[j-1].x>v.x || (p[j-1].x==v.x && p[j-1].y>v.y))){p[j]=p[j-1];--j;}
        p[j]=v;
    }
    for(int i=0;i<8;++i){while(count>=2 && cross(h[count-2],h[count-1],p[i])<=0)--count;h[count++]=p[i];}
    int first=count;
    for(int i=6;i>=0;--i){while(count>first && cross(h[count-2],h[count-1],p[i])<=0)--count;h[count++]=p[i];}
    --count;
    int top=480,bottom=0;
    for(int i=0;i<count;++i){if(h[i].y<top)top=h[i].y;if(h[i].y>bottom)bottom=h[i].y;}
    for(int y=top;y<=bottom;++y)for(int x=p[0].x;x<=p[7].x;++x) {
        int inside=1;
        for(int i=0;i<count;++i) {
            point a=h[i],b=h[(i+1)%count];int dx=b.x-a.x,dy=b.y-a.y;
            if(dx*(2*y+1-2*a.y)-dy*(2*x+1-2*a.x)<2*(abs(dx)+abs(dy)))inside=0;
        }
        if(inside) {
            if(depth[y*800+x]==65535){fprintf(stderr,"Missing face angle=%u cube=%u xy=%d,%d\n",angle,object,x,y);exit(1);}
            ++covered;
        }
    }
}
int main(void) {
    raster_reference_color=color;raster_reference_depth=depth;
    uint64_t first_hash=0;
    for(unsigned angle=0;angle<=512;++angle) {
        command_hash=1469598103934665603ULL;
        assert(raster_scene(0,angle,0,emit));
        if(!angle)first_hash=command_hash;
        if(angle==512)assert(command_hash==first_hash);
        silhouette(angle,0);silhouette(angle,1);
        unsigned next=(angle+1)&GPU_RASTER_PHASE_MASK;
        for(unsigned i=0;i<8;++i) {
            gpu_vec3 v={(i&1)?58:-58,(i&2)?58:-58,(i&4)?58:-58};
            gpu_vec3 a=scene3d_transform(v,angle,410),b=scene3d_transform(v,next,410);
            assert(abs(a.x-b.x)<=4 && abs(a.y-b.y)<=4 && abs(a.z-b.z)<=4);
        }
    }
    printf("PASS: 512 animation phases, zero dropped planes, %u interior silhouette pixels, periodic commands, continuous rotation\n",covered);
}
''')
    exe = args.out / 'geometry'
    subprocess.run(['cc', '-O2', '-std=c11', '-fsanitize=undefined',
                    '-fno-sanitize-recover=all', f'-DPERSPECTIVE={int(args.perspective)}', '-I', str(ROOT/'fw_console'),
                    str(source), str(ROOT/'fw_console/gpu_raster_commands.c'), '-o', str(exe)], check=True)
    result = subprocess.run([str(exe)], capture_output=True, text=True)
    (args.out/'result.txt').write_text(result.stdout + result.stderr)
    print(result.stdout + result.stderr, end='')
    result.check_returncode()


if __name__ == '__main__':
    main()
