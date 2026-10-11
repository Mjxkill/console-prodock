#include "gpu_3d_scene.h"
static unsigned demo3d_initialized,demo3d_angle,demo3d_front,demo3d_animate;
static unsigned demo3d_frames;
static uint64_t demo3d_cpu_total,demo3d_gpu_total,demo3d_frame_total;
static unsigned demo3d_cpu_max,demo3d_gpu_max,demo3d_frame_max;
static const unsigned demo3d_poses[4]={16,52,96,168};
static unsigned demo3d_pose;

// Independent CPU coverage reference: direct 64-bit half-plane tests, no
// scanline stepping or hardware span generation. Handles full int16 inputs.
static void reference_triangle(const gpu_command *cmd,uint8_t *dst)
{
    int x[3],y[3];
    for(unsigned i=0;i<3;++i){x[i]=(int16_t)(cmd->words[1+i]>>16);y[i]=(int16_t)cmd->words[1+i];}
    int64_t area=(int64_t)(x[1]-x[0])*(y[2]-y[0])-(int64_t)(y[1]-y[0])*(x[2]-x[0]);
    if(!area)return;
    if(area<0){int t=x[1];x[1]=x[2];x[2]=t;t=y[1];y[1]=y[2];y[2]=t;}
    int left=max_int(0,min_int(x[0],min_int(x[1],x[2]))),right=min_int(799,max_int(x[0],max_int(x[1],x[2])));
    int top=max_int(0,min_int(y[0],min_int(y[1],y[2]))),bottom=min_int(479,max_int(y[0],max_int(y[1],y[2])));
    for(int yy=top;yy<=bottom;++yy) for(int xx=left;xx<=right;++xx) {
        int covered=1;
        for(unsigned i=0;i<3;++i) {
            unsigned j=(i+1)%3;int dx=x[j]-x[i],dy=y[j]-y[i];
            int64_t e=(int64_t)dx*(2*yy+1-2*y[i])-(int64_t)dy*(2*xx+1-2*x[i]);
            if(e<0 || (!e && !(dy<0 || (!dy && dx>0)))) {covered=0;break;}
        }
        if(covered)dst[yy*800+xx]=(cmd->words[0]>>8)&255;
    }
}
static void demo3d_layers(unsigned page)
{
    memset(scene_layers,0,sizeof(scene_layers));
    scene_layers[0]=gpu_make_layer(GPU_PAGE_ADDR(page),800,800,480,0,0,800,480,0,0,GPU_LAYER_ENABLE);
    scene_layers[15]=gpu_make_layer(GPU_PAGE_ADDR(5),800,800,480,0,0,800,480,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
}
static int demo3d_render(unsigned angle,int close_up,int verify)
{
    const unsigned bytes=800*480,page=demo3d_front==6 ? 7:6;
    unsigned begin=read_csr(NDS_MCYCLE);
    scene3d_build(page,angle,close_up);
    unsigned prepared=read_csr(NDS_MCYCLE),before=gpu_completed();
    for(unsigned i=0;i<scene3d_count;++i)gpu_submit(&scene3d_commands[i]);
    if(!gpu_wait()) {printf("THREED FAIL FENCE\r\n");return 0;}
    unsigned drawn=read_csr(NDS_MCYCLE),cpu=prepared-begin,gpu=drawn-prepared;
    if(verify) {
        uint8_t *reference=(uint8_t *)GPU_PAGE_ADDR(4),*target=(uint8_t *)GPU_PAGE_ADDR(page);
        for(unsigned i=0;i<scene3d_count;++i) {
            if(scene3d_commands[i].words[0]>>24==GPU_TRIANGLE)reference_triangle(&scene3d_commands[i],reference);
            else reference_draw(&scene3d_commands[i],reference);
        }
        ae350_dcache_invalidate_range(GPU_PAGE_ADDR(page),bytes+64);
        unsigned errors=0;
        for(unsigned i=0;i<bytes+64;++i) {
            unsigned expected=i<bytes ? reference[i]:0xa5;
            if(target[i]!=expected) {
                if(errors<4)printf("THREED FAIL byte=%u expected=%02x got=%02x\r\n",i,expected,target[i]);
                ++errors;
            }
        }
        if(errors)return 0;
    }
    demo3d_layers(page);
    unsigned hash=verify ? gpu_layers_reference_hash(scene_layers):0;
    if(!gpu_layers_submit(scene_layers) || !gpu_display_wait()) {printf("THREED FAIL COMMIT\r\n");return 0;}
    demo3d_front=page;
    unsigned elapsed=read_csr(NDS_MCYCLE)-begin;
    if(verify) {
        unsigned frame=GPU[6],timeout=2000000;
        while((unsigned)(GPU[6]-frame)<2 && --timeout) {}
        if(!timeout || GPU[8]!=hash || GPU[7]) {printf("THREED FAIL HASH expected=%08x got=%08x underflows=%u\r\n",hash,(unsigned)GPU[8],(unsigned)GPU[7]);return 0;}
        printf("THREED POSE %u hash=%08x commands=%u triangles=%u clipped=%u cpu_cycles=%u gpu_cycles=%u underflows=%u\r\n",
            demo3d_pose,hash,(gpu_completed()-before)&65535,scene3d_triangles,scene3d_clipped,cpu,gpu,(unsigned)GPU[7]);
    } else {
        ++demo3d_frames;demo3d_cpu_total+=cpu;demo3d_gpu_total+=gpu;demo3d_frame_total+=elapsed;
        if(cpu>demo3d_cpu_max)demo3d_cpu_max=cpu;
        if(gpu>demo3d_gpu_max)demo3d_gpu_max=gpu;
        if(elapsed>demo3d_frame_max)demo3d_frame_max=elapsed;
    }
    return 1;
}
static int demo3d_prepare(void)
{
    demo3d_animate=demo3d_initialized=0;
    if(!gpu_blit_init() || !gpu_wait() || !gpu_display_wait())return 0;
    GPU[2]=0;GPU[3]=1;if(!gpu_display_wait())return 0;
    for(unsigned i=0;i<256;++i)GPU[0x100+i]=gpu_demo_palette_color(i);
    for(unsigned page=5;page<=7;++page) {
        memset((void *)GPU_PAGE_ADDR(page),page==5 ? 0:0xa5,800*480+64);
        gpu_publish_surface(GPU_PAGE_ADDR(page),800*480+64);
    }
    gpu_text(5,24,18,DEMO_WHITE,DEMO_BACKGROUND,2,"G5 - MEGA PRO 3D");
    gpu_text(5,24,56,DEMO_CYAN,DEMO_BACKGROUND,1,"CPU 800 MHz / DDR3 / TRIANGLES GPU");
    gpu_text(5,150,424,DEMO_CYAN,DEMO_BACKGROUND,2,"FIL DE FER");
    gpu_text(5,512,424,DEMO_YELLOW,DEMO_BACKGROUND,2,"SOLIDE");
    gpu_text(5,24,460,DEMO_WHITE,DEMO_BACKGROUND,1,"A : ANIMATION   X : PAUSE   J : POSE SUIVANTE");
    if(!gpu_wait())return 0;
    ae350_dcache_invalidate_range(GPU_PAGE_ADDR(5),800*480);
    demo3d_front=7;demo3d_angle=demo3d_poses[0];demo3d_initialized=1;
    // These demos reused the G3 surfaces. Their next invocation rebuilds them.
    layers_initialized=sprites_initialized=0;
    return 1;
}
static void demo3d_test(void)
{
    if(!demo3d_prepare()){printf("THREED FAIL INIT\r\n");return;}
    for(demo3d_pose=0;demo3d_pose<4;++demo3d_pose)
        if(!demo3d_render(demo3d_poses[demo3d_pose],demo3d_pose==3,1))return;
    demo3d_pose=0;if(!demo3d_render(demo3d_poses[0],0,1))return;
    printf("THREED READY poses=4 underflows=%u\r\n",(unsigned)GPU[7]);
}
static void demo3d_next(void)
{
    demo3d_animate=0;
    if(!demo3d_initialized){demo3d_test();return;}
    demo3d_pose=(demo3d_pose+1)%4;
    if(demo3d_render(demo3d_poses[demo3d_pose],demo3d_pose==3,1))printf("THREED MOVED pose=%u\r\n",demo3d_pose);
}
static void demo3d_start(void)
{
    if(!demo3d_initialized && !demo3d_prepare()){printf("THREED FAIL INIT\r\n");return;}
    demo3d_frames=demo3d_cpu_total=demo3d_gpu_total=demo3d_frame_total=0;
    demo3d_cpu_max=demo3d_gpu_max=demo3d_frame_max=0;demo3d_animate=1;
    printf("THREED ANIMATION started\r\n");
}
static void demo3d_tick(void)
{
    // Yaw takes 256 steps, pitch half as fast: wrap after both rotations.
    demo3d_angle=(demo3d_angle+2)&511;
    if(!demo3d_render(demo3d_angle,0,0)){demo3d_animate=0;return;}
    if(demo3d_frames==120) {
        unsigned avg=(unsigned)(demo3d_frame_total/demo3d_frames);
        printf("THREED BENCH frames=%u cpu_avg=%u cpu_max=%u gpu_avg=%u gpu_max=%u frame_avg=%u frame_max=%u fps_x100=%u underflows=%u\r\n",
            demo3d_frames,(unsigned)(demo3d_cpu_total/demo3d_frames),demo3d_cpu_max,(unsigned)(demo3d_gpu_total/demo3d_frames),demo3d_gpu_max,
            avg,demo3d_frame_max,(unsigned)(80000000000ULL/avg),(unsigned)GPU[7]);
        demo3d_frames=demo3d_cpu_total=demo3d_gpu_total=demo3d_frame_total=0;
        demo3d_cpu_max=demo3d_gpu_max=demo3d_frame_max=0;
    }
}
