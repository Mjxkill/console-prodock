#include "racer_scene.h"
static racer_state race_state;
static unsigned race_running,race_keys,race_last_input,race_last_tick,race_accumulator;
static unsigned race_front,race_frames,race_gpu_max;
static void racer_reset_bench(void)
{race_frames=0;race_gpu_max=0;}
static uint64_t race_cycles,race_gpu_cycles,race_cpu_cycles;

static void racer_reference_zoom(const gpu_command *c,uint8_t *dst)
{
    int x=(int16_t)(c->words[1]>>16),y=(int16_t)c->words[1];
    int w=(int16_t)(c->words[2]>>16),h=(int16_t)c->words[2];
    int sx=(int16_t)(c->words[3]>>16),sy=(int16_t)c->words[3];
    unsigned sw=c->words[4]>>16,sh=c->words[4]&65535;
    const uint8_t *src=(const uint8_t *)GPU_PAGE_ADDR((c->words[0]>>16)&15);
    for(int yy=max_int(0,y);yy<min_int(480,y+h);++yy)
        for(int xx=max_int(0,x);xx<min_int(800,x+w);++xx) {
            unsigned u=((uint64_t)(xx-x)*c->words[5])>>16,v=((uint64_t)(yy-y)*c->words[6])>>16;
            if(u<sw && v<sh){unsigned p=src[(sy+v)*800+sx+u];if(p)dst[yy*800+xx]=p;}
        }
}
static int racer_render(int verify,unsigned pose)
{
    unsigned page=race_front==6?7:6;
    unsigned begin=read_csr(NDS_MCYCLE);
    racer_build(&race_state,page);
    unsigned prepared=read_csr(NDS_MCYCLE);
    if(race_overflow){printf("RACE FAIL COMMAND OVERFLOW\r\n");return 0;}
    for(unsigned i=0;i<race_count;++i)gpu_submit(&race_commands[i]);
    if(!gpu_wait()){printf("RACE FAIL FENCE\r\n");return 0;}
    unsigned drawn=read_csr(NDS_MCYCLE);
    if(!verify){
        race_cpu_cycles+=prepared-begin;race_gpu_cycles+=drawn-prepared;
        if(drawn-prepared>race_gpu_max)race_gpu_max=drawn-prepared;
    }
    if(verify) {
        uint8_t *ref=(uint8_t *)GPU_PAGE_ADDR(4),*dst=(uint8_t *)GPU_PAGE_ADDR(page);
        memset(ref,0xa5,800*480);
        for(unsigned i=0;i<race_count;++i){
            const gpu_command *c=&race_commands[i];unsigned op=c->words[0]>>24;
            if(op==GPU_ZOOM)racer_reference_zoom(c,ref);
            else if(op==GPU_TRIANGLE)reference_triangle(c,ref);
            else reference_draw(c,ref);
        }
        ae350_dcache_invalidate_range(GPU_PAGE_ADDR(page),800*480+64);
        unsigned errors=0;
        for(unsigned i=0;i<800*480+64;++i)if(dst[i]!=(i<800*480?ref[i]:0xa5)){
            if(errors<4)printf("RACE FAIL byte=%u expected=%u got=%u\r\n",i,i<800*480?ref[i]:0xa5,dst[i]);++errors;
        }
        if(errors)return 0;
    }
    memset(scene_layers,0,sizeof(scene_layers));
    scene_layers[0]=gpu_make_layer(GPU_PAGE_ADDR(page),800,800,480,0,0,800,480,0,0,GPU_LAYER_ENABLE);
    unsigned hash=verify?gpu_layers_reference_hash(scene_layers):0;
    if(!gpu_layers_submit(scene_layers) || !gpu_display_wait()){printf("RACE FAIL COMMIT\r\n");return 0;}
    race_front=page;
    if(verify){
        unsigned frame=GPU[6],timeout=2000000;
        while((unsigned)(GPU[6]-frame)<2 && --timeout){}
        if(!timeout || GPU[8]!=hash || GPU[7]){printf("RACE FAIL HASH expected=%08x got=%08x underflows=%u\r\n",hash,(unsigned)GPU[8],(unsigned)GPU[7]);return 0;}
        printf("RACE POSE %u hash=%08x commands=%u underflows=%u\r\n",pose,hash,race_count,(unsigned)GPU[7]);
    }
    return 1;
}
static int racer_prepare(void)
{
    race_running=race_keys=demo3d_animate=demo3d_initialized=layers_initialized=sprites_initialized=0;
    if(!gpu_blit_init() || !gpu_wait() || !gpu_display_wait())return 0;
    GPU[2]=0;GPU[3]=1;if(!gpu_display_wait())return 0;
    for(unsigned i=0;i<256;++i)GPU[0x100+i]=racer_palette(i);
    racer_make_atlas((uint8_t *)GPU_PAGE_ADDR(RACE_ATLAS));
    gpu_publish_surface(GPU_PAGE_ADDR(RACE_ATLAS),800*480);
    for(unsigned page=6;page<=7;++page){
        memset((void *)GPU_PAGE_ADDR(page),0xa5,800*480+64);
        gpu_publish_surface(GPU_PAGE_ADDR(page),800*480+64);
    }
    // Cache the static panorama once; scrolling uses the existing DDR COPY.
    memset((void *)GPU_PAGE_ADDR(9),0,800*480);
    gpu_publish_surface(GPU_PAGE_ADDR(9),800*480);
    racer_background(9);
    for(unsigned i=0;i<race_count;++i)gpu_submit(&race_commands[i]);
    if(!gpu_wait())return 0;
    ae350_dcache_invalidate_range(GPU_PAGE_ADDR(9),800*480);
    racer_reset(&race_state);race_front=7;race_frames=0;race_cycles=race_cpu_cycles=race_gpu_cycles=0;race_accumulator=0;
    return 1;
}
static void racer_pose(racer_state *s,unsigned pose)
{
    racer_reset(s);
    if(pose){s->phase=1;s->distance=(int)pose*1700;s->speed=350;s->time_ticks=2200;
        s->traffic[0]=180;s->traffic[1]=390;s->traffic[2]=670;s->x=pose==2?-28:45;
        if(pose==3)s->crash_ticks=32;
    }
}
static void racer_test(void)
{
    if(!racer_prepare()){printf("RACE FAIL INIT\r\n");return;}
    for(unsigned i=0;i<4;++i){racer_pose(&race_state,i);if(!racer_render(1,i))return;}
    racer_reset(&race_state);if(!racer_render(0,0))return;
    printf("RACE VERIFIED poses=4 underflows=%u\r\n",(unsigned)GPU[7]);
}
static void racer_start(void)
{
    if(!racer_prepare() || !racer_render(0,0)){printf("RACE FAIL INIT\r\n");return;}
    racer_reset_bench();
    race_last_tick=race_last_input=read_csr(NDS_MCYCLE);race_running=1;
    race_cycles=race_cpu_cycles=race_gpu_cycles=0;
    printf("RACE READY controls=USB_CDC track_m=6000 mode=%s\r\n",race_original?"original":"cached");
}
static void racer_input(unsigned keys)
{
    race_keys=keys&31;race_last_input=read_csr(NDS_MCYCLE);
}
static void racer_status(void)
{
    printf("RACE STATUS running=%u phase=%d speed=%d distance=%d x=%d hits=%d keys=%u underflows=%u\r\n",
        race_running,race_state.phase,race_state.speed,race_state.distance,race_state.x,race_state.hits,race_keys,(unsigned)GPU[7]);
}
static void racer_tick(void)
{
    unsigned begin=read_csr(NDS_MCYCLE),elapsed=begin-race_last_tick;race_last_tick=begin;
    if((unsigned)(begin-race_last_input)>280000000U)race_keys=0; // 350 ms input watchdog
    if(elapsed>160000000U)elapsed=160000000U;
    race_accumulator+=elapsed;
    while(race_accumulator>=16000000U){racer_step(&race_state,race_keys);race_accumulator-=16000000U;}
    if(!racer_render(0,0)){race_running=0;return;}
    race_cycles+=(unsigned)(read_csr(NDS_MCYCLE)-begin);
    if(++race_frames==120){
        unsigned avg=(unsigned)(race_cycles/race_frames);
        printf("RACE BENCH frames=%u fps_x100=%u frame_avg=%u cpu_avg=%u gpu_avg=%u gpu_max=%u commands=%u underflows=%u\r\n",
            race_frames,(unsigned)(80000000000ULL/avg),avg,(unsigned)(race_cpu_cycles/race_frames),(unsigned)(race_gpu_cycles/race_frames),race_gpu_max,race_count,(unsigned)GPU[7]);
        racer_reset_bench();race_cycles=race_cpu_cycles=race_gpu_cycles=0;
    }
}

// Identical deterministic geometry sequence in both modes. Includes vblank,
// with CPU and submission+GPU costs also measured separately. No host input.
static void racer_benchmark(void)
{
    race_running=0;
    for(unsigned mode=0;mode<2;++mode) {
        race_original=mode==0;
        if(!racer_prepare()){printf("RACE FAIL PERF INIT\r\n");return;}
        racer_reset_bench();race_cycles=race_cpu_cycles=race_gpu_cycles=0;
        for(unsigned frame=0;frame<240;++frame) {
            racer_pose(&race_state,1);
            race_state.distance=(int)frame*50; // whole curvature period
            race_state.x=(frame/60)%2 ? -28:45;
            for(int i=0;i<RACE_OBJECTS;++i)race_state.traffic[i]=80+(i*487+(int)frame*23)%2400;
            unsigned before=read_csr(NDS_MCYCLE);
            if(!racer_render(0,0))return;
            race_cycles+=(unsigned)(read_csr(NDS_MCYCLE)-before);
        }
        unsigned avg=(unsigned)(race_cycles/240);
        printf("RACE PERF mode=%s frames=240 cpu_avg=%u gpu_avg=%u gpu_max=%u frame_avg=%u fps_x100=%u underflows=%u\r\n",
            race_original?"original":"cached",(unsigned)(race_cpu_cycles/240),(unsigned)(race_gpu_cycles/240),race_gpu_max,
            avg,(unsigned)(80000000000ULL/avg),(unsigned)GPU[7]);
    }
    race_original=1;racer_start();
}
