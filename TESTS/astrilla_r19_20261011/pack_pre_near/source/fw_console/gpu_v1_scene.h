#ifndef CONSOLE_GPU_V1_SCENE_H
#define CONSOLE_GPU_V1_SCENE_H
#include "gpu_v1.h"
#define V1_TEXTURE_BASE GPU_PAGE_ADDR(15)
#define V1_ALPHA_BASE (V1_TEXTURE_BASE+0xb0000)
#define V1_FONT_BASE (V1_TEXTURE_BASE+0xc0000)
#define V1_PITCH 832U
// Fixed resource layout used by the three qualification scenes, not by the API.
static uint16_t v1_asset(unsigned x,unsigned y)
{
    if(y<256) {
        unsigned grain=(x*13+y*7+(x*y)%17)&7;
        return (uint16_t)((3+grain/2)<<11)|((24+grain*2)<<5)|(3+grain/3);
    }
    if(x<256) {
        if((y&31)<2 || ((x+((y>>5)&1)*16)&63)<2)return 0x4208;
        return (uint16_t)((15+((x^y)&3))<<11)|(19<<5)|9;
    }
    unsigned grain=(x*3+y*5)&3;
    return (uint16_t)((7+grain)<<11)|((14+grain*2)<<5)|(7+grain);
}
static uint16_t v1_alpha_asset(unsigned x,unsigned y)
{
    int dx=(int)x-31,dy=(int)y-31;unsigned d=(unsigned)(dx*dx+dy*dy);
    unsigned a=d>=960?0:d<=576?15:(960-d)*15/384;
    return (uint16_t)((a<<12)|((x/4)<<8)|((15-y/4)<<4)|12);
}
static uint32_t v1_level_offset(unsigned lod)
{
    uint32_t offset=0;
    for(unsigned k=0;k<lod;++k){unsigned n=512U>>k;offset+=((n*2+31)&~31U)*n;}
    return offset;
}
static gpu_texture_level v1_level(unsigned lod)
{
    unsigned n=512U>>lod;
    return (gpu_texture_level){V1_TEXTURE_BASE+v1_level_offset(lod),n,n,(n*2+31)&~31U,GPU_RGB565,2,2,lod};
}
static void v1_assets(uint16_t *base,const uint8_t font[4096])
{
    for(unsigned y=0;y<512;++y)for(unsigned x=0;x<512;++x)base[y*512+x]=v1_asset(x,y);
    for(unsigned lod=1;lod<=9;++lod) {
        unsigned n=512U>>lod,prev_stride=(((n*2)*2+31)&~31U)/2,stride=((n*2+31)&~31U)/2;
        uint16_t *src=base+v1_level_offset(lod-1)/2,*dst=base+v1_level_offset(lod)/2;
        for(unsigned y=0;y<n;++y)for(unsigned x=0;x<n;++x) {
            unsigned r=0,g=0,b=0;
            for(unsigned yy=0;yy<2;++yy)for(unsigned xx=0;xx<2;++xx){unsigned p=src[(y*2+yy)*prev_stride+x*2+xx];r+=p>>11;g+=(p>>5)&63;b+=p&31;}
            dst[y*stride+x]=(uint16_t)((((r+2)/4)<<11)|(((g+2)/4)<<5)|((b+2)/4));
        }
    }
    for(unsigned y=0;y<64;++y)for(unsigned x=0;x<64;++x)base[0xb0000/2+y*64+x]=v1_alpha_asset(x,y);
    gpu_v1_font(base+0xc0000/2,font);
}
static int v1_rect_texture(gpu_v1_context *c,int x,int y,int w,int h,int u,int v,int uw,int vh,int z)
{
    gpu_vertex p[4]={{x,y,u,v,z,65536,256,256,256},{x+w,y,u+uw,v,z,65536,256,256,256},
        {x+w,y+h,u+uw,v+vh,z,65536,256,256,256},{x,y+h,u,v+vh,z,65536,256,256,256}};
    return gpu_v1_quad(c,p);
}
static int v1_scene(gpu_v1_context *c,unsigned scene,unsigned phase,unsigned page)
{
    gpu_target target={GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,V1_PITCH,V1_PITCH};
    if(!gpu_v1_target(c,&target))return 0;
    gpu_v1_clear(c,3,scene==0?0x2385:0x5b90,65535,0,0,400,240);
    // Render viewport is inset; the full-resolution HUD is composed separately.
    if(!gpu_v1_viewport(c,4,12,392,218) || !gpu_v1_scissor(c,4,12,392,218))return 0;
    gpu_texture_level texture=v1_level(scene==0?1:0);
    gpu_material material={1|6,256,0,256,256,256,0,0,0};
    if(!gpu_v1_texture(c,&texture) || !gpu_v1_material(c,&material))return 0;
    int shift=(int)(phase%24)-12;
    if(scene==0) {
        // Adventure: tile-sized textured floor patches, buildings, alpha foliage.
        for(int row=0;row<3;++row)for(int col=0;col<6;++col)
            if(!v1_rect_texture(c,20+col*60+shift,32+row*54,48,44,col*64,row*64,64,64,50000))return 0;
        texture=v1_level(0);if(!gpu_v1_texture(c,&texture))return 0;
        for(int col=0;col<3;++col)if(!v1_rect_texture(c,52+col*118,56,60,58,16+col*64,270,64,64,30000))return 0;
        gpu_texture_level alpha={V1_ALPHA_BASE,64,64,128,GPU_ARGB4444,2,2,0};
        if(!gpu_v1_texture(c,&alpha))return 0;
        material.flags=1|2;material.alpha=208;if(!gpu_v1_material(c,&material))return 0;
        for(int col=0;col<4;++col)if(!v1_rect_texture(c,26+col*92,130+shift,48,48,0,0,64,64,20000))return 0;
    } else {
        // FPS/racing: floor or road with reciprocal-depth texture mapping and fog.
        material.flags=1|6|16|128;material.fog_near=22000;material.fog_color=0x8c95;material.fog_scale=700;
        if(!gpu_v1_material(c,&material))return 0;
        int left=scene==1?4:138+shift,right=scene==1?396:262+shift;
        gpu_vertex floor[4]={{left,85,256,(int)(phase%64)+256,56000,16384,256,256,256},
            {right,85,511,(int)(phase%64)+256,56000,16384,256,256,256},
            {396,225,511,(int)(phase%64)+448,8000,131072,256,256,256},
            {4,225,256,(int)(phase%64)+448,8000,131072,256,256,256}};
        if(!gpu_v1_quad(c,floor))return 0;
        if(scene==1) {
            // Corridor walls: perspective and per-vertex illumination.
            material.flags=1|6|16|64|128;if(!gpu_v1_material(c,&material))return 0;
            gpu_vertex wall[4]={{4,22,0,256,9000,131072,256,230,210},{128+shift,68,192,256,53000,16384,90,120,150},
                {128+shift,170,192,448,53000,16384,90,120,150},{4,226,0,448,9000,131072,256,230,210}};
            if(!gpu_v1_quad(c,wall))return 0;
            for(unsigned i=0;i<4;++i)wall[i].x=400-wall[i].x;
            if(!gpu_v1_quad(c,wall))return 0;
            // Solid crosshair is an RGB565 primitive.
            gpu_v1_clear(c,1,0xffff,0,196,119,8,2);gpu_v1_clear(c,1,0xffff,0,199,116,2,8);
        } else {
            // Two-lane road: perspective center marks, roadside quads and vehicles.
            material.flags=6;material.color=0xffac;if(!gpu_v1_material(c,&material))return 0;
            for(int n=0;n<4;++n) {
                int y=100+n*29+(int)(phase%14),w=2+n;
                if(!v1_rect_texture(c,200+shift-w,y,w*2,12+n*2,0,0,0,0,25000-n*4000))return 0;
            }
            material.color=0xf940;if(!gpu_v1_material(c,&material))return 0;
            if(!v1_rect_texture(c,148+shift,164,29,26,0,0,0,0,14000))return 0;
            material.color=0x253f;if(!gpu_v1_material(c,&material))return 0;
            if(!v1_rect_texture(c,240-shift,123,18,15,0,0,0,0,22000))return 0;
        }
    }
    // Additive particles and direct RGB text/copy cover the API complements.
    gpu_texture_level alpha={V1_ALPHA_BASE,64,64,128,GPU_ARGB4444,2,2,0};
    material=(gpu_material){1|32,144,0,256,180,80,0,0,0};
    if(!gpu_v1_texture(c,&alpha) || !gpu_v1_material(c,&material) ||
       !v1_rect_texture(c,340-shift,36,26,26,0,0,64,64,0))return 0;
    if(!gpu_v1_text(c,V1_FONT_BASE,12,210,0xffff,256,1,scene==0?"ADVENTURE":scene==1?"FPS 3D":"RACING"))return 0;
    gpu_v1_copy(c,&target,340-shift,36,364,198,20,20);
    return 1;
}
static inline unsigned v1_hud_pixel(unsigned x,unsigned y,const uint8_t font[4096])
{
    static const char title[]="GPU V1  400x240 + HUD 800x480";
    if(y>=20)return 0;
    if(y<2 || y>=18)return 1;
    unsigned ch=x/8;
    return ch<sizeof(title)-1 && (font[(unsigned char)title[ch]*16+y-2]&(128U>>(x%8))) ? 255:2;
}
#endif
