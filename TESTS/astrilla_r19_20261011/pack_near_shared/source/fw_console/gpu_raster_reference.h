#ifndef CONSOLE_GPU_RASTER_REFERENCE_H
#define CONSOLE_GPU_RASTER_REFERENCE_H
#include "gpu_raster_scene.h"
// Verification only: half-plane coverage and independent per-pixel products.
// The hardware walks spans and accumulators. These buffers are supplied by
// the caller (DDR on board, host memory in the renderer).
static uint16_t *raster_reference_color,*raster_reference_depth;
static uint32_t raster_ref_flags,raster_ref_alpha,raster_ref_solid;
static gpu_raster_plane raster_ref_plane[4];
static void raster_reference(const gpu_command *command)
{
    const uint32_t *w=command->words;unsigned op=w[0]>>24;
    if(op==GPU_RASTER_STATE) {
        raster_ref_flags=w[2];raster_ref_alpha=w[3];raster_ref_solid=w[4];return;
    }
    if((op>=GPU_PLANE_U && op<=GPU_PLANE_Z) || op==GPU_PLANE_Q) {
        int64_t origin=(w[4]&0x10000U) ? (int64_t)(int16_t)w[4]*4294967296LL+w[1]:
            op==GPU_PLANE_Z ? (int64_t)w[1]:(int64_t)(int32_t)w[1];
        raster_ref_plane[op==GPU_PLANE_Q?3:op-GPU_PLANE_U]=(gpu_raster_plane){origin,(int32_t)w[2],(int32_t)w[3]};return;
    }
    if(op==GPU_RASTER_CLEAR) {
        for(unsigned i=0;i<800*480;++i) {
            if(w[1]&1)raster_reference_color[i]=(uint16_t)w[2];
            if(w[1]&2)raster_reference_depth[i]=(uint16_t)w[3];
        }
        return;
    }
    if(op!=GPU_RASTER_TRIANGLE || !raster_ref_alpha)return;
    int x[3],y[3];
    for(unsigned i=0;i<3;++i){x[i]=(int16_t)(w[i+1]>>16);y[i]=(int16_t)w[i+1];}
    int64_t area=(int64_t)(x[1]-x[0])*(y[2]-y[0])-(int64_t)(y[1]-y[0])*(x[2]-x[0]);
    if(!area)return;
    if(area<0){int t=x[1];x[1]=x[2];x[2]=t;t=y[1];y[1]=y[2];y[2]=t;}
    int l=800,r=-1,t=480,b=-1;
    for(unsigned i=0;i<3;++i){if(x[i]<l)l=x[i];if(x[i]>r)r=x[i];if(y[i]<t)t=y[i];if(y[i]>b)b=y[i];}
    if(l<0)l=0;
    if(r>799)r=799;
    if(t<0)t=0;
    if(b>479)b=479;
    for(int yy=t;yy<=b;++yy)for(int xx=l;xx<=r;++xx) {
        unsigned inside=1;
        for(unsigned i=0;i<3;++i) {
            unsigned j=(i+1)%3;int dx=x[j]-x[i],dy=y[j]-y[i];
            int64_t e=(int64_t)dx*(2*yy+1-2*y[i])-(int64_t)dy*(2*xx+1-2*x[i]);
            if(e<0 || (!e && !(dy<0 || (!dy && dx>0))))inside=0;
        }
        if(!inside)continue;
        int64_t f[4],raw[4];
        for(unsigned i=0;i<4;++i) {
            const gpu_raster_plane *p=&raster_ref_plane[i];
            int64_t value=p->origin+(int64_t)xx*p->dx+(int64_t)yy*p->dy;
            raw[i]=value;
            f[i]=value>=0?value/65536:-((-value+65535)/65536);
        }
        if(raster_ref_flags&GPU_PERSPECTIVE) {
            if(raw[3]<=0)continue;
            for(unsigned i=0;i<2;++i)f[i]=raw[i]>=0 ? raw[i]/raw[3]:-((-raw[i]+raw[3]-1)/raw[3]);
        }
        unsigned color=raster_ref_solid;
        if(raster_ref_flags&GPU_RASTER_TEXTURE) {
            // The demo uses clamp: fixed-point rounding on a shared edge
            // must sample its border texel instead of opening a hairline hole.
            unsigned u=f[0]<0 ? 0:f[0]>63 ? 63:(unsigned)f[0];
            unsigned v=f[1]<0 ? 0:f[1]>63 ? 63:(unsigned)f[1];
            color=raster_asset(u,v);
        }
        if((raster_ref_flags&GPU_KEY_ZERO) && !color)continue;
        unsigned at=(unsigned)yy*800+(unsigned)xx;
        if(raster_ref_flags&(GPU_Z_TEST|GPU_Z_WRITE)) {
            if(f[2]<0 || f[2]>65535)continue;
            if((raster_ref_flags&GPU_Z_TEST) && f[2]>=raster_reference_depth[at])continue;
        }
        unsigned bg=raster_reference_color[at],a=raster_ref_alpha;
        unsigned red=(((color>>11)*a+(bg>>11)*(256-a)+128)>>8);
        unsigned green=((((color>>5)&63)*a+((bg>>5)&63)*(256-a)+128)>>8);
        unsigned blue=(((color&31)*a+(bg&31)*(256-a)+128)>>8);
        raster_reference_color[at]=(uint16_t)((red<<11)|(green<<5)|blue);
        if(raster_ref_flags&GPU_Z_WRITE)raster_reference_depth[at]=(uint16_t)f[2];
    }
}
#endif
