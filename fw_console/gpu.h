#ifndef CONSOLE_GPU_H
#define CONSOLE_GPU_H
#include <stdint.h>

#define GPU_WIDTH 800
#define GPU_HEIGHT 480
#define GPU_PAGE_BYTES 1048576UL
#define GPU_PAGE_ADDR(p) (0x00800000UL + (unsigned)(p) * GPU_PAGE_BYTES)
enum gpu_opcode { GPU_FILL=1, GPU_GRAD_H, GPU_GRAD_V, GPU_GRAD_D,
                  GPU_LINE, GPU_CIRCLE, GPU_DISK, GPU_COPY, GPU_TEXT };
typedef struct { uint32_t words[8]; } gpu_command;

// One producer. Flush CPU-written surfaces before submitting GPU work;
// invalidate GPU-written surfaces after waiting, before reading them on CPU.
// Font updates require all preceding text commands to have completed.
int gpu_blit_init(void);
gpu_command gpu_make_command(unsigned op, unsigned dst, unsigned src,
    int x, int y, int a, int b, int sx, int sy, unsigned fg, unsigned bg);
void gpu_submit(const gpu_command *cmd);
int gpu_wait(void);
void gpu_text(unsigned page, int x, int y, unsigned fg, unsigned bg,
              unsigned scale, const char *text);
void gpu_font_write(unsigned address, const uint8_t *bytes, unsigned count);
void gpu_publish_surface(unsigned long address, unsigned long bytes);
unsigned gpu_completed(void);
unsigned gpu_errors(void);

typedef struct { uint32_t words[8]; } gpu_layer;
enum { GPU_LAYER_ENABLE=1, GPU_LAYER_KEY_ZERO=2 };
gpu_layer gpu_make_layer(unsigned long base,unsigned stride,unsigned width,unsigned height,
    int x,int y,unsigned view_width,unsigned view_height,unsigned scroll_x,unsigned scroll_y,unsigned flags);
// Upload all 16 descriptors to the inactive bank, then request a vblank swap.
// Priority is the table index: layer 0 behind, layer 15 in front.
int gpu_layers_submit(const gpu_layer table[16]);
int gpu_display_wait(void);
typedef struct { uint32_t words[4]; } gpu_sprite;
enum { GPU_SPRITE_ENABLE=1, GPU_SPRITE_FLIP_X=2, GPU_SPRITE_FLIP_Y=4 };
// Indexed pixels, 32-byte aligned base and fixed 32-byte pitch, size 1..32.
// Sprites at priority p appear above layer p and below layer p+1. A higher
// sprite table index wins ties. Index zero is always transparent.
gpu_sprite gpu_make_sprite(unsigned long base,int x,int y,unsigned width,unsigned height,
    unsigned priority,unsigned flags);
int gpu_scene_submit(const gpu_layer layers[16],const gpu_sprite sprites[64]);
#endif
