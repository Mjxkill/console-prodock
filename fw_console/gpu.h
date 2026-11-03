#ifndef CONSOLE_GPU_H
#define CONSOLE_GPU_H
#include <stdint.h>

#define GPU_WIDTH 800
#define GPU_HEIGHT 480
#define GPU_PAGE_BYTES 1048576UL
#define GPU_PAGE_ADDR(p) (0x00800000UL + (unsigned)(p) * GPU_PAGE_BYTES)
enum gpu_opcode { GPU_FILL=1, GPU_GRAD_H, GPU_GRAD_V, GPU_GRAD_D,
                  GPU_LINE, GPU_CIRCLE, GPU_DISK, GPU_COPY, GPU_TEXT, GPU_TRIANGLE, GPU_ZOOM,
                  GPU_AFFINE_SETUP, GPU_AFFINE,
                  GPU_RASTER_STATE, GPU_TEXTURE, GPU_PLANE_U, GPU_PLANE_V,
                  GPU_PLANE_Z, GPU_RASTER_TRIANGLE, GPU_RASTER_CLEAR, GPU_PLANE_Q };
typedef struct { uint32_t words[8]; } gpu_command;

// One producer. Flush CPU-written surfaces before submitting GPU work;
// invalidate GPU-written surfaces after waiting, before reading them on CPU.
// Font updates require all preceding text commands to have completed.
int gpu_blit_init(void);
gpu_command gpu_make_command(unsigned op, unsigned dst, unsigned src,
    int x, int y, int a, int b, int sx, int sy, unsigned fg, unsigned bg);
void gpu_submit(const gpu_command *cmd);
// Filled: pixel centres, top-left rule, either winding, zero area draws nothing.
// Outline: three accelerated Bresenham lines. Coordinates are signed 16-bit.
void gpu_triangle(unsigned page,int x0,int y0,int x1,int y1,int x2,int y2,
                  unsigned color,int filled);
// Nearest neighbour transparent zoom; source crop 1..128 per axis, within
// an 800x480 page. Different source/destination pages. Dest size 1..32767.
// Q16 sampling: floor(relative * floor(source_size*65536/dest_size)/65536).
gpu_command gpu_make_zoom(unsigned dst,unsigned src,int x,int y,int w,int h,
                          int sx,int sy,unsigned sw,unsigned sh);
// Inverse transform from destination-relative coordinates to source-relative
// coordinates. All six coefficients are signed Q16.16; samples use floor.
// Submit SETUP before DRAW. SETUP persists until replaced/reset; both count
// as commands. Source 1..128 per axis, destination 1..32767; zero/outside is
// transparent. Same-page overlap uses a snapshot of the entire source crop.
typedef struct { int32_t u0,v0,du_dx,dv_dx,du_dy,dv_dy; } gpu_affine_transform;
int gpu_affine_supported(void);
gpu_command gpu_make_affine_setup(const gpu_affine_transform *transform);
gpu_command gpu_make_affine(unsigned dst,unsigned src,int x,int y,int w,int h,
                            int sx,int sy,unsigned sw,unsigned sh);
int gpu_wait(void);
void gpu_text(unsigned page, int x, int y, unsigned fg, unsigned bg,
              unsigned scale, const char *text);
void gpu_font_write(unsigned address, const uint8_t *bytes, unsigned count);
void gpu_publish_surface(unsigned long address, unsigned long bytes);
unsigned gpu_completed(void);
unsigned gpu_errors(void);
enum { GPU_RASTER_TEXTURE=1, GPU_Z_TEST=2, GPU_Z_WRITE=4, GPU_KEY_ZERO=8, GPU_PERSPECTIVE=16 };
enum { GPU_TEX_DISCARD=0, GPU_TEX_REPEAT=1, GPU_TEX_CLAMP=2 };
typedef struct { int64_t origin; int32_t dx,dy; } gpu_raster_plane;
int gpu_raster_supported(void);
int gpu_perspective_supported(void);
unsigned gpu_raster_rejected(void);
int gpu_rgb565_present(unsigned page);
// Pure legacy raster packet builders, implemented in gpu_raster_commands.c.
// They do not submit commands or access MMIO. Unencodable fields retain the
// invalid-packet marker so the GPU rejects them instead of silently clipping.
gpu_command gpu_make_raster_state(unsigned page,unsigned zpage,unsigned flags,
                                  unsigned alpha,unsigned color);
gpu_command gpu_make_texture(unsigned page,unsigned x,unsigned y,unsigned width,
                             unsigned height,unsigned mode_u,unsigned mode_v);
// Plane origin is signed 48-bit; dx/dy are signed 32-bit fixed-point values.
gpu_command gpu_make_plane(unsigned op,const gpu_raster_plane *p);
gpu_command gpu_make_raster_clear(unsigned flags,unsigned color,unsigned depth);

typedef struct { uint32_t words[8]; } gpu_layer;
enum { GPU_LAYER_ENABLE=1, GPU_LAYER_KEY_ZERO=2, GPU_LAYER_TILES=4,
       GPU_LAYER_WRAP_X=8, GPU_LAYER_WRAP_Y=16 };
gpu_layer gpu_make_layer(unsigned long base,unsigned stride,unsigned width,unsigned height,
    int x,int y,unsigned view_width,unsigned view_height,unsigned scroll_x,unsigned scroll_y,unsigned flags);
// Upload all 16 descriptors to the inactive bank, then request a vblank swap.
// Priority is the table index: layer 0 behind, layer 15 in front.
int gpu_layers_submit(const gpu_layer table[16]);
int gpu_display_wait(void);
// L11 tile map layer: composed like a surface of (map size x tile size)
// pixels, without any drawing command. Map: 16-bit entries, row-major,
// 2^map_w_log2 (16..4096) by 2^map_h_log2 tiles, at most 32768 pixels per
// axis. Atlas: tile i is tile_size*tile_size bytes at atlas+i*size*size.
// tile_size 8, 16 or 32. Both addresses 32-byte aligned; the map and 8192
// atlas tiles must lie in the first GiB. The GPU counts a layer that breaks
// these rules in its invalid layer counter and does not display it.
// A wrapped axis repeats the map; otherwise the map ends like a surface.
// Window sizes up to 32768. Flags: ENABLE, KEY_ZERO, WRAP_X, WRAP_Y.
enum { GPU_TILE_INDEX=0x1fff, GPU_TILE_FLIP_X=0x4000, GPU_TILE_FLIP_Y=0x8000 }; // bit 13: write zero
int gpu_tiles_supported(void);
gpu_layer gpu_make_tile_layer(unsigned long map,unsigned long atlas,unsigned tile_size,
    unsigned map_w_log2,unsigned map_h_log2,int x,int y,unsigned view_width,unsigned view_height,
    unsigned scroll_x,unsigned scroll_y,unsigned flags);
typedef struct { uint32_t words[4]; } gpu_sprite;
enum { GPU_SPRITE_ENABLE=1, GPU_SPRITE_FLIP_X=2, GPU_SPRITE_FLIP_Y=4 };
// Indexed pixels, 32-byte aligned base and fixed 32-byte pitch, size 1..32.
// Sprites at priority p appear above layer p and below layer p+1. A higher
// sprite table index wins ties. Index zero is always transparent.
gpu_sprite gpu_make_sprite(unsigned long base,int x,int y,unsigned width,unsigned height,
    unsigned priority,unsigned flags);
int gpu_scene_submit(const gpu_layer layers[16],const gpu_sprite sprites[64]);
// RGB565 background and indexed overlays committed together at vblank.
int gpu_rgb565_scene_submit(unsigned page,const gpu_layer layers[16],const gpu_sprite sprites[64]);
#endif
