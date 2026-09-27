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
#endif
