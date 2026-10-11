#ifndef CONSOLE_GPU_RASTER_SCENE_H
#define CONSOLE_GPU_RASTER_SCENE_H
#include "gpu_3d_scene.h"
#include <limits.h>
typedef void (*gpu_emit_fn)(const gpu_command *);
enum { GPU_RASTER_PHASE_MASK=511 };

static uint16_t raster_asset(unsigned x,unsigned y)
{
    if(x<2 || x>=62 || y<2 || y>=62)return 0xffff;
    if((x/8+y/8)%5==0)return 0;
    return (uint16_t)((((x*31)/63)<<11)|(((y*63)/63)<<5)|(((x^y)&63)/2));
}
// Derive a screen-space plane at pixel centres; signed division truncates
// toward zero once during setup. Pixel evaluation itself uses floor Q16.16.
static int raster_plane(gpu_raster_plane *p,const int x[3],const int y[3],const int64_t f[3])
{
    int64_t a=(int64_t)(x[1]-x[0])*(y[2]-y[0])-(int64_t)(y[1]-y[0])*(x[2]-x[0]);
    if(!a)return 0;
    int64_t dx=((f[1]-f[0])*(y[2]-y[0])-(f[2]-f[0])*(y[1]-y[0]))/a;
    int64_t dy=((int64_t)(x[1]-x[0])*(f[2]-f[0])-(int64_t)(x[2]-x[0])*(f[1]-f[0]))/a;
    int64_t origin=f[0]-dx*x[0]-dy*y[0]+(dx+dy)/2;
    if(dx<INT32_MIN || dx>INT32_MAX || dy<INT32_MIN || dy>INT32_MAX ||
       origin<-(1LL<<47) || origin>=(1LL<<47))return 0;
    p->origin=origin;p->dx=(int32_t)dx;p->dy=(int32_t)dy;return 1;
}
static int raster_triangle_emit_mode(gpu_emit_fn emit,const int x[3],const int y[3],const int u[3],const int v[3],const int z[3],const int q[3])
{
    gpu_raster_plane planes[4];int64_t f[3];
    for(unsigned n=0;n<(q?4U:3U);++n) {
        const int *values=n==0?u:n==1?v:z;
        for(unsigned i=0;i<3;++i)f[i]=n==3 ? q[i]:n<2 && q ? (int64_t)values[i]*q[i]:(int64_t)values[i]*65536;
        if(!raster_plane(&planes[n],x,y,f))return 0;
    }
    for(unsigned n=0;n<(q?4U:3U);++n){gpu_command c=gpu_make_plane(n==3 ? GPU_PLANE_Q:GPU_PLANE_U+n,&planes[n]);emit(&c);}
    gpu_command c={{GPU_RASTER_TRIANGLE<<24,
        ((uint32_t)(uint16_t)x[0]<<16)|(uint16_t)y[0],
        ((uint32_t)(uint16_t)x[1]<<16)|(uint16_t)y[1],
        ((uint32_t)(uint16_t)x[2]<<16)|(uint16_t)y[2],0,0,0,0}};
    emit(&c);return 1;
}
static int raster_triangle_emit(gpu_emit_fn emit,const int x[3],const int y[3],const int u[3],const int v[3],const int z[3])
{ return raster_triangle_emit_mode(emit,x,y,u,v,z,0); }
static int raster_scene_mode(unsigned page,unsigned angle,unsigned reverse,gpu_emit_fn emit,unsigned perspective)
{
    int valid=1;
    gpu_command c=gpu_make_raster_state(page,8,0,256,0);emit(&c);
    c=gpu_make_raster_clear(3,0x1083,65535);emit(&c);
    static const int8_t corners[8][3]={{-1,-1,-1},{1,-1,-1},{1,1,-1},{-1,1,-1},
        {-1,-1,1},{1,-1,1},{1,1,1},{-1,1,1}};
    static const uint8_t faces[6][4]={{0,3,2,1},{4,5,6,7},{1,2,6,5},{0,4,7,3},{3,7,6,2},{0,1,5,4}};
    // Separate cubes make the faces readable; submit faces without sorting.
    for(unsigned object=0;object<2;++object) {
        gpu_vec3 vertices[8];
        for(unsigned i=0;i<8;++i) {
            gpu_vec3 p={corners[i][0]*58,corners[i][1]*58,corners[i][2]*58};
            vertices[i]=scene3d_transform(p,angle+object*53,410);
        }
        c=gpu_make_raster_state(page,8,GPU_RASTER_TEXTURE|GPU_Z_TEST|GPU_Z_WRITE|(perspective?GPU_PERSPECTIVE:0),256,0);emit(&c);
        for(unsigned order=0;order<6;++order) {
            unsigned face=reverse?5-order:order;
            gpu_vec3 p0=vertices[faces[face][0]],p1=vertices[faces[face][1]],p2=vertices[faces[face][2]];
            gpu_vec3 a={p1.x-p0.x,p1.y-p0.y,p1.z-p0.z},b={p2.x-p0.x,p2.y-p0.y,p2.z-p0.z};
            int facing=(a.y*b.z-a.z*b.y)*p0.x+(a.z*b.x-a.x*b.z)*p0.y+(a.x*b.y-a.y*b.x)*p0.z;
            if(facing>=0)continue;
            for(unsigned t=0;t<2;++t) {
                unsigned idx[3]={0,t+1,t+2};int x[3],y[3],u[3],v[3],z[3],q[3];
                for(unsigned k=0;k<3;++k) {
                    gpu_vec3 p=vertices[faces[face][idx[k]]];
                    x[k]=(object?565:235)+p.x*440/p.z;y[k]=162-p.y*440/p.z;
                    u[k]=(idx[k]==1 || idx[k]==2)?63:0;v[k]=idx[k]>=2?63:0;
                    q[k]=(1<<30)/p.z;
                    z[k]=60000-8000000/p.z; // affine normalized reciprocal depth
                }
                // Pixel rounding can invert a nearly edge-on triangle.
                // Apply the same front-face rule after viewport projection.
                if((x[1]-x[0])*(y[2]-y[0])-(y[1]-y[0])*(x[2]-x[0])<=0)continue;
                valid &= raster_triangle_emit_mode(emit,x,y,u,v,z,perspective?q:0);
            }
        }
    }
    // Fixed alpha panels below the cubes, Z read-only and transparent holes.
    for(unsigned i=0;i<3;++i) {
        int x[3]={310+(int)i*52,420+(int)i*32,330+(int)i*52};
        int y[3]={286,318,369};int u[3]={0,63,0},v[3]={0,0,63},z[3]={20000,20000,20000};
        c=gpu_make_raster_state(page,8,GPU_RASTER_TEXTURE|GPU_Z_TEST|GPU_KEY_ZERO,64+i*64,0);emit(&c);
        valid &= raster_triangle_emit(emit,x,y,u,v,z);
    }
    // A row of solid alpha swatches, including 0 and 256.
    for(unsigned i=0;i<9;++i) {
        c=gpu_make_raster_state(page,8,0,i*32,0xfd20);emit(&c);
        int x[3]={180+(int)i*50,224+(int)i*50,180+(int)i*50};
        int y[3]={392,392,436},u[3]={0,0,0},v[3]={0,0,0},z[3]={0,0,0};
        valid &= raster_triangle_emit(emit,x,y,u,v,z);
        x[0]+=44;y[0]+=44;valid &= raster_triangle_emit(emit,x,y,u,v,z);
    }
    return valid;
}
static int raster_scene(unsigned page,unsigned angle,unsigned reverse,gpu_emit_fn emit)
{ return raster_scene_mode(page,angle,reverse,emit,0); }
#endif
