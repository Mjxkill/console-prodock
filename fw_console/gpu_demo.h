// Hardware diagnostic: draw off-screen, then compare every byte with a CPU image.
// Included only by gpu_diag.c; the application-facing driver is gpu.h/gpu.c.
#include "gpu.h"
#include "build/gpu_font.h"
#include <string.h>
static gpu_command demo_commands[128];
static unsigned demo_count;
static uint8_t copy_row[GPU_WIDTH];
static uint8_t custom_glyph[16];

static void ref_pixel(uint8_t *dst, int x, int y, unsigned color)
{
    if ((unsigned)x < GPU_WIDTH && (unsigned)y < GPU_HEIGHT)
        dst[y*GPU_WIDTH+x] = color;
}
static int max_int(int a, int b) { return a > b ? a : b; }
static int min_int(int a, int b) { return a < b ? a : b; }
static int abs_int(int a) { return a < 0 ? -a : a; }
static void reference_draw(const gpu_command *cmd, uint8_t *dst)
{
    const uint32_t *w = cmd->words;
    unsigned op=w[0]>>24, fg=(w[0]>>8)&255, bg=w[0]&255;
    unsigned dp=(w[0]>>20)&15, sp=(w[0]>>16)&15;
    int x=(int16_t)(w[1]>>16), y=(int16_t)w[1];
    int a=(int16_t)(w[2]>>16), b=(int16_t)w[2];
    int sx=(int16_t)(w[3]>>16), sy=(int16_t)w[3];
    if (op>=GPU_FILL && op<=GPU_GRAD_D) {
        if (a<=0 || b<=0) return;
        unsigned n=op==GPU_GRAD_H ? a-1 : op==GPU_GRAD_V ? b-1 : a+b-2;
        unsigned step=n ? 65536/n : 65536;
        for (int yy=max_int(0,y); yy<min_int(GPU_HEIGHT,y+b); ++yy)
            for (int xx=max_int(0,x); xx<min_int(GPU_WIDTH,x+a); ++xx) {
                unsigned pos=op==GPU_GRAD_H ? xx-x : op==GPU_GRAD_V ? yy-y : xx-x+yy-y;
                unsigned delta=(abs_int((int)bg-(int)fg)*pos*step)>>16;
                ref_pixel(dst,xx,yy,op==GPU_FILL ? fg : bg<fg ? fg-delta : fg+delta);
            }
    } else if (op==GPU_LINE) {
        int dx=abs_int(a-x), dy=abs_int(b-y), ex=x<a ? 1 : -1, ey=y<b ? 1 : -1, err=dx-dy;
        for (;;) {
            ref_pixel(dst,x,y,fg);
            if (x==a && y==b) break;
            int e=err*2;
            if (e>-dy) {err-=dy; x+=ex;}
            if (e<dx) {err+=dx; y+=ey;}
        }
    } else if (op==GPU_CIRCLE || op==GPU_DISK) {
        int cx=a, cy=0, err=1-a;
        while (cx>=cy) {
            if (op==GPU_CIRCLE) {
                const int pts[8][2]={{cx,cy},{-cx,cy},{cx,-cy},{-cx,-cy},
                                     {cy,cx},{-cy,cx},{cy,-cx},{-cy,-cx}};
                for (unsigned i=0;i<8;++i) ref_pixel(dst,x+pts[i][0],y+pts[i][1],fg);
            } else {
                const int rows[4][3]={{cy,-cx,cx},{-cy,-cx,cx},{cx,-cy,cy},{-cx,-cy,cy}};
                for (unsigned i=0;i<4;++i)
                    for (int xx=max_int(0,x+rows[i][1]);xx<=min_int(GPU_WIDTH-1,x+rows[i][2]);++xx)
                        ref_pixel(dst,xx,y+rows[i][0],fg);
            }
            ++cy;
            if (err<0) err+=2*cy+1;
            else {--cx;err+=2*(cy-cx)+1;}
        }
    } else if (op==GPU_COPY) {
        uint8_t *src=sp==dp ? dst : (uint8_t *)GPU_PAGE_ADDR(sp);
        int first=0, end=b, inc=1;
        if (sp==dp && y>sy) {first=b-1;end=-1;inc=-1;}
        for (int row=first;row!=end;row+=inc) {
            if ((unsigned)(y+row)>=GPU_HEIGHT || (unsigned)(sy+row)>=GPU_HEIGHT) continue;
            int left=max_int(0,max_int(-x,-sx)),right=min_int(a,min_int(GPU_WIDTH-x,GPU_WIDTH-sx));
            if (left>=right) continue;
            memcpy(copy_row,src+(sy+row)*GPU_WIDTH+sx+left,right-left);
            memcpy(dst+(y+row)*GPU_WIDTH+x+left,copy_row,right-left);
        }
    } else if (op==GPU_TEXT) {
        int scale=b==2 ? 2 : 1;
        const uint8_t *text=(const uint8_t *)&w[4];
        for (int i=0;i<min_int(a,16);++i)
            for (int row=0;row<16;++row)
                for (int col=0;col<8;++col) {
                    unsigned bits=text[i]==0x80 ? custom_glyph[row] : gpu_font[text[i]*16+row];
                    unsigned on=bits & (128U>>col);
                    if (!on && !bg) continue;
                    for (int yy=0;yy<scale;++yy) for (int xx=0;xx<scale;++xx)
                        ref_pixel(dst,x+(i*8+col)*scale+xx,y+row*scale+yy,on ? fg : bg);
                }
    }
}
static void demo_add(unsigned op,int x,int y,int a,int b,unsigned fg,unsigned bg,int sx,int sy,unsigned src)
{
    demo_commands[demo_count++]=gpu_make_command(op,1,src,x,y,a,b,sx,sy,fg,bg);
}
static void demo_text(int x,int y,unsigned scale,unsigned fg,unsigned bg,const char *text)
{
    unsigned n=strlen(text);
    if(n>16) n=16;
    demo_add(GPU_TEXT,x,y,n,scale,fg,bg,0,0,0);
    memcpy(&demo_commands[demo_count-1].words[4],text,n);
}
static int gpu_accel_demo(void)
{
    if (!gpu_blit_init()) {printf("BLIT FAIL ID\r\n");return 0;}
    if (!gpu_wait()) {printf("BLIT FAIL INITIAL FENCE\r\n");return 0;}
    // A spare source surface with a nonuniform byte pattern exercises copy lanes.
    uint8_t *target=(uint8_t *)GPU_PAGE_ADDR(1), *ref=(uint8_t *)GPU_PAGE_ADDR(2);
    uint8_t *source=(uint8_t *)GPU_PAGE_ADDR(3);
    const unsigned bytes=GPU_WIDTH*GPU_HEIGHT;
    memset(target,0x5a,bytes+64); memset(ref,0x5a,bytes+64);
    for(unsigned i=0;i<bytes;++i) source[i]=(i*29+(i>>11))&255;
    gpu_publish_surface(GPU_PAGE_ADDR(1),bytes+64);
    gpu_publish_surface(GPU_PAGE_ADDR(3),bytes);
    for(unsigned row=0;row<16;++row) custom_glyph[row]=(row&1)?0xa5:0x5a;
    gpu_font_write(0x800,custom_glyph,16);
    demo_count=0;
    demo_add(GPU_FILL,0,0,800,480,0x01,0,0,0,0);
    demo_add(GPU_GRAD_H,20,90,256,60,0,255,0,0,0);
    demo_add(GPU_GRAD_V,290,90,90,260,0x03,0xfc,0,0,0);
    demo_add(GPU_GRAD_D,395,90,200,130,0x20,0xff,0,0,0);
    demo_add(GPU_DISK,680,155,60,0,0xe0,0,0,0,0);
    demo_add(GPU_CIRCLE,680,155,70,0,0xff,0,0,0,0);
    demo_add(GPU_LINE,10,470,790,230,0xfc,0,0,0,0);
    demo_add(GPU_LINE,10,230,790,470,0x1f,0,0,0,0);
    for(unsigned i=0;i<32;++i)
        demo_add(GPU_COPY,20+i,180+i*2,96-i,1,0,0,31-i,100+i,3);
    demo_add(GPU_COPY,145,175,110,75,0,0,12,178,1);
    demo_add(GPU_COPY,147,180,100,70,0,0,145,175,1);
    demo_add(GPU_COPY,148,180,96,60,0,0,147,180,1);
    demo_add(GPU_COPY,-5,300,40,25,0,0,-10,470,3);
    demo_add(GPU_FILL,32760,50,100,10,0xff,0,0,0,0);
    demo_add(GPU_FILL,10,10,0,1,0xff,0,0,0,0);
    demo_add(GPU_LINE,-32768,479,32767,478,0x87,0,0,0,0);
    demo_add(GPU_CIRCLE,32760,50,100,0,0xff,0,0,0,0);
    demo_add(GPU_GRAD_H,-32700,476,32767,2,3,240,0,0,0);
    demo_text(24,20,2,255,0,"MEGA PRO CONSOLE");
    demo_text(24,58,1,0xfc,0,"G2 - DDR3 - 2D");
    demo_text(420,260,2,255,0,"BLITTER + TEXTE");
    demo_text(420,303,1,0x1f,0,"AE350 : 800 MHz");
    demo_text(420,332,1,0xfc,0x24,"COPIES / FORMES");
    demo_text(420,361,1,255,0,"POLICE : \x80\x80\x80");
    demo_text(540,437,2,255,0,"0123456789ABCDEF");
    unsigned before=gpu_completed();
    unsigned cycles=read_csr(NDS_MCYCLE);
    for(unsigned i=0;i<demo_count;++i) gpu_submit(&demo_commands[i]);
    // Exercise CPU DDR traffic while the blitter finishes and scanout continues.
    volatile uint32_t *shared=(volatile uint32_t *)0x00200000UL;
    for(unsigned i=0;i<4096;++i) shared[i]=0x9e3779b9U*i;
    ae350_dcache_flush_range((unsigned long)shared,16384);
    unsigned shared_errors=0;
    for(unsigned i=0;i<4096;++i) if(shared[i]!=0x9e3779b9U*i) ++shared_errors;
    if(shared_errors) {printf("BLIT FAIL SHARED errors=%u\r\n",shared_errors);return 0;}
    if(!gpu_wait()) {printf("BLIT FAIL FENCE done=%u errors=%08x\r\n",gpu_completed(),gpu_errors());return 0;}
    cycles=read_csr(NDS_MCYCLE)-cycles;
    printf("BLIT DRAW commands=%u cycles=%u done=%u\r\n",demo_count,cycles,(gpu_completed()-before)&65535);
    // CPU reference uses a different page, so it cannot hide a failed GPU write.
    for(unsigned i=0;i<demo_count;++i) reference_draw(&demo_commands[i],ref);
    ae350_dcache_invalidate_range(GPU_PAGE_ADDR(1),bytes+64);
    unsigned errors=0, sum=0;
    for(unsigned i=0;i<bytes+64;++i) {
        unsigned got=target[i],expected=ref[i];
        if(got!=expected) {
            if(errors<8) printf("BLIT FAIL byte=%u expected=%02x got=%02x\r\n",i,expected,got);
            ++errors;
        }
    }
    for(unsigned i=0;i<bytes/4;++i) sum+=((uint32_t *)target)[i];
    if(errors) {printf("BLIT END errors=%u\r\n",errors);return 0;}
    page_sums[1]=sum;
    if(!gpu_commit(1)) {printf("BLIT FAIL COMMIT\r\n");return 0;}
    displayed_page=1;
    printf("BLIT END errors=0 commands=%u sum=%08x\r\n",demo_count,sum);
    return 1;
}
