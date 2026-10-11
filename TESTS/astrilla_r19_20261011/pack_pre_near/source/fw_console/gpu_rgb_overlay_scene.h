#ifndef CONSOLE_GPU_RGB_OVERLAY_SCENE_H
#define CONSOLE_GPU_RGB_OVERLAY_SCENE_H
#include "gpu.h"
// Assets are generated once; animation changes only descriptors at vblank.
static const char overlay_title[]="PERSPECTIVE + RGB565 + COUCHES / SPRITES";
static const char overlay_legend[]="TEXTURES 3D - Z16 - ALPHA       DECOR 2D INDEPENDANT";
static unsigned overlay_text(unsigned x,unsigned y,const uint8_t *font)
{
    const char *text=y<16 ? overlay_title:overlay_legend;
    unsigned row=y<16 ? y:y-24,n=x/8;
    unsigned count=y<16 ? sizeof(overlay_title)-1:sizeof(overlay_legend)-1;
    return row<16 && n<count && (font[(unsigned char)text[n]*16+row]&(128>>(x%8))) ? 255:0;
}
static unsigned overlay_sprite(unsigned x,unsigned y)
{
    int d=(int)y-16;if(d<0)d=-d;
    return x>=4 && x<29 && d<(int)(32-x)/2 ? (x<9 ? 224:255):0;
}
static unsigned overlay_tile(unsigned tile,unsigned x,unsigned y)
{ return (x+y)%3==0 ? 0:tile ? 28:227; }
static unsigned overlay_palette(unsigned i)
{ return (((i>>5)*9)<<12)|((((i>>2)&7)*9)<<6)|((i&3)*21); }
static void overlay_descriptors(unsigned angle,gpu_layer layers[16],gpu_sprite sprites[64])
{
    for(unsigned i=0;i<16;++i)layers[i]=(gpu_layer){{0}};
    for(unsigned i=0;i<64;++i)sprites[i]=(gpu_sprite){{0}};
    layers[0]=gpu_make_layer(GPU_PAGE_ADDR(9),800,768,40,16,8,768,40,0,0,3);
    // Index zero is deliberately opaque on this small lower-left patch.
    layers[3]=gpu_make_layer(GPU_PAGE_ADDR(9)+800*48,800,80,16,16,448,80,16,0,0,1);
    layers[6]=gpu_make_tile_layer(GPU_PAGE_ADDR(11),GPU_PAGE_ADDR(12),8,4,4,
        0,472,800,8,angle&127,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO|GPU_LAYER_WRAP_X);
    sprites[0]=gpu_make_sprite(GPU_PAGE_ADDR(10),16+(angle*3)%736,438,32,32,4,GPU_SPRITE_ENABLE);
}
// Independent composition for the demo's sparse overlay, including opaque 0.
static int overlay_sample(unsigned x,unsigned y,unsigned angle,const uint8_t *font)
{
    int pixel=-1;
    if(x>=16 && x<784 && y>=8 && y<48) {
        unsigned c=overlay_text(x-16,y-8,font);if(c)pixel=(int)c;
    }
    if(x>=16 && x<96 && y>=448 && y<464)pixel=0;
    int sx=(int)x-(16+(int)((angle*3)%736)),sy=(int)y-438;
    if(sx>=0 && sx<32 && sy>=0 && sy<32) {
        unsigned c=overlay_sprite((unsigned)sx,(unsigned)sy);if(c)pixel=(int)c;
    }
    if(y>=472) {
        unsigned tx=(x+(angle&127))&127;
        unsigned c=overlay_tile((tx/8)&1,tx&7,y-472);if(c)pixel=(int)c;
    }
    return pixel;
}
#endif
