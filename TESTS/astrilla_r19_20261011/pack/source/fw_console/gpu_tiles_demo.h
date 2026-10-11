// L11 tile map diagnostic. U builds the scene in DDR and verifies every
// pose against the CPU reference; Y shows the next pose; W scrolls the
// scene, one descriptor update per LCD frame and no drawing command.
#include "gpu_tiles_scene.h"
static gpu_layer tiles_layers[16];
static gpu_sprite tiles_sprites[64];
static unsigned tiles_initialized,tiles_pose,tiles_animate,tiles_frames;
static int tiles_step,tiles_direction;
static uint64_t tiles_cycles,tiles_cpu_cycles;

static void tiles_clear_maxima(void)
{
    GPU[0x2c/4]=0;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}
static int tiles_show(unsigned pose,int step,int verify)
{
    tiles_scene_pose(pose,step,tiles_layers,tiles_sprites);
    if(!verify) return gpu_scene_submit(tiles_layers,tiles_sprites);
    unsigned expected=gpu_scene_reference_hash(tiles_layers,tiles_sprites);
    if(!gpu_scene_submit(tiles_layers,tiles_sprites) || !gpu_display_wait()) {printf("TILES FAIL COMMIT\r\n");return 0;}
    tiles_clear_maxima();
    unsigned frame=GPU[6],timeout=2000000;
    while((unsigned)(GPU[6]-frame)<3 && --timeout) {}
    unsigned actual=GPU[8],invalid=GPU[0x38/4],invalid_sprites=GPU[0x48/4],underflows=GPU[7];
    if(!timeout || actual!=expected || invalid || invalid_sprites || underflows || GPU[0x34/4]!=1) {
        printf("TILES FAIL pose=%u expected=%08x got=%08x invalid=%u invalid_sprites=%u underflows=%u max_cycles=%u\r\n",
            pose,expected,actual,invalid,invalid_sprites,underflows,(unsigned)GPU[0x2c/4]);
        return 0;
    }
    tiles_pose=pose;
    printf("TILES POSE %u hash=%08x max_cycles=%u underflows=%u\r\n",pose,actual,(unsigned)GPU[0x2c/4],underflows);
    return 1;
}
static void tiles_demo(void)
{
    tiles_initialized=tiles_animate=0;
    if(!gpu_tiles_supported()) {printf("TILES FAIL CAPABILITY\r\n");return;}
    if(GPU[0x28/4]!=16 || GPU[0x3c/4]!=64 || !gpu_display_wait()) {printf("TILES FAIL INIT\r\n");return;}
    // The palette is global: rebuild everything while scanout is disabled.
    GPU[2]=0;GPU[3]=1;
    if(!gpu_display_wait()) {printf("TILES FAIL DISABLE\r\n");return;}
    for(unsigned i=0;i<256;++i) GPU[0x100+i]=gpu_demo_palette_color(i);
    tiles_scene_build();
    gpu_publish_surface(TILES_BASE,TILES_BYTES);
    printf("TILES SCENE bytes=%u designs=%u\r\n",(unsigned)TILES_BYTES,TILES_DESIGNS);
    for(unsigned pose=0;pose<TILES_POSES;++pose) if(!tiles_show(pose,0,1)) return;
    if(!tiles_show(0,0,1)) return;
    tiles_initialized=1;
    printf("TILES READY poses=%u hash=%08x underflows=%u\r\n",TILES_POSES,(unsigned)GPU[8],(unsigned)GPU[7]);
}
static void tiles_next(void)
{
    if(!tiles_initialized) {printf("TILES FAIL run U first\r\n");return;}
    tiles_animate=0;
    if(tiles_show((tiles_pose+1)%TILES_POSES,0,1)) printf("TILES MOVED pose=%u\r\n",tiles_pose);
}
static void tiles_start(void)
{
    if(!tiles_initialized) {printf("TILES FAIL run U first\r\n");return;}
    tiles_step=0;tiles_direction=1;tiles_frames=0;tiles_cycles=tiles_cpu_cycles=0;
    if(!tiles_show(0,0,0) || !gpu_display_wait()) {printf("TILES FAIL COMMIT\r\n");return;}
    tiles_clear_maxima();
    tiles_animate=1;
    printf("TILES SCROLL started\r\n");
}
// The playfield map ends: scroll there and back. The far layer and the
// panel are wrapped and simply follow.
static void tiles_tick(void)
{
    unsigned begin=read_csr(NDS_MCYCLE);
    tiles_step+=tiles_direction;
    if(tiles_step==0 || tiles_step==416) tiles_direction=-tiles_direction;
    tiles_scene_pose(0,tiles_step,tiles_layers,tiles_sprites);
    tiles_cpu_cycles+=(unsigned)(read_csr(NDS_MCYCLE)-begin);
    if(!gpu_scene_submit(tiles_layers,tiles_sprites) || !gpu_display_wait()) {
        tiles_animate=0;printf("TILES FAIL COMMIT\r\n");return;
    }
    tiles_cycles+=(unsigned)(read_csr(NDS_MCYCLE)-begin);
    if(++tiles_frames==240) {
        unsigned average=(unsigned)(tiles_cycles/tiles_frames);
        printf("TILES BENCH frames=%u fps_x100=%u frame_avg=%u cpu_avg=%u gpu_commands=0 max_cycles=%u invalid=%u underflows=%u\r\n",
            tiles_frames,(unsigned)(80000000000ULL/average),average,(unsigned)(tiles_cpu_cycles/tiles_frames),
            (unsigned)GPU[0x2c/4],(unsigned)GPU[0x38/4],(unsigned)GPU[7]);
        tiles_frames=0;tiles_cycles=tiles_cpu_cycles=0;
    }
}
