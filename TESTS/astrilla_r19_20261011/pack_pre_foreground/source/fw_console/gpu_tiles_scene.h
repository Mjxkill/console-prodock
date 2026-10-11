// L11 tile map scene: atlases, maps, a surface and sprite images, all
// procedural. Shared by the firmware and tools/render_gpu_tiles.py: no
// register access here. Every address below is a DDR address; the host
// redirects TILES_MEMORY to its own buffer.
#ifndef CONSOLE_GPU_TILES_SCENE_H
#define CONSOLE_GPU_TILES_SCENE_H
#include "gpu.h"
#include "gpu_palette.h"

#define TILES_BASE      0x03000000UL              // 48 MiB, above the G4 sprite images
#define TILES_BYTES     0x00030000UL
#define TILES_ATLAS8    (TILES_BASE+0x00000UL)    // TILES_DESIGNS tiles of 64 bytes
#define TILES_ATLAS16   (TILES_BASE+0x01000UL)    // ... of 256 bytes
#define TILES_ATLAS32   (TILES_BASE+0x04000UL)    // ... of 1024 bytes
#define TILES_MAP_FAR   (TILES_BASE+0x08000UL)    // 32 x 16 tiles of 32 pixels
#define TILES_MAP_MAIN  (TILES_BASE+0x10000UL)    // 128 x 32 tiles of 16 pixels
#define TILES_MAP_PANEL (TILES_BASE+0x18000UL)    // 128 x 16 tiles of 8 pixels
#define TILES_BANNER    (TILES_BASE+0x20000UL)    // surface 256 x 48, pitch 256
#define TILES_SPRITES   (TILES_BASE+0x28000UL)    // TILES_SPRITE_COUNT images of 32 x 32
#define TILES_DESIGNS 12
#define TILES_SPRITE_COUNT 8
#define TILES_POSES 4
#ifndef TILES_MEMORY
#define TILES_MEMORY(address) ((uint8_t *)(address))
#endif

enum { TILE_EMPTY, TILE_GRASS, TILE_EARTH, TILE_BRICK, TILE_WATER, TILE_ARROW, TILE_LADDER,
       TILE_STAR, TILE_SKY, TILE_CLOUD, TILE_SLOPE, TILE_ROCK };
enum { TILE_GREEN=28, TILE_SKY_COLOR=DEMO_COOL_FIRST+6 };

// One design drawn at 8, 16 or 32 pixels. The arrow, the slope and the
// ladder rung are asymmetric: a wrong flip or row order changes the image.
static unsigned tiles_design_pixel(unsigned design,unsigned x,unsigned y,unsigned size)
{
    int xx=(int)(x*32/size),yy=(int)(y*32/size);
    int ax=xx>16 ? xx-16 : 16-xx,ay=yy>16 ? yy-16 : 16-yy;
    switch(design) {
    case TILE_GRASS: if(yy<10) return yy<3 ? DEMO_YELLOW : TILE_GREEN; // fall through
    case TILE_EARTH: return DEMO_GRAY_FIRST+12+(unsigned)((xx*7+yy*13)&7);
    case TILE_BRICK: return (yy%16==0 || (xx+(yy/16)*8)%16==0) ? DEMO_GRAY_FIRST+44
                                                             : DEMO_WARM_FIRST+4+(unsigned)((xx^yy)&3);
    case TILE_WATER: return DEMO_COOL_FIRST+16+(unsigned)((xx+yy*3)&15);
    case TILE_ARROW:
        if(xx<6 && yy<6) return DEMO_RED;
        return xx>=6 && ay*2<=28-xx ? DEMO_YELLOW : DEMO_TRANSPARENT;
    case TILE_LADDER:
        if(xx==6 || xx==7 || xx==24 || xx==25) return DEMO_WHITE;
        return xx>7 && xx<24 && yy%8<2 ? DEMO_CYAN : DEMO_TRANSPARENT;
    case TILE_STAR: return ax+ay<5 ? DEMO_WHITE : ax+ay<11 ? DEMO_YELLOW : DEMO_TRANSPARENT;
    case TILE_SKY: return TILE_SKY_COLOR;
    case TILE_CLOUD: return (xx-16)*(xx-16)+4*(yy-18)*(yy-18)<200 ? DEMO_GRAY_LAST-(unsigned)(yy&7) : TILE_SKY_COLOR;
    case TILE_SLOPE: return yy>=31-xx ? DEMO_GRAY_FIRST+24+(unsigned)(yy&3) : TILE_SKY_COLOR;
    case TILE_ROCK: return DEMO_GRAY_FIRST+24+(unsigned)((xx*3+yy)&3);
    default: return DEMO_TRANSPARENT;
    }
}
static unsigned tiles_far_entry(unsigned col,unsigned row)
{
    unsigned top=9+(col*5+col/3)%4; // first mountain row of this column
    if(row>top) return TILE_ROCK;
    if(row==top) return TILE_SLOPE|(col&1 ? GPU_TILE_FLIP_X : 0);
    return (col*5+row*3)%7==0 ? TILE_CLOUD : TILE_SKY;
}
static unsigned tiles_main_entry(unsigned col,unsigned row)
{
    unsigned pit=(col/8)%4==3;
    if(row>=27) return pit ? TILE_WATER : row==27 ? TILE_GRASS : TILE_EARTH;
    if(row==20-(col/16)%3*4 && col%16>=4 && col%16<=10) return TILE_BRICK;
    if(col%16==11 && row>20-(col/16)%3*4 && !pit) return TILE_LADDER;
    // All four orientations of the asymmetric arrow.
    if(row==25 && col%6==0 && !pit) return TILE_ARROW|((col/6)&1 ? GPU_TILE_FLIP_X : 0)|((col/6)&2 ? GPU_TILE_FLIP_Y : 0);
    if(row==17-(col/16)%3*4 && col%16==7) return TILE_STAR;
    return TILE_EMPTY;
}
static unsigned tiles_panel_entry(unsigned col,unsigned row)
{
    static const uint8_t designs[8]={TILE_BRICK,TILE_EMPTY,TILE_ARROW,TILE_STAR,TILE_EMPTY,TILE_LADDER,TILE_ARROW,TILE_WATER};
    return designs[(col+row*3)%8]|((col+row)&2 ? GPU_TILE_FLIP_X : 0)|(col&4 ? GPU_TILE_FLIP_Y : 0);
}
static void tiles_write_map(unsigned long address,unsigned width,unsigned height,unsigned (*entry)(unsigned,unsigned))
{
    uint8_t *map=TILES_MEMORY(address);
    for(unsigned row=0;row<height;++row) for(unsigned col=0;col<width;++col) {
        unsigned value=entry(col,row);
        *map++=(uint8_t)value;*map++=(uint8_t)(value>>8);
    }
}
// Writes TILES_BYTES bytes from TILES_BASE. The caller publishes them.
static void tiles_scene_build(void)
{
    static const unsigned long atlases[3]={TILES_ATLAS8,TILES_ATLAS16,TILES_ATLAS32};
    for(unsigned code=0;code<3;++code) {
        unsigned size=8U<<code;
        uint8_t *atlas=TILES_MEMORY(atlases[code]);
        for(unsigned design=0;design<TILES_DESIGNS;++design)
            for(unsigned y=0;y<size;++y) for(unsigned x=0;x<size;++x)
                *atlas++=(uint8_t)tiles_design_pixel(design,x,y,size);
    }
    tiles_write_map(TILES_MAP_FAR,32,16,tiles_far_entry);
    tiles_write_map(TILES_MAP_MAIN,128,32,tiles_main_entry);
    tiles_write_map(TILES_MAP_PANEL,128,16,tiles_panel_entry);
    uint8_t *banner=TILES_MEMORY(TILES_BANNER);
    for(unsigned y=0;y<48;++y) for(unsigned x=0;x<256;++x)
        *banner++=(x<3 || x>=253 || y<3 || y>=45) ? DEMO_WHITE
                 : (x/16+y/16)&1 ? DEMO_TRANSPARENT : (uint8_t)(DEMO_COOL_FIRST+x/4);
    uint8_t *sprite=TILES_MEMORY(TILES_SPRITES);
    for(unsigned s=0;s<TILES_SPRITE_COUNT;++s)
        for(unsigned y=0;y<32;++y) for(unsigned x=0;x<32;++x)
            *sprite++=(uint8_t)tiles_design_pixel(s&1 ? TILE_STAR : TILE_ARROW,x,y,32);
}
// Far mountains (32, opaque, wrapped), playfield (16, its map ends), a
// panel (8, wrapped on both axes, small window), a surface and sprites
// between them. Pose 3 moves every window partly off the screen.
static void tiles_scene_pose(unsigned pose,int step,gpu_layer layers[16],gpu_sprite sprites[64])
{
    static const uint16_t far_x[TILES_POSES]={0,300,1000,40000},far_y[TILES_POSES]={32,40,0,64};
    static const uint16_t main_x[TILES_POSES]={0,403,1248,1500},main_y[TILES_POSES]={32,20,5,32};
    static const uint16_t panel_x[TILES_POSES]={0,3,77,1021};
    int shift=pose==3 ? 1 : 0;
    for(unsigned l=0;l<16;++l) layers[l]=gpu_make_layer(0,0,0,0,0,0,0,0,0,0,0);
    for(unsigned s=0;s<64;++s) sprites[s]=gpu_make_sprite(0,0,0,0,0,0,0);
    layers[0]=gpu_make_tile_layer(TILES_MAP_FAR,TILES_ATLAS32,32,5,4,0,0,GPU_WIDTH,GPU_HEIGHT,
        (unsigned)(far_x[pose]+step)&65535,far_y[pose],GPU_LAYER_ENABLE|GPU_LAYER_WRAP_X);
    layers[4]=gpu_make_tile_layer(TILES_MAP_MAIN,TILES_ATLAS16,16,7,5,shift ? -40 : 0,shift ? 30 : 0,GPU_WIDTH,GPU_HEIGHT,
        (unsigned)(main_x[pose]+step*3)&65535,main_y[pose],GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
    layers[8]=gpu_make_layer(TILES_BANNER,256,256,48,shift ? 700 : 272,shift ? -20 : 60,256,48,0,0,
        GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
    layers[10]=gpu_make_tile_layer(TILES_MAP_PANEL,TILES_ATLAS8,8,7,4,shift ? -5 : 0,4,GPU_WIDTH,16,
        (unsigned)(panel_x[pose]+step*5)&65535,pose*9,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO|GPU_LAYER_WRAP_X|GPU_LAYER_WRAP_Y);
    for(unsigned s=0;s<TILES_SPRITE_COUNT;++s)
        sprites[s]=gpu_make_sprite(TILES_SPRITES+s*1024UL,(int)s*97+20+(int)pose*11,(int)(s%3)*110+90,32,32,
            s<4 ? 2 : 12,GPU_SPRITE_ENABLE|(((s+pose)&3)<<1)); // behind and in front of the playfield
}
#endif
