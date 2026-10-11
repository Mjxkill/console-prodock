#include "gpu_v1.h"
#include <limits.h>
static uint32_t xy(int x,int y){return ((uint32_t)(uint16_t)x<<16)|(uint16_t)y;}
static int region(uint32_t base,unsigned width,unsigned height,unsigned stride,unsigned maxw,unsigned maxh)
{
    return !(base&31) && width && width<=maxw && height && height<=maxh &&
        !(stride&31) && stride>=width*2 && stride<=65535 && (uint64_t)base+(uint64_t)height*stride<=0x40000000ULL;
}
void gpu_v1_init(gpu_v1_context *c,void (*emit)(const gpu_command *))
{ *c=(gpu_v1_context){0};c->emit=emit; }
int gpu_v1_target(gpu_v1_context *c,const gpu_target *t)
{
    if(!region(t->color,t->width,t->height,t->stride,1024,512) || !region(t->depth,t->width,t->height,t->zstride,1024,512) ||
       (t->color<t->depth+(uint32_t)t->zstride*t->height && t->depth<t->color+(uint32_t)t->stride*t->height))return 0;
    gpu_command cmd={{22U<<24,t->color,t->depth,xy(t->width,t->height),xy(t->stride,t->zstride),0,0,0}};
    c->emit(&cmd);c->target=*t;c->vx=c->vy=0;c->vw=t->width;c->vh=t->height;return 1;
}
int gpu_v1_scissor(gpu_v1_context *c,unsigned x,unsigned y,unsigned w,unsigned h)
{
    if(x>c->target.width || y>c->target.height || w>c->target.width-x || h>c->target.height-y)return 0;
    gpu_command cmd={{23U<<24,xy(x,y),xy(x+w,y+h),0,0,0,0,0}};c->emit(&cmd);return 1;
}
int gpu_v1_viewport(gpu_v1_context *c,int x,int y,unsigned w,unsigned h)
{
    if(x<0 || y<0 || (unsigned)x>c->target.width || (unsigned)y>c->target.height || !w || !h ||
        w>c->target.width-(unsigned)x || h>c->target.height-(unsigned)y)return 0;
    c->vx=x;c->vy=y;c->vw=(int)w;c->vh=(int)h;return 1;
}
int gpu_v1_project(const gpu_v1_context *c,int nx,int ny,int *x,int *y)
{
    if(nx<-65536 || nx>65536 || ny<-65536 || ny>65536)return 0;
    *x=c->vx+(int)((int64_t)(nx+65536)*c->vw/131072);
    *y=c->vy+(int)((int64_t)(65536-ny)*c->vh/131072);return 1;
}
int gpu_v1_texture(gpu_v1_context *c,const gpu_texture_level *t)
{
    if(!region(t->base,t->width,t->height,t->stride,512,512) || t->format>1 || t->u_mode>2 || t->v_mode>2 || t->lod>9 ||
       (t->u_mode==1 && (t->width&(t->width-1))) || (t->v_mode==1 && (t->height&(t->height-1))))return 0;
    gpu_command cmd={{24U<<24,t->base,xy(t->width,t->height),t->stride|((unsigned)t->format<<16),
        t->u_mode|(t->v_mode<<2)|(t->lod<<4),0,0,0}};c->emit(&cmd);return 1;
}
int gpu_v1_material(gpu_v1_context *c,const gpu_material *m)
{
    if(m->flags>255 || ((m->flags&16) && !(m->flags&1)) || m->alpha>256 || m->r>256 || m->g>256 || m->b>256 || m->fog_scale>0x1000000)return 0;
    gpu_command cmd={{25U<<24,m->flags,m->alpha,m->color,m->r|(m->g<<9)|(m->b<<18),
        ((uint32_t)m->fog_near<<16)|m->fog_color,m->fog_scale,0}};
    c->emit(&cmd);c->flags=m->flags;return 1;
}
int gpu_v1_plane(gpu_v1_context *c,unsigned index,const gpu_raster_plane *p)
{
    if(index>6 || p->origin<-(1LL<<47) || p->origin>=(1LL<<47))return 0;
    gpu_command cmd={{(26U<<24)|index,(uint32_t)p->origin,(uint32_t)p->dx,(uint32_t)p->dy,
        (uint32_t)((uint64_t)p->origin>>32)&65535,0,0,0}};c->emit(&cmd);return 1;
}
static int triangle_planes(const gpu_v1_context *c,const gpu_vertex v[3],gpu_raster_plane p[7],unsigned *mask)
{
    for(unsigned i=0;i<3;++i)if(v[i].x<INT16_MIN || v[i].x>INT16_MAX || v[i].y<INT16_MIN || v[i].y>INT16_MAX ||
        v[i].u<-32768 || v[i].u>32767 || v[i].v<-32768 || v[i].v>32767 || v[i].z<0 || v[i].z>65535 ||
        v[i].q<0 || v[i].q>0xffffff || v[i].r<0 || v[i].r>256 || v[i].g<0 || v[i].g>256 || v[i].b<0 || v[i].b>256)return 0;
    int64_t area=(int64_t)(v[1].x-v[0].x)*(v[2].y-v[0].y)-(int64_t)(v[1].y-v[0].y)*(v[2].x-v[0].x);
    *mask=(c->flags&1 ? 3U:0U)|(c->flags&16 ? 4U:0U)|(c->flags&134 ? 8U:0U)|(c->flags&64 ? 112U:0U);
    if(!area){*mask=0;return 1;}
    for(unsigned k=0;k<7;++k)if(*mask&(1U<<k)) {
        int64_t f[3];
        for(unsigned i=0;i<3;++i) {
            int value=k==0?v[i].u:k==1?v[i].v:k==2?v[i].q:k==3?v[i].z:k==4?v[i].r:k==5?v[i].g:v[i].b;
            f[i]=k==2?value:(int64_t)value*(k<2 && (c->flags&16)?v[i].q:65536);
        }
        int64_t dx=((f[1]-f[0])*(v[2].y-v[0].y)-(f[2]-f[0])*(v[1].y-v[0].y))/area;
        int64_t dy=((int64_t)(v[1].x-v[0].x)*(f[2]-f[0])-(int64_t)(v[2].x-v[0].x)*(f[1]-f[0]))/area;
        // Reject extreme thin triangles before multiplying a gradient by x/y.
        if(dx<INT32_MIN || dx>INT32_MAX || dy<INT32_MIN || dy>INT32_MAX)return 0;
        int64_t origin=f[0]-dx*v[0].x-dy*v[0].y+(dx+dy)/2;
        if(origin<-(1LL<<47) || origin>=(1LL<<47))return 0;
        p[k]=(gpu_raster_plane){origin,(int32_t)dx,(int32_t)dy};
    }
    return 1;
}
int gpu_v1_triangle(gpu_v1_context *c,const gpu_vertex v[3])
{
    gpu_raster_plane p[7];unsigned mask;
    if(!triangle_planes(c,v,p,&mask))return 0;
    if(!((int64_t)(v[1].x-v[0].x)*(v[2].y-v[0].y)-(int64_t)(v[1].y-v[0].y)*(v[2].x-v[0].x)))return 1;
    for(unsigned k=0;k<7;++k)if(mask&(1U<<k))gpu_v1_plane(c,k,&p[k]);
    gpu_command cmd={{27U<<24,xy(v[0].x,v[0].y),xy(v[1].x,v[1].y),xy(v[2].x,v[2].y),0,0,0,0}};c->emit(&cmd);return 1;
}
int gpu_v1_quad(gpu_v1_context *c,const gpu_vertex v[4])
{
    gpu_vertex second[3]={v[0],v[2],v[3]};gpu_raster_plane p[7];unsigned mask;
    if(!triangle_planes(c,v,p,&mask) || !triangle_planes(c,second,p,&mask))return 0;
    return gpu_v1_triangle(c,v) && gpu_v1_triangle(c,second);
}
int gpu_v1_clear(gpu_v1_context *c,unsigned flags,unsigned color,unsigned depth,int x,int y,unsigned w,unsigned h)
{
    if(flags>3 || color>65535 || depth>65535 || x<INT16_MIN || x>INT16_MAX || y<INT16_MIN || y>INT16_MAX || w>65535 || h>65535)return 0;
    gpu_command cmd={{28U<<24,flags,color,depth,xy(x,y),xy(w,h),0,0}};c->emit(&cmd);return 1;
}
int gpu_v1_copy(gpu_v1_context *c,const gpu_target *s,int sx,int sy,int x,int y,unsigned w,unsigned h)
{
    if(!region(s->color,s->width,s->height,s->stride,1024,512) || sx<INT16_MIN || sx>INT16_MAX || sy<INT16_MIN || sy>INT16_MAX ||
       x<INT16_MIN || x>INT16_MAX || y<INT16_MIN || y>INT16_MAX || w>65535 || h>65535)return 0;
    uint32_t src_end=s->color+(uint32_t)s->stride*s->height;
    uint32_t dst_end=c->target.color+(uint32_t)c->target.stride*c->target.height;
    if(s->color<dst_end && c->target.color<src_end && (s->color!=c->target.color || s->stride!=c->target.stride))return 0;
    gpu_command cmd={{29U<<24,s->color,xy(s->width,s->height),s->stride,xy(sx,sy),xy(x,y),xy(w,h),0}};c->emit(&cmd);return 1;
}
void gpu_v1_invalidate(gpu_v1_context *c){gpu_command cmd={{30U<<24,0,0,0,0,0,0,0}};c->emit(&cmd);}
void gpu_v1_font(uint16_t *atlas,const uint8_t font[4096])
{
    for(unsigned ch=0;ch<256;++ch)for(unsigned y=0;y<16;++y)for(unsigned x=0;x<8;++x)
        atlas[((ch/16)*16+y)*128+(ch%16)*8+x]=(font[ch*16+y]&(128U>>x))?0xffff:0;
}
int gpu_v1_text(gpu_v1_context *c,uint32_t atlas,int x,int y,unsigned color,unsigned alpha,unsigned scale,const char *text)
{
    if(!scale || scale>16 || alpha>256 || color>65535)return 0;
    gpu_texture_level t={atlas,128,256,256,GPU_ARGB4444,0,0,0};
    gpu_material m={1,alpha,0,((color>>11)*256+15)/31,(((color>>5)&63)*256+31)/63,((color&31)*256+15)/31,0,0,0};
    if(!gpu_v1_texture(c,&t) || !gpu_v1_material(c,&m))return 0;
    for(;*text;++text,x+=8*(int)scale) {
        if(x<INT16_MIN || x>INT16_MAX-8*(int)scale || y<INT16_MIN || y>INT16_MAX-16*(int)scale)return 0;
        unsigned ch=(uint8_t)*text;int u=(ch%16)*8,v=(ch/16)*16;
        gpu_vertex corners[4]={{x,y,u,v,0,0,256,256,256},{x+8*(int)scale,y,u+8,v,0,0,256,256,256},
            {x+8*(int)scale,y+16*(int)scale,u+8,v+16,0,0,256,256,256},{x,y+16*(int)scale,u,v+16,0,0,256,256,256}};
        if(!gpu_v1_quad(c,corners))return 0;
    }
    return 1;
}
int gpu_v1_image(gpu_v1_context *c,const gpu_texture_level *t,const gpu_vertex corners[4],unsigned alpha)
{
    gpu_material m={1,alpha,0,256,256,256,0,0,0};
    if(alpha>256 || !gpu_v1_texture(c,t) || !gpu_v1_material(c,&m))return 0;
    return gpu_v1_quad(c,corners);
}

int gpu_v1_asset_level(const void *data,unsigned bytes,uint32_t gpu_base,unsigned lod,unsigned u_mode,unsigned v_mode,gpu_texture_level *out)
{
    if(!data || !out || ((uintptr_t)data&3) || (gpu_base&31) || bytes<32 || u_mode>2 || v_mode>2)return 0;
    const uint32_t *h=(const uint32_t *)data;
    if(h[0]!=0x31545647 || h[1]!=1 || h[2]>1 || !h[3] || h[3]>10 || lod>=h[3] || h[4]>512 || !h[4] ||
       h[5]>512 || !h[5] || h[6]>bytes || h[6]<32+h[3]*16 || h[7] || (uint64_t)gpu_base+h[6]>0x40000000ULL)return 0;
    const uint32_t *l=h+8+lod*4;
    unsigned width=l[1]>>16,height=l[1]&65535;
    if(l[0]<((32+h[3]*16+31)&~31U) || l[3]!=lod || l[2]>65535 ||
       width!=((h[4]+(1U<<lod)-1)>>lod) || height!=((h[5]+(1U<<lod)-1)>>lod) ||
       (uint64_t)l[0]+(uint64_t)l[2]*height>h[6] ||
       !region(gpu_base+l[0],width,height,l[2],512,512) ||
       (u_mode==1 && (width&(width-1))) || (v_mode==1 && (height&(height-1))))return 0;
    *out=(gpu_texture_level){gpu_base+l[0],width,height,l[2],h[2],u_mode,v_mode,lod};return 1;
}
