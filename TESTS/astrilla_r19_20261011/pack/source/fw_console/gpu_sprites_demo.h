// G4 hardware sprites. Three immutable texture sets in DDR at 32 MiB.
#define SPRITE_IMAGE_ADDR(s,frame) (0x02000000UL+(frame)*65536UL+(s)*1024UL)
static gpu_sprite scene_sprites[64];
static unsigned sprites_initialized,sprite_pose;

static unsigned sprite_demo_size(unsigned s,unsigned pose)
{
    return pose==2 || s==0 || s==63 ? 32 : 8U<<(s%3);
}
// An asymmetric ship: nose to the right, a bright cockpit above its axis,
// and a two-frame flame. Transparent corners make overlap/flip observable.
static unsigned sprite_demo_pixel(unsigned s,unsigned frame,unsigned x,unsigned y,unsigned size)
{
    unsigned xx=x*32/size,yy=y*32/size;
    int axis=(int)yy-16;if(axis<0) axis=-axis;
    if(xx>=8 && xx<29 && axis<=(int)(31-xx)/2) {
        if(xx>25 || axis==(int)(31-xx)/2) return DEMO_WHITE;
        if(xx>=15 && xx<=20 && yy>=11 && yy<=14) return DEMO_CYAN;
        return s%2 ? DEMO_YELLOW : DEMO_RED;
    }
    if(xx>=9 && xx<=16 && yy>=5 && yy<=26) return yy<8 || yy>23 ? DEMO_WHITE : DEMO_CYAN;
    if(xx>=2+frame*3 && xx<8 && axis<3+(int)frame) return frame ? DEMO_YELLOW : DEMO_RED;
    return 0;
}
static void gpu_sprites_make_pose(unsigned pose)
{
    gpu_layers_make_pose(0);
    if(pose==2) for(unsigned l=0;l<16;++l) scene_layers[l].words[6]=0;
    for(unsigned s=0;s<64;++s) {
        unsigned col=s%8,row=s/8,size=sprite_demo_size(s,pose);
        int x=pose==2 ? (int)(s%16)*49-3 : (int)col*100+35;
        int y=pose==2 ? 208 : 58+(int)row*49;
        unsigned priority=pose==2 || row%3 ? 15 : col*2;
        if(pose==1) {x+=17;y+=7;}
        if(pose!=2 && s==0) {x=-6;y=-4;}
        if(pose!=2 && s==63) {x=790;y=470;}
        scene_sprites[s]=gpu_make_sprite(SPRITE_IMAGE_ADDR(s,pose),x,y,size,size,priority,
            GPU_SPRITE_ENABLE|(((s+pose)&3)<<1));
    }
}
static int gpu_sprites_check_pose(unsigned pose)
{
    gpu_sprites_make_pose(pose);
    unsigned expected=gpu_scene_reference_hash(scene_layers,scene_sprites);
    if(!gpu_scene_submit(scene_layers,scene_sprites) || !gpu_display_wait()) {printf("SPRITES FAIL COMMIT\r\n");return 0;}
    unsigned frame=GPU[6],timeout=2000000;
    while((unsigned)(GPU[6]-frame)<2 && --timeout) {}
    unsigned actual=GPU[8],invalid=GPU[0x48/4],underflows=GPU[7];
    if(!timeout || actual!=expected || invalid || underflows || GPU[0x44/4]!=1) {
        printf("SPRITES FAIL pose=%u expected=%08x got=%08x invalid=%u underflows=%u max_cycles=%u\r\n",
            pose,expected,actual,invalid,underflows,(unsigned)GPU[0x2c/4]);return 0;
    }
    sprite_pose=pose;
    printf("SPRITES POSE %u hash=%08x max_cycles=%u max_sprites=%u max_pixels=%u cache_cycles=%u loads=%u underflows=%u\r\n",
        pose,actual,(unsigned)GPU[0x2c/4],(unsigned)GPU[0x4c/4],(unsigned)GPU[0x54/4],(unsigned)GPU[0x50/4],(unsigned)GPU[0x58/4],underflows);
    return 1;
}
static void gpu_sprites_demo(void)
{
    if(GPU[0x3c/4]!=64 || !gpu_display_wait()) {printf("SPRITES FAIL INIT\r\n");return;}
    if(!layers_initialized) gpu_layers_demo();
    if(!layers_initialized) return;
    sprites_initialized=0;
    GPU[2]=0;GPU[3]=1;
    if(!gpu_display_wait()) {printf("SPRITES FAIL DISABLE\r\n");return;}
    for(unsigned pose=0;pose<3;++pose) for(unsigned s=0;s<64;++s) {
        uint8_t *image=(uint8_t *)SPRITE_IMAGE_ADDR(s,pose);
        unsigned size=sprite_demo_size(s,pose);
        for(unsigned y=0;y<32;++y) for(unsigned x=0;x<32;++x)
            image[y*32+x]=(x<size && y<size) ? sprite_demo_pixel(s,pose==1,x,y,size) : 0;
    }
    gpu_publish_surface(SPRITE_IMAGE_ADDR(0,0),196608);
    for(unsigned pose=0;pose<3;++pose) if(!gpu_sprites_check_pose(pose)) return;
    if(!gpu_sprites_check_pose(0)) return;
    sprites_initialized=1;
    printf("SPRITES READY count=64 poses=3 hash=%08x underflows=%u\r\n",(unsigned)GPU[8],(unsigned)GPU[7]);
}
static void gpu_sprites_next(void)
{
    if(!sprites_initialized) {printf("SPRITES FAIL run O first\r\n");return;}
    if(gpu_sprites_check_pose((sprite_pose+1)%3)) printf("SPRITES MOVED pose=%u\r\n",sprite_pose);
}
