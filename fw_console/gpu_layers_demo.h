// G3 diagnostic: every pixel of 16 full surfaces is fetched, even when keyed
// transparent. Each surface contributes a numbered colored strip to the LCD.
static gpu_layer scene_layers[16];
static uint8_t layer_reference_row[GPU_WIDTH];
static unsigned layers_initialized,layer_pose;

static uint32_t rotate32(uint32_t value,unsigned n)
{
    return (value<<(n&31))|(value>>((32-n)&31));
}
static unsigned gpu_layers_reference_hash(const gpu_layer table[16])
{
    uint32_t hash=0;
    for(int y=0;y<GPU_HEIGHT;++y) {
        memset(layer_reference_row,0,sizeof(layer_reference_row));
        for(unsigned l=0;l<16;++l) {
            const uint32_t *d=table[l].words;
            unsigned flags=d[6];
            int px=(int16_t)d[2],py=(int16_t)(d[2]>>16);
            int sw=d[1]&65535,sh=d[1]>>16,vw=d[3]&65535,vh=d[3]>>16;
            int sx=d[4]&65535,sy=d[4]>>16,dy=y-py;
            if(!(flags&GPU_LAYER_ENABLE) || dy<0 || dy>=vh || sy+dy>=sh) continue;
            int left=max_int(0,px),right=min_int(GPU_WIDTH,min_int(px+vw,px+sw-sx));
            const uint8_t *source=(const uint8_t *)d[0]+(sy+dy)*(d[5]&65535);
            for(int x=left;x<right;++x) {
                unsigned p=source[sx+x-px];
                if(!(flags&GPU_LAYER_KEY_ZERO) || p) layer_reference_row[x]=p;
            }
        }
        for(unsigned x=0;x<GPU_WIDTH;x+=32) {
            uint32_t block=0;
            for(unsigned w=0;w<8;++w) {
                uint32_t word;memcpy(&word,&layer_reference_row[x+w*4],4);
                block^=rotate32(word,w*4);
            }
            hash=rotate32(hash,5)^block;
        }
    }
    return hash;
}
static void gpu_layers_make_pose(unsigned pose)
{
    for(unsigned l=0;l<16;++l) {
        unsigned page=pose==2 ? (l+5)&15 : l;
        int x=pose==1 ? (int)(l%4)*3-4 : pose==2 ? ((l&1)?25:-12) : 0;
        int y=pose==1 ? (int)(l%3)*3-3 : 0;
        unsigned sx=pose==1 ? l%5 : 0,sy=pose==1 ? l%7 : 0;
        scene_layers[l]=gpu_make_layer(GPU_PAGE_ADDR(page),GPU_WIDTH,GPU_WIDTH,GPU_HEIGHT,
            x,y,GPU_WIDTH,GPU_HEIGHT,sx,sy,GPU_LAYER_ENABLE|(l ? GPU_LAYER_KEY_ZERO : 0));
    }
}
static int gpu_layers_check_pose(unsigned pose)
{
    gpu_layers_make_pose(pose);
    unsigned expected=gpu_layers_reference_hash(scene_layers);
    if(!gpu_layers_submit(scene_layers) || !gpu_display_wait()) {printf("LAYERS FAIL COMMIT\r\n");return 0;}
    unsigned frame=GPU[6],timeout=2000000;
    while((unsigned)(GPU[6]-frame)<2 && --timeout) {}
    unsigned actual=GPU[8],errors=GPU[0x38/4],underflows=GPU[7];
    if(!timeout || actual!=expected || errors || underflows || GPU[0x34/4]!=1) {
        printf("LAYERS FAIL pose=%u expected=%08x got=%08x invalid=%u underflows=%u max_cycles=%u\r\n",pose,expected,actual,errors,underflows,(unsigned)GPU[0x2c/4]);
        return 0;
    }
    layer_pose=pose;
    printf("LAYERS POSE %u hash=%08x max_cycles=%u underflows=%u\r\n",pose,actual,(unsigned)GPU[0x2c/4],underflows);
    return 1;
}
static void gpu_layers_demo(void)
{
    if(GPU[0x28/4]!=16 || !gpu_blit_init() || !gpu_wait() || !gpu_display_wait()) {
        printf("LAYERS FAIL INIT\r\n");return;
    }
    // Rebuild all surfaces while scanout is disabled; the palette is global.
    GPU[2]=0;GPU[0x30/4]=0;GPU[3]=1;
    if(!gpu_display_wait()) {printf("LAYERS FAIL DISABLE\r\n");return;}
    layers_initialized=0;
    for(unsigned i=0;i<256;++i) GPU[0x100+i]=gpu_demo_palette_color(i);
    for(unsigned page=0;page<16;++page) {
        uint8_t *surface=(uint8_t *)GPU_PAGE_ADDR(page);
        unsigned ramp=64+(page%3)*64;
        for(unsigned y=0;y<GPU_HEIGHT;++y)
            for(unsigned x=0;x<GPU_WIDTH;++x)
                surface[y*GPU_WIDTH+x]=(x/50==page && x%50<46) ? ramp+y*63/(GPU_HEIGHT-1) : 0;
        gpu_publish_surface(GPU_PAGE_ADDR(page),GPU_WIDTH*GPU_HEIGHT);
        char label[3]={'0'+page/10,'0'+page%10,0};
        gpu_text(page,(int)page*50+7,24,DEMO_WHITE,0,2,label);
    }
    if(!gpu_wait()) {printf("LAYERS FAIL TEXT\r\n");return;}
    for(unsigned page=0;page<16;++page)
        ae350_dcache_invalidate_range(GPU_PAGE_ADDR(page),GPU_WIDTH*GPU_HEIGHT);
    printf("LAYERS SURFACES count=16 bytes=%u\r\n",16*GPU_WIDTH*GPU_HEIGHT);
    for(unsigned pose=0;pose<3;++pose) if(!gpu_layers_check_pose(pose)) return;
    if(!gpu_layers_check_pose(0)) return;
    layers_initialized=1;
    printf("LAYERS READY poses=3 hash=%08x max_cycles=%u underflows=%u\r\n",(unsigned)GPU[8],(unsigned)GPU[0x2c/4],(unsigned)GPU[7]);
}
static void gpu_layers_next(void)
{
    if(!layers_initialized) {printf("LAYERS FAIL run L first\r\n");return;}
    if(gpu_layers_check_pose((layer_pose+1)%3)) printf("LAYERS MOVED pose=%u\r\n",layer_pose);
}
