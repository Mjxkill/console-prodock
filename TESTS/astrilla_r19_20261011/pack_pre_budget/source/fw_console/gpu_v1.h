#ifndef CONSOLE_GPU_V1_H
#define CONSOLE_GPU_V1_H
#include "gpu.h"
// V1 ABI 1. Byte addresses in the first GiB. All bases/pitches are 32-byte aligned.
// Single producer; changes to texture memory require publish + ordered invalidate.
enum { GPU_V1_TARGET=22,GPU_V1_SCISSOR,GPU_V1_TEXTURE,GPU_V1_MATERIAL,GPU_V1_PLANE,
       GPU_V1_TRIANGLE,GPU_V1_CLEAR,GPU_V1_COPY,GPU_V1_INVALIDATE };
enum { GPU_V1_ADDITIVE=32,GPU_V1_GOURAUD=64,GPU_V1_FOG=128 };
enum { GPU_RGB565=0,GPU_ARGB4444=1 };
typedef struct { uint32_t color,depth;uint16_t width,height,stride,zstride; } gpu_target;
typedef struct { uint32_t base;uint16_t width,height,stride;uint8_t format,u_mode,v_mode,lod; } gpu_texture_level;
typedef struct { uint16_t flags,alpha,color,r,g,b,fog_near,fog_color;uint32_t fog_scale; } gpu_material;
typedef struct { int x,y,u,v,z,q,r,g,b; } gpu_vertex;
typedef struct {
    void (*emit)(const gpu_command *);
    gpu_target target;
    unsigned flags;
    int vx,vy,vw,vh;
} gpu_v1_context;
void gpu_v1_init(gpu_v1_context *c,void (*emit)(const gpu_command *));
int gpu_v1_target(gpu_v1_context *c,const gpu_target *t);
int gpu_v1_scissor(gpu_v1_context *c,unsigned x,unsigned y,unsigned w,unsigned h);
int gpu_v1_viewport(gpu_v1_context *c,int x,int y,unsigned w,unsigned h);
// Map signed Q16 NDC to the viewport; clipping/near-plane intersection precedes this.
int gpu_v1_project(const gpu_v1_context *c,int nx,int ny,int *x,int *y);
int gpu_v1_texture(gpu_v1_context *c,const gpu_texture_level *t);
int gpu_v1_material(gpu_v1_context *c,const gpu_material *m);
int gpu_v1_plane(gpu_v1_context *c,unsigned index,const gpu_raster_plane *p);
// Vertex UV in base-level texels, Z=0..65535, Q positive reciprocal-depth scale <=0xffffff,
// RGB gains 0..256. Gouraud interpolates gains in screen space and replaces tint.
int gpu_v1_triangle(gpu_v1_context *c,const gpu_vertex v[3]);
int gpu_v1_quad(gpu_v1_context *c,const gpu_vertex v[4]);
int gpu_v1_clear(gpu_v1_context *c,unsigned flags,unsigned color,unsigned depth,int x,int y,unsigned w,unsigned h);
int gpu_v1_copy(gpu_v1_context *c,const gpu_target *src,int sx,int sy,int x,int y,unsigned w,unsigned h);
void gpu_v1_invalidate(gpu_v1_context *c);
// Atlas: 128x256 ARGB4444, 16 columns of 8x16 glyphs. Upload before first use.
void gpu_v1_font(uint16_t *atlas,const uint8_t font[4096]);
int gpu_v1_text(gpu_v1_context *c,uint32_t atlas,int x,int y,unsigned color,unsigned alpha,unsigned scale,const char *text);
// Images, zoom and rotation reuse the same quad/triangle pipeline. No second rasterizer.
int gpu_v1_image(gpu_v1_context *c,const gpu_texture_level *texture,const gpu_vertex corners[4],unsigned alpha);
// Native LCD or 400x240 x2. Indexed layers/sprites stay at native LCD resolution.
int gpu_rgb565_surface_submit(const gpu_target *t,unsigned half,const gpu_layer layers[16],const gpu_sprite sprites[64]);
// Validate a .gtex container in CPU-addressable memory and bind a selected mip.
// The caller has already published its bytes to the GPU's DDR address gpu_base.
int gpu_v1_asset_level(const void *data,unsigned bytes,uint32_t gpu_base,unsigned lod,
                       unsigned u_mode,unsigned v_mode,gpu_texture_level *out);
int gpu_v1_supported(void);
unsigned gpu_v1_rejected(void);
#endif
