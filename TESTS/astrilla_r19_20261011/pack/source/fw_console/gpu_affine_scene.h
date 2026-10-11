#ifndef CONSOLE_GPU_AFFINE_SCENE_H
#define CONSOLE_GPU_AFFINE_SCENE_H
#include "gpu.h"
#include "gpu_palette.h"
#include "gpu_3d_scene.h" // Reuse the existing integer sine table.

static const unsigned affine_poses[4]={0,32,64,117};
// Deliberately asymmetric asset: transparent corners/hole, colored quadrants,
// white rim, upward arrow. It makes rotation, handedness and keying visible.
static unsigned affine_asset(unsigned x,unsigned y)
{
    int dx=(int)x-64,dy=(int)y-64,r=dx*dx+dy*dy;
    if(r>60*60 || r<12*12)return 0;
    if(r>57*57)return DEMO_WHITE;
    if((y>18 && y<47 && x>59 && x<69) ||
       (y>=12 && y<30 && (dx<0?-dx:dx)<(int)y-11))return DEMO_WHITE;
    if(x<64)return y<64 ? 192+(x&63):128+(y&63);
    return y<64 ? 128+(x&63):192+(y&63);
}
static void affine_object(unsigned page,int x,int y,int w,int h,
    int ux,int vx,int uy,int vy,void (*emit)(const gpu_command *))
{
    gpu_affine_transform t={64*65536-(w/2)*ux-(h/2)*uy,
        64*65536-(w/2)*vx-(h/2)*vy,ux,vx,uy,vy};
    gpu_command c=gpu_make_affine_setup(&t);emit(&c);
    c=gpu_make_affine(page,15,x,y,w,h,17,19,128,128);emit(&c);
}
static void affine_scene(unsigned page,unsigned angle,void (*emit)(const gpu_command *))
{
    gpu_command c=gpu_make_command(GPU_FILL,page,0,0,0,800,480,0,0,DEMO_BACKGROUND,0);emit(&c);
    int s=scene3d_sin(angle)*4,co=scene3d_sin(angle+64)*4;
    affine_object(page,25,82,220,220,co,-s,s,co,emit);
    affine_object(page,284,90,236,196,32768,0,0,98304,emit);
    affine_object(page,550,90,220,220,65536,0,-30000,65536,emit);
    affine_object(page,30,300,170,150,-65536,0,0,65536,emit);
    affine_object(page,292,297,208,151,co*3/2,-s*3/2,s/2,co/2,emit);
    affine_object(page,572,309,176,128,65536,17000,24000,65536,emit);
}
#endif
