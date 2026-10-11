#include "gpu_v1_scene.h"
#include "gpu_v1_expected.h"
static unsigned v1_initialized,v1_animate,v1_front,v1_phase,v1_scene_id,v1_frames;
static unsigned v1_gpu_max,v1_frame_max,v1_present_tick;
static uint64_t v1_gpu_total,v1_frame_total;
static uint32_t v1_hash(uint32_t address,unsigned count)
{
    ae350_dcache_invalidate_range(address,count);
    const uint8_t *p=(const uint8_t *)(uintptr_t)address;uint32_t hash=2166136261U;
    while(count--)hash=(hash^*p++)*16777619U;
    return hash;
}
// Native-size benchmarking touches bytes used as padding in the half-size mode.
// Restore those bytes once after that benchmark; later checks only read them.
static int v1_guards(unsigned restore)
{
    for(unsigned page=0;page<3;++page) {
        uint32_t base=GPU_PAGE_ADDR(page);ae350_dcache_invalidate_range(base,V1_PITCH*240+64);
        uint32_t *p=(uint32_t *)(uintptr_t)base;
        for(unsigned y=0;y<=240;++y) {
            unsigned start=y==240 ? V1_PITCH*240/4:(y*V1_PITCH+800)/4;
            unsigned words=y==240?16:8;
            for(unsigned i=0;i<words;++i) {
                if(restore)p[start+i]=0xa5a5a5a5U;
                else if(p[start+i]!=0xa5a5a5a5U){printf("V1 FAIL GUARD page=%u word=%u\r\n",page,start+i);return 0;}
            }
        }
        if(restore)gpu_publish_surface(base,V1_PITCH*240+64);
    }
    return 1;
}
static int v1_prepare(void)
{
    v1_initialized=v1_animate=0;
    if(!gpu_v1_supported() || !gpu_blit_init() || !gpu_wait() || !gpu_display_wait())return 0;
    GPU[2]=0;GPU[3]=1;if(!gpu_display_wait())return 0;
    for(unsigned page=0;page<3;++page){memset((void *)GPU_PAGE_ADDR(page),0xa5,GPU_PAGE_BYTES);gpu_publish_surface(GPU_PAGE_ADDR(page),GPU_PAGE_BYTES);}
    v1_assets((uint16_t *)V1_TEXTURE_BASE,gpu_font);gpu_publish_surface(V1_TEXTURE_BASE,GPU_PAGE_BYTES);
    gpu_v1_context c;gpu_v1_init(&c,gpu_submit);gpu_v1_invalidate(&c);if(!gpu_wait())return 0;
    memset(scene_layers,0,sizeof(scene_layers));memset(scene_sprites,0,sizeof(scene_sprites));
    uint8_t *hud=(uint8_t *)GPU_PAGE_ADDR(9);
    for(unsigned y=0;y<20;++y)for(unsigned x=0;x<800;++x)hud[y*800+x]=(uint8_t)v1_hud_pixel(x,y,gpu_font);
    gpu_publish_surface(GPU_PAGE_ADDR(9),800*20);
    scene_layers[15]=gpu_make_layer(GPU_PAGE_ADDR(9),800,800,20,0,0,800,20,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
    GPU[0x101]=(40U<<6)|63U;GPU[0x102]=(2U<<12)|(4U<<6)|8U;GPU[0x1ff]=0x3ffff;
    layers_initialized=sprites_initialized=demo3d_initialized=tiles_initialized=affine_initialized=raster_initialized=0;
    v1_front=1;v1_present_tick=0;v1_phase=0;v1_scene_id=0;v1_initialized=1;GPU[0x2c/4]=0;return 1;
}
static int v1_render(unsigned scene,unsigned phase,int verify)
{
    unsigned page=v1_front^1U,begin=read_csr(NDS_MCYCLE),before=gpu_completed();
    gpu_v1_context c;gpu_v1_init(&c,gpu_submit);
    if(!v1_scene(&c,scene,phase,page) || !gpu_wait() || gpu_v1_rejected() || gpu_errors()) {
        printf("V1 FAIL RENDER rejected=%u\r\n",gpu_v1_rejected());return 0;
    }
    unsigned gpu_cycles=read_csr(NDS_MCYCLE)-begin;
    unsigned color=0,depth=0;
    if(verify>=0) {
        color=v1_hash(GPU_PAGE_ADDR(page),V1_PITCH*240+64);depth=v1_hash(GPU_PAGE_ADDR(2),V1_PITCH*240+64);
        if(color!=v1_expected[scene][verify][0] || depth!=v1_expected[scene][verify][1]) {
            printf("V1 FAIL HASH scene=%u phase=%u color=%08x/%08x depth=%08x/%08x\r\n",scene,phase,color,(unsigned)v1_expected[scene][verify][0],depth,(unsigned)v1_expected[scene][verify][1]);return 0;
        }
    }
    if(!gpu_rgb565_surface_submit(&c.target,1,scene_layers,scene_sprites) || !gpu_display_wait()){printf("V1 FAIL COMMIT\r\n");return 0;}
    v1_front=page;
    unsigned presented=read_csr(NDS_MCYCLE);
    unsigned present_interval=presented-(v1_present_tick?v1_present_tick:begin);
    v1_present_tick=presented;
    if(verify>=0) {
        unsigned frame=GPU[6],timeout=4000000;
        while((unsigned)(GPU[6]-frame)<3 && --timeout){}
        unsigned lcd=GPU[0x60/4];
        if(!timeout || lcd!=v1_expected[scene][verify][2] || GPU[7]){printf("V1 FAIL LCD scene=%u actual=%08x expected=%08x underflows=%u\r\n",scene,lcd,(unsigned)v1_expected[scene][verify][2],(unsigned)GPU[7]);return 0;}
        printf("V1 POSE scene=%u phase=%u color=%08x depth=%08x lcd=%08x commands=%u gpu_cycles=%u underflows=%u\r\n",scene,phase,color,depth,lcd,(gpu_completed()-before)&65535,gpu_cycles,(unsigned)GPU[7]);
    } else {
        unsigned frame_cycles=present_interval;
        v1_gpu_total+=gpu_cycles;v1_frame_total+=frame_cycles;++v1_frames;
        if(gpu_cycles>v1_gpu_max)v1_gpu_max=gpu_cycles;
        if(frame_cycles>v1_frame_max)v1_frame_max=frame_cycles;
        if(GPU[7]){printf("V1 FAIL UNDERFLOW %u\r\n",(unsigned)GPU[7]);return 0;}
    }
    return 1;
}
static int v1_scale_benchmark(void)
{
    for(unsigned scale=1;scale<=2;++scale) {
        gpu_v1_context c;gpu_v1_init(&c,gpu_submit);
        gpu_target t={GPU_PAGE_ADDR(v1_front^1U),GPU_PAGE_ADDR(2),400*scale,240*scale,832*scale,832*scale};
        gpu_texture_level texture=v1_level(0);
        gpu_material material={7,256,0,256,256,256,0,0,0};
        gpu_v1_invalidate(&c);if(!gpu_wait())return 0;
        unsigned begin=read_csr(NDS_MCYCLE);
        if(!gpu_v1_target(&c,&t))return 0;
        gpu_v1_clear(&c,3,0,65535,0,0,t.width,t.height);
        if(!gpu_v1_texture(&c,&texture) || !gpu_v1_material(&c,&material) ||
           !v1_rect_texture(&c,0,0,t.width,t.height,0,0,512,512,10000) || !gpu_wait())return 0;
        unsigned cycles=read_csr(NDS_MCYCLE)-begin;
        printf("V1 SCALE width=%u height=%u pixels=%u cycles=%u underflows=%u\r\n",t.width,t.height,(unsigned)t.width*t.height,cycles,(unsigned)GPU[7]);
        if(gpu_v1_rejected() || GPU[7])return 0;
    }
    return 1;
}
// Rebind Z below the color page after a target whose Z was above it. This
// exposes stale range bases from wrongly absorbed, independently enabled DSP
// registers. Also exercise a cross-page copy with unequal halfword alignment.
static int v1_memory_test(void)
{
    for(unsigned page=4;page<=6;++page) {
        uint16_t *p=(uint16_t *)GPU_PAGE_ADDR(page);
        for(unsigned i=0;i<416;++i)p[i]=page==4 && i/48<8 && i%48<32 ? (uint16_t)(0x1200+i):0xa5a5;
        gpu_publish_surface(GPU_PAGE_ADDR(page),832);
    }
    gpu_v1_context c;gpu_v1_init(&c,gpu_submit);
    gpu_target t={GPU_PAGE_ADDR(5),GPU_PAGE_ADDR(6),32,8,96,96};
    gpu_target src={GPU_PAGE_ADDR(4),GPU_PAGE_ADDR(6),32,8,96,96};
    if(!gpu_v1_target(&c,&t) || !gpu_wait())return 0;
    t.depth=GPU_PAGE_ADDR(4);
    if(!gpu_v1_target(&c,&t) || !gpu_v1_clear(&c,1,0xf800,0,0,0,32,8) ||
       !gpu_v1_copy(&c,&src,2,1,3,2,20,3) ||
       !gpu_v1_clear(&c,2,0,0x1234,1,6,7,1) || !gpu_wait() || gpu_v1_rejected())return 0;
    for(unsigned page=4;page<=6;++page) {
        ae350_dcache_invalidate_range(GPU_PAGE_ADDR(page),832);
        const uint16_t *p=(const uint16_t *)GPU_PAGE_ADDR(page);
        for(unsigned i=0;i<416;++i) {
            unsigned y=i/48,x=i%48,expected=0xa5a5;
            if(y<8 && x<32) {
                if(page==4)expected=y==6 && x>=1 && x<8 ? 0x1234:0x1200+i;
                if(page==5)expected=y>=2 && y<5 && x>=3 && x<23 ? 0x1200+(y-1)*48+x-1:0xf800;
            }
            if(p[i]!=expected){printf("V1 FAIL MEMORY page=%u word=%u actual=%x expected=%x\r\n",page,i,(unsigned)p[i],expected);return 0;}
        }
    }
    printf("V1 MEMORY PASS rebind_z=1 copy_between_pages=1 guards=1\r\n");return 1;
}
static void v1_test(void)
{
    if(!v1_prepare()){printf("V1 FAIL INIT\r\n");return;}
    if(!v1_memory_test()){printf("V1 FAIL MEMORY TEST\r\n");return;}
    for(unsigned scene=0;scene<3;++scene)for(unsigned pose=0;pose<4;++pose)
        if(!v1_render(scene,v1_phases[pose],(int)pose))return;
    if(!v1_scale_benchmark() || !v1_guards(1)){printf("V1 FAIL SCALE\r\n");return;}
    printf("V1 READY scenes=3 poses=12 underflows=%u\r\n",(unsigned)GPU[7]);
}
static void v1_start(void)
{
    if(!v1_initialized && !v1_prepare()){printf("V1 FAIL INIT\r\n");return;}
    v1_present_tick=0;v1_frames=v1_gpu_max=v1_frame_max=0;v1_gpu_total=v1_frame_total=0;
    v1_animate=1;printf("V1 ANIMATION started\r\n");
}
static void v1_tick(void)
{
    if(!v1_render(v1_scene_id,++v1_phase,-1)){v1_animate=0;return;}
    if(v1_frames==120) {
        if(!v1_guards(0)){v1_animate=0;return;}
        unsigned avg=(unsigned)(v1_frame_total/v1_frames);
        volatile uint32_t *blt=(volatile uint32_t *)0xe9001000UL;
        printf("V1 BENCH scene=%u frames=%u gpu_avg=%u gpu_max=%u frame_avg=%u frame_max=%u fps_x100=%u hits=%u misses=%u line=%u underflows=%u rejected=%u\r\n",
            v1_scene_id,v1_frames,(unsigned)(v1_gpu_total/v1_frames),v1_gpu_max,avg,v1_frame_max,
            (unsigned)(80000000000ULL/avg),(unsigned)blt[0x40/4],(unsigned)blt[0x44/4],(unsigned)GPU[0x64/4],(unsigned)GPU[7],gpu_v1_rejected());
        v1_frames=v1_gpu_max=v1_frame_max=0;v1_gpu_total=v1_frame_total=0;v1_scene_id=(v1_scene_id+1)%3;
    }
}
