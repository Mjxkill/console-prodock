#ifndef CONSOLE_GPU_3D_SCENE_H
#define CONSOLE_GPU_3D_SCENE_H
// Portable scene preparation: CPU transforms, culling, near clipping and
// painter ordering; only lines/flat triangles are submitted to the GPU.
#include "gpu.h"
#include "gpu_palette.h"
typedef struct { int x,y,z; } gpu_vec3;
typedef struct { gpu_vec3 v[5];int n,depth;unsigned color,wire,cx; } gpu_face3;
static gpu_command scene3d_commands[96];
static unsigned scene3d_count,scene3d_triangles,scene3d_clipped;
static const int16_t scene3d_sine[65]={
    0,402,804,1205,1606,2006,2404,2801,3196,3590,3981,4370,4756,
    5139,5520,5897,6270,6639,7005,7366,7723,8076,8423,8765,9102,9434,
    9760,10080,10394,10702,11003,11297,11585,11866,12140,12406,12665,12916,13160,
    13395,13623,13842,14053,14256,14449,14635,14811,14978,15137,15286,15426,15557,
    15679,15791,15893,15986,16069,16143,16207,16261,16305,16340,16364,16379,16384,
};
static int scene3d_sin(unsigned phase)
{
    phase&=255;unsigned q=phase&63;
    int value=scene3d_sine[(phase&64)?64-q:q];
    return phase&128 ? -value:value;
}
static gpu_vec3 scene3d_transform(gpu_vec3 v,unsigned angle,int distance)
{
    int s=scene3d_sin(angle),c=scene3d_sin(angle+64);
    int x=(v.x*c+v.z*s)/16384,z=(v.z*c-v.x*s)/16384;
    s=scene3d_sin(angle/2+19);c=scene3d_sin(angle/2+83);
    gpu_vec3 r={x,(v.y*c-z*s)/16384,distance+(v.y*s+z*c)/16384};return r;
}
static int scene3d_clip(const gpu_vec3 *in,int n,gpu_vec3 *out,int near_z)
{
    int count=0;
    for(int i=0;i<n;++i) {
        gpu_vec3 a=in[i],b=in[(i+1)%n];
        int ai=a.z>=near_z,bi=b.z>=near_z;
        if(ai) out[count++]=a;
        if(ai!=bi) {
            gpu_vec3 p={a.x+(b.x-a.x)*(near_z-a.z)/(b.z-a.z),
                a.y+(b.y-a.y)*(near_z-a.z)/(b.z-a.z),near_z};
            out[count++]=p;
        }
    }
    return count;
}
static void scene3d_add(unsigned op,unsigned page,int x,int y,int a,int b,int sx,int sy,unsigned color)
{
    scene3d_commands[scene3d_count++]=gpu_make_command(op,page,0,x,y,a,b,sx,sy,color,0);
    if(op==GPU_TRIANGLE) ++scene3d_triangles;
}
static void scene3d_build(unsigned page,unsigned angle,int close_up)
{
    static const int8_t vertices[8][3]={{-1,-1,-1},{1,-1,-1},{1,1,-1},{-1,1,-1},
        {-1,-1,1},{1,-1,1},{1,1,1},{-1,1,1}};
    static const uint8_t faces[6][4]={{0,3,2,1},{4,5,6,7},{1,2,6,5},{0,4,7,3},{3,7,6,2},{0,1,5,4}};
    gpu_face3 list[12];int count=0;
    scene3d_count=scene3d_triangles=scene3d_clipped=0;
    scene3d_add(GPU_FILL,page,0,0,800,480,0,0,DEMO_BACKGROUND);
    for(unsigned object=0;object<2;++object) {
        gpu_vec3 v[8];
        int near_z=close_up && object ? 200:64;
        for(unsigned i=0;i<8;++i) {
            gpu_vec3 p={vertices[i][0]*72,vertices[i][1]*72,vertices[i][2]*72};
            v[i]=scene3d_transform(p,angle+(object?21:0),close_up && object ? 235:400);
        }
        for(unsigned f=0;f<6;++f) {
            gpu_vec3 p[4];for(unsigned i=0;i<4;++i)p[i]=v[faces[f][i]];
            gpu_vec3 a={p[1].x-p[0].x,p[1].y-p[0].y,p[1].z-p[0].z};
            gpu_vec3 b={p[2].x-p[0].x,p[2].y-p[0].y,p[2].z-p[0].z};
            int facing=(a.y*b.z-a.z*b.y)*p[0].x+(a.z*b.x-a.x*b.z)*p[0].y+(a.x*b.y-a.y*b.x)*p[0].z;
            // Wireframe retains rear edges; solid faces are back-face culled.
            if(object && facing>=0)continue;
            gpu_face3 *face=&list[count];
            face->n=scene3d_clip(p,4,face->v,near_z);
            for(unsigned i=0;i<4;++i) if(p[i].z<near_z) {++scene3d_clipped;break;}
            if(face->n<3)continue;
            face->depth=0;for(int i=0;i<face->n;++i)face->depth+=face->v[i].z;
            face->depth/=face->n;face->wire=!object;face->cx=object?572:218;
            face->color=object ? 192+12+f*9 : DEMO_COOL_FIRST+20+f*8;
            ++count;
        }
    }
    for(int i=1;i<count;++i) {
        gpu_face3 face=list[i];int j=i;
        while(j && list[j-1].depth<face.depth){list[j]=list[j-1];--j;}list[j]=face;
    }
    for(int f=0;f<count;++f) {
        gpu_face3 *face=&list[f];int x[5],y[5];
        for(int i=0;i<face->n;++i) {
            x[i]=(int)face->cx+face->v[i].x*400/face->v[i].z;
            y[i]=260-face->v[i].y*400/face->v[i].z;
        }
        if(face->wire)for(int i=0;i<face->n;++i) {
            int j=(i+1)%face->n;scene3d_add(GPU_LINE,page,x[i],y[i],x[j],y[j],0,0,face->color);
        }
        else for(int i=1;i+1<face->n;++i)
            scene3d_add(GPU_TRIANGLE,page,x[0],y[0],x[i],y[i],x[i+1],y[i+1],face->color);
    }
}
#endif
