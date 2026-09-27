#include "gpu.h"
#include "cache.h"
#define BLT ((volatile uint32_t *)0xe9001000UL)
static uint16_t submitted;

int gpu_blit_init(void)
{
    if (BLT[0] != 0x424c5432U) return 0;
    submitted = (uint16_t)BLT[2];
    return 1;
}
gpu_command gpu_make_command(unsigned op, unsigned dst, unsigned src,
    int x, int y, int a, int b, int sx, int sy, unsigned fg, unsigned bg)
{
    gpu_command cmd = {{(op << 24) | ((dst & 15) << 20) | ((src & 15) << 16)
        | ((fg & 255) << 8) | (bg & 255),
        ((uint32_t)(uint16_t)x << 16) | (uint16_t)y,
        ((uint32_t)(uint16_t)a << 16) | (uint16_t)b,
        ((uint32_t)(uint16_t)sx << 16) | (uint16_t)sy, 0,0,0,0}};
    return cmd;
}
void gpu_submit(const gpu_command *cmd)
{
    for (unsigned i = 0; i < 8; ++i) BLT[4] = cmd->words[i];
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    ++submitted;
}
int gpu_wait(void)
{
    unsigned timeout = 20000000;
    while ((uint16_t)BLT[2] != submitted && --timeout) {}
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return timeout && !gpu_errors();
}
unsigned gpu_completed(void) { return BLT[2]; }
unsigned gpu_errors(void) { return BLT[3] | BLT[7]; }
void gpu_text(unsigned page, int x, int y, unsigned fg, unsigned bg,
              unsigned scale, const char *text)
{
    scale = scale == 2 ? 2 : 1;
    while (*text) {
        gpu_command cmd = gpu_make_command(GPU_TEXT,page,0,x,y,0,scale,0,0,fg,bg);
        unsigned n = 0;
        while (n < 16 && *text) {
            cmd.words[4+n/4] |= (uint32_t)(uint8_t)*text++ << (8*(n%4));
            ++n;
        }
        cmd.words[2] |= n << 16;
        gpu_submit(&cmd);
        x += (int)(n*8*scale);
    }
}
void gpu_font_write(unsigned address, const uint8_t *bytes, unsigned count)
{
    BLT[5] = address & 4095;
    while (count--) BLT[6] = *bytes++;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}
void gpu_publish_surface(unsigned long address, unsigned long bytes)
{
    if (!bytes) return;
    ae350_dcache_flush_range(address,bytes);
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    // Flush invalidates these lines. Read back the final byte through DDR so
    // posted writes in the CPU bridge/arbiter have drained before another
    // master can read this surface. Do not modify it again until the GPU fence.
    (void)*(volatile uint8_t *)(address+bytes-1);
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}
