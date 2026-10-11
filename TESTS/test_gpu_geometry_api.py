#!/usr/bin/env python3
"""Public geometry API: boundaries, atomic rejection, no NaN conversion under UBSan."""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
C=r'''
#include <assert.h>
#include <math.h>
#include <limits.h>
#include "gpu_geometry.h"
static unsigned count;static gpu_command last;
static void emit(const gpu_command *c){++count;last=*c;}
int main(void){
 gpu_v1_context c;gpu_v1_init(&c,emit);
 gpu_target t={0x800000,0x900000,400,240,800,800};assert(gpu_v1_target(&c,&t));
 gpu_geom_camera cam={16384,80*65536,200*65536,200*65536,200,120};
 assert(gpu_geom_set_camera(&c,&cam));assert(last.words[0]==32U<<24);
 unsigned before=count;cam.near_z=0;assert(!gpu_geom_set_camera(&c,&cam));assert(count==before);cam.near_z=16384;
 cam.center_x=401;assert(!gpu_geom_set_camera(&c,&cam));cam.center_x=200;
 cam.focal_x=65536;assert(!gpu_geom_set_camera(&c,&cam));cam.focal_x=200*65536;
 gpu_geom_mesh m={0x6000000,0x6002000,8,12};gpu_geom_transform x={{65536,0,0,0,0,65536,0,0,0,0,65536,0}};
 gpu_geom_light l={0,0,-32767,64,192};
 assert(gpu_geom_instance(&c,&m,&x,&l,1));assert(count==before+5);before=count;
 m.vertex_count=257;assert(!gpu_geom_instance(&c,&m,&x,&l,1));assert(count==before);m.vertex_count=8;
 m.faces=0x1fffffe0;assert(!gpu_geom_instance(&c,&m,&x,&l,1));assert(count==before);m.faces=0x6002000;
 l.diffuse=257;assert(!gpu_geom_instance(&c,&m,&x,&l,1));assert(count==before);l.diffuse=192;
 c.flags=64;assert(!gpu_geom_instance(&c,&m,&x,&l,1));assert(count==before);c.flags=0;
 int32_t fixed=123;assert(!gpu_geom_fixed(NAN,&fixed)&&fixed==123);assert(!gpu_geom_fixed(INFINITY,&fixed));
 assert(!gpu_geom_fixed(32768,&fixed));assert(gpu_geom_fixed(-32768,&fixed)&&fixed==INT32_MIN);
 assert(gpu_geom_fixed(1.25,&fixed)&&fixed==81920);
 assert(gpu_geom_billboard_transform(&x,0,0,65536,65536,2*65536,0,32767));
 assert(x.values[0]==65534&&x.values[5]==131068&&x.values[11]==65536);
 assert(!gpu_geom_billboard_transform(&x,0,0,1,0,1,0,32767));
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='geom_api_') as temp:
 p=Path(temp);(p/'test.c').write_text(C)
 subprocess.run(['cc','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=undefined,float-cast-overflow','-fno-sanitize-recover=all','-I'+str(ROOT/'fw_console'),str(p/'test.c'),str(ROOT/'fw_console/gpu_geometry.c'),str(ROOT/'fw_console/gpu_v1.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: geometry API bounds, atomic rejection, fixed-point and billboard transforms')
