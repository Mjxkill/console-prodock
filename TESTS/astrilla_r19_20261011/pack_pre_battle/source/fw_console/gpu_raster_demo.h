#include "gpu_raster_reference.h"
#include "gpu_rgb_overlay_scene.h"
static unsigned raster_advanced;
static unsigned raster_initialized,raster_animate,raster_front,raster_angle,raster_frames;
static unsigned raster_gpu_max,raster_frame_max;
static uint64_t raster_gpu_total,raster_frame_total;
static int raster_prepare(void)
{
    raster_initialized=raster_animate=0;
    if(raster_advanced && !gpu_perspective_supported())return 0;
    if(!gpu_blit_init() || !gpu_raster_supported() || !gpu_wait() || !gpu_display_wait())return 0;
    GPU[2]=0;GPU[3]=1;if(!gpu_display_wait())return 0;
    for(unsigned p=6;p<=8;++p) {
        memset((void *)GPU_PAGE_ADDR(p),0xa5,800*480*2+64);
        gpu_publish_surface(GPU_PAGE_ADDR(p),800*480*2+64);
    }
    uint16_t *source=(uint16_t *)GPU_PAGE_ADDR(15);
    for(unsigned y=0;y<64;++y)for(unsigned x=0;x<64;++x)source[(y+19)*800+x+17]=raster_asset(x,y);
    gpu_publish_surface(GPU_PAGE_ADDR(15),800*480*2);
    gpu_command c=gpu_make_texture(15,17,19,64,64,GPU_TEX_CLAMP,GPU_TEX_CLAMP);gpu_submit(&c);
    if(!gpu_wait())return 0;
    layers_initialized=sprites_initialized=demo3d_initialized=tiles_initialized=affine_initialized=0;
    if(raster_advanced) {
        for(unsigned i=0;i<256;++i)GPU[0x100+i]=overlay_palette(i);
        uint8_t *hud=(uint8_t *)GPU_PAGE_ADDR(9),*sp=(uint8_t *)GPU_PAGE_ADDR(10),*atlas=(uint8_t *)GPU_PAGE_ADDR(12);
        uint16_t *map=(uint16_t *)GPU_PAGE_ADDR(11);
        memset(hud,0,800*64);
        for(unsigned y=0;y<40;++y)for(unsigned x=0;x<768;++x)hud[y*800+x]=(uint8_t)overlay_text(x,y,gpu_font);
        for(unsigned y=0;y<32;++y)for(unsigned x=0;x<32;++x)sp[y*32+x]=(uint8_t)overlay_sprite(x,y);
        for(unsigned i=0;i<256;++i)map[i]=i&1;
        for(unsigned t=0;t<2;++t)for(unsigned y=0;y<8;++y)for(unsigned x=0;x<8;++x)atlas[t*64+y*8+x]=(uint8_t)overlay_tile(t,x,y);
        gpu_publish_surface(GPU_PAGE_ADDR(9),800*64);gpu_publish_surface(GPU_PAGE_ADDR(10),1024);
        gpu_publish_surface(GPU_PAGE_ADDR(11),512);gpu_publish_surface(GPU_PAGE_ADDR(12),128);
    }
    raster_front=7;raster_angle=0;raster_initialized=1;return 1;
}
static int raster_render(unsigned angle,unsigned reverse,int verify)
{
    unsigned page=raster_front==6?7:6,begin=read_csr(NDS_MCYCLE);
    unsigned before=gpu_completed();
    if(!raster_scene_mode(page,angle,reverse,gpu_submit,raster_advanced)){printf("RASTER FAIL PLANES\r\n");return 0;}
    if(!gpu_wait() || gpu_raster_rejected()){printf("RASTER FAIL FENCE rejected=%u\r\n",gpu_raster_rejected());return 0;}
    unsigned gpu=read_csr(NDS_MCYCLE)-begin;
    unsigned sum=0;
    if(verify) {
        raster_reference_color=(uint16_t *)GPU_PAGE_ADDR(3);
        raster_reference_depth=(uint16_t *)GPU_PAGE_ADDR(4);
        raster_scene_mode(page,angle,reverse,raster_reference,raster_advanced);
        unsigned errors=0;
        for(unsigned kind=0;kind<2;++kind) {
            unsigned p=kind?8:page;
            ae350_dcache_invalidate_range(GPU_PAGE_ADDR(p),800*480*2+64);
            const uint16_t *actual=(const uint16_t *)GPU_PAGE_ADDR(p);
            const uint16_t *expected=kind?raster_reference_depth:raster_reference_color;
            for(unsigned i=0;i<800*480+32;++i) {
                unsigned want=i<800*480?expected[i]:0xa5a5;
                if(actual[i]!=want) {
                    if(errors<4)printf("RASTER FAIL kind=%u pixel=%u expected=%04x got=%04x\r\n",kind,i,want,actual[i]);
                    ++errors;
                }
            }
        }
        if(errors)return 0;
        const uint32_t *pixels=(const uint32_t *)GPU_PAGE_ADDR(page);
        for(unsigned i=0;i<800*480/2;++i)sum+=pixels[i];
    }
    if(raster_advanced)overlay_descriptors(angle,scene_layers,scene_sprites);
    if(!(raster_advanced ? gpu_rgb565_scene_submit(page,scene_layers,scene_sprites) && gpu_display_wait():gpu_rgb565_present(page))){printf("RASTER FAIL COMMIT\r\n");return 0;}
    raster_front=page;
    if(verify) {
        unsigned frame=GPU[6],timeout=3000000;
        while((unsigned)(GPU[6]-frame)<2 && --timeout){}
        if(!timeout || GPU[8]!=sum || GPU[7]){printf("RASTER FAIL DISPLAY expected=%08x got=%08x underflows=%u\r\n",sum,(unsigned)GPU[8],(unsigned)GPU[7]);return 0;}
        if(raster_advanced) {
            unsigned lcd_sum=0;
            for(unsigned y=0;y<480;++y)for(unsigned x=0;x<800;++x) {
                unsigned color=raster_reference_color[y*800+x];
                int ix=overlay_sample(x,y,angle,gpu_font);
                lcd_sum+=ix>=0 ? overlay_palette((unsigned)ix):
                    (((color>>11)*2+(color>>15))<<12)|(((color>>5)&63)<<6)|((color&31)*2+((color>>4)&1));
            }
            // LCD checksum is published at VS after the visible image.
            frame=GPU[6];timeout=3000000;
            while((unsigned)(GPU[6]-frame)<2 && --timeout){}
            if(!timeout || GPU[0x60/4]!=lcd_sum){printf("RASTER FAIL OVERLAY expected=%08x got=%08x\r\n",lcd_sum,(unsigned)GPU[0x60/4]);return 0;}
            printf("RASTER OVERLAY sum=%08x line_cycles=%u underflows=%u\r\n",lcd_sum,(unsigned)GPU[0x64/4],(unsigned)GPU[7]);
        }
        printf("RASTER POSE angle=%u reverse=%u sum=%08x commands=%u gpu_cycles=%u underflows=%u\r\n",angle,reverse,sum,(gpu_completed()-before)&65535,gpu,(unsigned)GPU[7]);
    } else {
        unsigned frame=read_csr(NDS_MCYCLE)-begin;
        raster_gpu_total+=gpu;raster_frame_total+=frame;++raster_frames;
        if(gpu>raster_gpu_max)raster_gpu_max=gpu;
        if(frame>raster_frame_max)raster_frame_max=frame;
    }
    return 1;
}
static void raster_test(unsigned advanced)
{
    raster_advanced=advanced;
    if(!raster_prepare()){printf("RASTER FAIL INIT\r\n");return;}
    for(unsigned i=0;i<4;++i)if(!raster_render(i*37,i&1,1))return;
    printf("RASTER READY poses=4 rgb565=1 alpha=1 textures=1 depth=1 perspective=%u overlay=%u underflows=%u\r\n",raster_advanced,raster_advanced,(unsigned)GPU[7]);
}
static void raster_start(unsigned advanced)
{
    if(raster_advanced!=advanced)raster_initialized=0;
    raster_advanced=advanced;
    if(!raster_initialized && !raster_prepare()){printf("RASTER FAIL INIT\r\n");return;}
    raster_frames=raster_gpu_max=raster_frame_max=0;raster_gpu_total=raster_frame_total=0;
    raster_animate=1;printf("RASTER ANIMATION started\r\n");
}
static void raster_tick(void)
{
    raster_angle=(raster_angle+1)&GPU_RASTER_PHASE_MASK;
    if(!raster_render(raster_angle,0,0)){raster_animate=0;return;}
    if(raster_frames==120) {
        unsigned avg=(unsigned)(raster_frame_total/raster_frames);
        printf("RASTER BENCH frames=%u gpu_avg=%u gpu_max=%u frame_avg=%u frame_max=%u fps_x100=%u underflows=%u\r\n",
            raster_frames,(unsigned)(raster_gpu_total/raster_frames),raster_gpu_max,avg,raster_frame_max,
            (unsigned)(80000000000ULL/avg),(unsigned)GPU[7]);
        raster_frames=raster_gpu_max=raster_frame_max=0;raster_gpu_total=raster_frame_total=0;
    }
}
