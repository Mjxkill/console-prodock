#include "gpu_v1.h"
#include "cache.h"
#define BLT ((volatile uint32_t *)0xe9001000UL)
#define DISPLAY ((volatile uint32_t *)0xe9000000UL)
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
gpu_command gpu_make_zoom(unsigned dst,unsigned src,int x,int y,int w,int h,
                          int sx,int sy,unsigned sw,unsigned sh)
{
    gpu_command c=gpu_make_command(GPU_ZOOM,dst,src,x,y,w,h,sx,sy,0,0);
    if(w<=0 || h<=0 || w>32767 || h>32767 || sw<1 || sw>128 || sh<1 || sh>128) {
        c.words[2]=0;return c;
    }
    c.words[4]=(sw<<16)|sh;c.words[5]=(sw<<16)/(unsigned)w;c.words[6]=(sh<<16)/(unsigned)h;
    return c;
}
int gpu_affine_supported(void) { return (BLT[8]&1)!=0; }
int gpu_raster_supported(void) { return (BLT[8]&14)==14; }
int gpu_perspective_supported(void) { return (BLT[8]&16)!=0 && (DISPLAY[0x68/4]&1)!=0; }
unsigned gpu_raster_rejected(void) { return BLT[9]; }
int gpu_rgb565_present(unsigned page)
{
    if(page>15 || !gpu_display_wait())return 0;
    DISPLAY[0x6c/4]=0;DISPLAY[1]=GPU_PAGE_ADDR(page);DISPLAY[0x30/4]=0;DISPLAY[0x40/4]=0;DISPLAY[2]=3;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    DISPLAY[3]=1;
    return gpu_display_wait();
}
gpu_command gpu_make_affine_setup(const gpu_affine_transform *t)
{
    gpu_command c={{GPU_AFFINE_SETUP<<24,(uint32_t)t->u0,(uint32_t)t->v0,
        (uint32_t)t->du_dx,(uint32_t)t->dv_dx,(uint32_t)t->du_dy,(uint32_t)t->dv_dy,0}};
    return c;
}
gpu_command gpu_make_affine(unsigned dst,unsigned src,int x,int y,int w,int h,
                            int sx,int sy,unsigned sw,unsigned sh)
{
    gpu_command c=gpu_make_command(GPU_AFFINE,dst,src,x,y,w,h,sx,sy,0,0);
    if(w<=0 || h<=0 || w>32767 || h>32767 || sw<1 || sw>128 || sh<1 || sh>128 ||
       x< -32768 || x>32767 || y< -32768 || y>32767 ||
       sx<0 || sy<0 || sx>GPU_WIDTH-(int)sw || sy>GPU_HEIGHT-(int)sh) {
        c.words[2]=0;return c;
    }
    c.words[4]=(sw<<16)|sh;
    return c;
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
void gpu_triangle(unsigned page,int x0,int y0,int x1,int y1,int x2,int y2,
                  unsigned color,int filled)
{
    gpu_command c=gpu_make_command(filled ? GPU_TRIANGLE:GPU_LINE,page,0,
        x0,y0,x1,y1,x2,y2,color,0);
    gpu_submit(&c);
    if(!filled) {
        c=gpu_make_command(GPU_LINE,page,0,x1,y1,x2,y2,0,0,color,0);gpu_submit(&c);
        c=gpu_make_command(GPU_LINE,page,0,x2,y2,x0,y0,0,0,color,0);gpu_submit(&c);
    }
}
unsigned gpu_completed(void) { return BLT[2]; }
unsigned gpu_errors(void) { return BLT[3] | BLT[7] | BLT[9]; }
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
gpu_layer gpu_make_layer(unsigned long base,unsigned stride,unsigned width,unsigned height,
    int x,int y,unsigned view_width,unsigned view_height,unsigned scroll_x,unsigned scroll_y,unsigned flags)
{
    gpu_layer layer={{base,((height&65535)<<16)|(width&65535),
        ((uint32_t)(uint16_t)y<<16)|(uint16_t)x,
        ((view_height&65535)<<16)|(view_width&65535),
        ((scroll_y&65535)<<16)|(scroll_x&65535),stride&65535,flags&3,0}};
    return layer;
}
int gpu_tiles_supported(void) { return DISPLAY[0x5c/4]==0x00000d07U; }
gpu_layer gpu_make_tile_layer(unsigned long map,unsigned long atlas,unsigned tile_size,
    unsigned map_w_log2,unsigned map_h_log2,int x,int y,unsigned view_width,unsigned view_height,
    unsigned scroll_x,unsigned scroll_y,unsigned flags)
{
    // An unsupported size becomes code 3: the GPU rejects and counts the
    // layer, instead of displaying it with another tile size.
    unsigned code=tile_size==8 ? 0 : tile_size==16 ? 1 : tile_size==32 ? 2 : 3;
    gpu_layer layer={{map,atlas,
        ((uint32_t)(uint16_t)y<<16)|(uint16_t)x,
        ((view_height&65535)<<16)|(view_width&65535),
        ((scroll_y&65535)<<16)|(scroll_x&65535),
        (map_w_log2&15)|((map_h_log2&15)<<4)|(code<<8),
        (flags&(GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO|GPU_LAYER_WRAP_X|GPU_LAYER_WRAP_Y))|GPU_LAYER_TILES,0}};
    return layer;
}
int gpu_display_wait(void)
{
    unsigned timeout=1000000;
    while((DISPLAY[3]&1) && --timeout) {}
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return timeout!=0;
}
int gpu_layers_submit(const gpu_layer table[16])
{
    if(DISPLAY[0x28/4]!=16 || !gpu_display_wait()) return 0;
    for(unsigned l=0;l<16;++l)
        for(unsigned w=0;w<8;++w) DISPLAY[0x800/4+l*8+w]=table[l].words[w];
    DISPLAY[0x30/4]=1;
    DISPLAY[0x40/4]=0;
    DISPLAY[2]=1;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    DISPLAY[3]=1;
    return 1;
}
gpu_sprite gpu_make_sprite(unsigned long base,int x,int y,unsigned width,unsigned height,
    unsigned priority,unsigned flags)
{
    gpu_sprite sprite={{base,((uint32_t)(uint16_t)y<<16)|(uint16_t)x,
        (width&255)|((height&255)<<8)|((flags&7)<<16)|((priority&15)<<20),0}};
    return sprite;
}
static int gpu_scene_present(unsigned format,unsigned long base,unsigned stride,const gpu_layer layers[16],const gpu_sprite sprites[64])
{
    if(DISPLAY[0x3c/4]!=64 || !gpu_display_wait()) return 0;
    for(unsigned l=0;l<16;++l)
        for(unsigned w=0;w<8;++w) DISPLAY[0x800/4+l*8+w]=layers[l].words[w];
    for(unsigned s=0;s<64;++s)
        for(unsigned w=0;w<4;++w) DISPLAY[0xc00/4+s*4+w]=sprites[s].words[w];
    DISPLAY[0x6c/4]=stride;DISPLAY[1]=base;DISPLAY[0x30/4]=1;DISPLAY[0x40/4]=1;DISPLAY[2]=format;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    DISPLAY[3]=1;
    return 1;
}

int gpu_scene_submit(const gpu_layer layers[16],const gpu_sprite sprites[64])
{ return gpu_scene_present(1,DISPLAY[1],0,layers,sprites); }
int gpu_rgb565_scene_submit(unsigned page,const gpu_layer layers[16],const gpu_sprite sprites[64])
{ return page<16 && gpu_scene_present(3,GPU_PAGE_ADDR(page),0,layers,sprites); }

int gpu_v1_supported(void){return BLT[0x30/4]==0x1ff && (DISPLAY[0x68/4]&7)==7;}
unsigned gpu_v1_rejected(void){return BLT[0x34/4];}
int gpu_rgb565_surface_submit(const gpu_target *t,unsigned half,const gpu_layer layers[16],const gpu_sprite sprites[64])
{
    if(half>1 || t->width!=(half?400:800) || t->height!=(half?240:480) ||
       (t->color&31) || (t->stride&31) || t->stride<t->width*2 ||
       (uint64_t)t->color+(uint64_t)t->height*t->stride>0x40000000ULL)return 0;
    return gpu_scene_present(half?7:3,t->color,t->stride,layers,sprites);
}
