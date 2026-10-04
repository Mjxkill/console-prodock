#include "gpu_affine_scene.h"
static unsigned affine_initialized,affine_animate,affine_front,affine_angle,affine_pose;
static unsigned affine_frames,affine_gpu_max,affine_frame_max;
static uint64_t affine_gpu_total,affine_frame_total;
static gpu_affine_transform affine_reference_matrix;

static int64_t affine_floor(int64_t n)
{
    return n>=0 ? n/65536 : -((-n+65535)/65536);
}
static void affine_reference(const gpu_command *c)
{
    uint8_t *dst=(uint8_t *)GPU_PAGE_ADDR(4);
    const uint32_t *w=c->words;
    if(w[0]>>24==GPU_AFFINE_SETUP) {
        affine_reference_matrix=(gpu_affine_transform){(int32_t)w[1],(int32_t)w[2],
            (int32_t)w[3],(int32_t)w[4],(int32_t)w[5],(int32_t)w[6]};
    } else if(w[0]>>24==GPU_AFFINE) {
        int x=(int16_t)(w[1]>>16),y=(int16_t)w[1],width=w[2]>>16,height=w[2]&65535;
        const gpu_affine_transform *m=&affine_reference_matrix;
        // Independent 64-bit per-pixel products, no accumulated coordinates.
        for(int yy=max_int(y,0);yy<min_int(y+height,480);++yy)
            for(int xx=max_int(x,0);xx<min_int(x+width,800);++xx) {
                int64_t u=affine_floor((int64_t)m->u0+(int64_t)(xx-x)*m->du_dx+(int64_t)(yy-y)*m->du_dy);
                int64_t v=affine_floor((int64_t)m->v0+(int64_t)(xx-x)*m->dv_dx+(int64_t)(yy-y)*m->dv_dy);
                if(u>=0 && u<128 && v>=0 && v<128) {
                    unsigned pixel=affine_asset((unsigned)u,(unsigned)v);
                    if(pixel)dst[yy*800+xx]=pixel;
                }
            }
    } else reference_draw(c,dst);
}
static int affine_prepare(void)
{
    affine_initialized=affine_animate=0;
    if(!gpu_blit_init() || !gpu_affine_supported() || !gpu_wait() || !gpu_display_wait())return 0;
    GPU[2]=0;GPU[3]=1;if(!gpu_display_wait())return 0;
    for(unsigned i=0;i<256;++i)GPU[0x100+i]=gpu_demo_palette_color(i);
    for(unsigned p=5;p<=7;++p) {
        memset((void *)GPU_PAGE_ADDR(p),p==5?0:0xa5,800*480+64);
        gpu_publish_surface(GPU_PAGE_ADDR(p),800*480+64);
    }
    uint8_t *source=(uint8_t *)GPU_PAGE_ADDR(15);
    memset(source,0xa5,800*480+64);
    for(unsigned y=0;y<128;++y)for(unsigned x=0;x<128;++x)source[(y+19)*800+x+17]=affine_asset(x,y);
    gpu_publish_surface(GPU_PAGE_ADDR(15),800*480+64);
    gpu_text(5,24,16,DEMO_WHITE,0,2,"L12 - AFFINE GPU");
    gpu_text(5,24,54,DEMO_CYAN,0,1,"ROTATION / ZOOM X-Y / CISAILLEMENT / TRANSPARENCE");
    gpu_text(5,70,284,DEMO_YELLOW,0,1,"ROTATION");
    gpu_text(5,344,284,DEMO_YELLOW,0,1,"ZOOM X/Y");
    gpu_text(5,604,284,DEMO_YELLOW,0,1,"CISAILLEMENT");
    gpu_text(5,24,460,DEMO_WHITE,0,1,"I : TEST   Z : ANIMATION   Q : PAUSE");
    if(!gpu_wait())return 0;
    ae350_dcache_invalidate_range(GPU_PAGE_ADDR(5),800*480);
    layers_initialized=sprites_initialized=demo3d_initialized=tiles_initialized=0;
    affine_front=7;affine_angle=0;affine_initialized=1;return 1;
}
static int affine_render(unsigned angle,int verify)
{
    unsigned page=affine_front==6?7:6,begin=read_csr(NDS_MCYCLE),before=gpu_completed();
    affine_scene(page,angle,gpu_submit);
    if(!gpu_wait()){printf("AFFINE FAIL FENCE\r\n");return 0;}
    unsigned drawn=read_csr(NDS_MCYCLE),gpu=drawn-begin;
    if(verify) {
        affine_scene(page,angle,affine_reference);
        ae350_dcache_invalidate_range(GPU_PAGE_ADDR(page),800*480+64);
        uint8_t *actual=(uint8_t *)GPU_PAGE_ADDR(page),*expected=(uint8_t *)GPU_PAGE_ADDR(4);
        unsigned errors=0;
        for(unsigned i=0;i<800*480+64;++i) {
            unsigned want=i<800*480?expected[i]:0xa5;
            if(actual[i]!=want) {
                if(errors<4)printf("AFFINE FAIL byte=%u expected=%02x got=%02x\r\n",i,want,actual[i]);
                ++errors;
            }
        }
        if(errors)return 0;
    }
    memset(scene_layers,0,sizeof(scene_layers));
    scene_layers[0]=gpu_make_layer(GPU_PAGE_ADDR(page),800,800,480,0,0,800,480,0,0,GPU_LAYER_ENABLE);
    scene_layers[15]=gpu_make_layer(GPU_PAGE_ADDR(5),800,800,480,0,0,800,480,0,0,GPU_LAYER_ENABLE|GPU_LAYER_KEY_ZERO);
    unsigned hash=verify?gpu_layers_reference_hash(scene_layers):0;
    if(!gpu_layers_submit(scene_layers) || !gpu_display_wait()){printf("AFFINE FAIL COMMIT\r\n");return 0;}
    affine_front=page;
    if(verify) {
        unsigned frame=GPU[6],timeout=2000000;
        while((unsigned)(GPU[6]-frame)<2 && --timeout) {}
        if(!timeout || GPU[8]!=hash || GPU[7]){printf("AFFINE FAIL HASH expected=%08x got=%08x underflows=%u\r\n",hash,(unsigned)GPU[8],(unsigned)GPU[7]);return 0;}
        printf("AFFINE POSE %u hash=%08x commands=%u gpu_cycles=%u underflows=%u\r\n",affine_pose,hash,(gpu_completed()-before)&65535,gpu,(unsigned)GPU[7]);
    } else {
        unsigned elapsed=read_csr(NDS_MCYCLE)-begin;
        ++affine_frames;affine_gpu_total+=gpu;affine_frame_total+=elapsed;
        if(gpu>affine_gpu_max)affine_gpu_max=gpu;
        if(elapsed>affine_frame_max)affine_frame_max=elapsed;
    }
    return 1;
}
static void affine_test(void)
{
    if(!affine_prepare()){printf("AFFINE FAIL INIT\r\n");return;}
    for(affine_pose=0;affine_pose<4;++affine_pose)if(!affine_render(affine_poses[affine_pose],1))return;
    printf("AFFINE READY poses=4 underflows=%u\r\n",(unsigned)GPU[7]);
}
static void affine_start(void)
{
    if(!affine_initialized && !affine_prepare()){printf("AFFINE FAIL INIT\r\n");return;}
    affine_frames=affine_gpu_max=affine_frame_max=0;affine_gpu_total=affine_frame_total=0;
    affine_animate=1;printf("AFFINE ANIMATION started\r\n");
}
static void affine_tick(void)
{
    affine_angle=(affine_angle+1)&255;
    if(!affine_render(affine_angle,0)){affine_animate=0;return;}
    if(affine_frames==240) {
        unsigned avg=(unsigned)(affine_frame_total/affine_frames);
        printf("AFFINE BENCH frames=%u gpu_avg=%u gpu_max=%u frame_avg=%u frame_max=%u fps_x100=%u underflows=%u\r\n",
            affine_frames,(unsigned)(affine_gpu_total/affine_frames),affine_gpu_max,avg,affine_frame_max,
            (unsigned)(80000000000ULL/avg),(unsigned)GPU[7]);
        affine_frames=affine_gpu_max=affine_frame_max=0;affine_gpu_total=affine_frame_total=0;
    }
}
