// Interactive and autonomous hardware 3D validation, C37-compatible board wiring.
#include <stdio.h>
#include "ae350.h"
#include "cache.h"
#include "world3d_scene.h"
#include "astrilla_hud.h"
#include "astrilla_hud_font.h"
#define DISPLAY ((volatile uint32_t *)0xe9000000UL)
_Static_assert(sizeof(world3d_state)==36,"Wire state contains exactly nine floats");
_Static_assert(WORLD_EXTRA_BASE+WORLD_EXTRA_BYTES<0x08000000UL,"Geometry overlaps upload staging");
static gpu_layer layers[16];static gpu_sprite sprites[64];
static world3d_state view;static world3d_info info;static as_meter meter;
static unsigned frame,front,run=1,automatic=1,loading,submitted,errors,invalid,commands,fx_max,fx_cycles,color_crc,geometry_cycles;
static unsigned vertex_count,triangle_count,clip_count,sliver_count,initial_underflows;
static uint64_t epoch,total_commands;static unsigned last_fps,last_cps;
static uint64_t cycles(void){unsigned h,l,a;do{__asm__ volatile("rdcycleh %0":"=r"(h));__asm__ volatile("rdcycle %0":"=r"(l));__asm__ volatile("rdcycleh %0":"=r"(a));}while(h!=a);return ((uint64_t)h<<32)|l;}
static void put(unsigned c){while(!(AE350_UART2->LSR&0x20U)){}AE350_UART2->THR=c;}
static int get_bytes(uint8_t *p,unsigned n){uint64_t end=cycles()+160000000ULL;for(unsigned i=0;i<n;++i){while(!(AE350_UART2->LSR&1))if(cycles()>end)return 0;p[i]=AE350_UART2->RBR;}return 1;}
static uint32_t crc32(const uint8_t *p,unsigned n){uint32_t c=~0U;for(unsigned i=0;i<n;++i){c^=p[i];for(unsigned b=0;b<8;++b)c=(c>>1)^(0xedb88320U&(0U-(c&1)));}return ~c;}
static void emit(const gpu_command *c){gpu_submit(c);++commands;++total_commands;}
long except_handler(long cause,long epc){printf("WORLD3D TRAP cause=%08x pc=%08x\r\n",(unsigned)cause,(unsigned)epc);for(;;){}}
static int show_loading(void){
 gpu_v1_context c;gpu_v1_init(&c,gpu_submit);gpu_target target={GPU_PAGE_ADDR(7),GPU_PAGE_ADDR(2),400,240,800,800};
 memset(layers,0,sizeof(layers));memset(sprites,0,sizeof(sprites));
 if(!gpu_v1_target(&c,&target)||!gpu_v1_clear(&c,1,2,65535,0,0,400,240)||!gpu_wait())return 0;
 layers[13]=gpu_make_layer(ASTRILLA_LOADING,640,640,128,80,158,640,128,0,0,3);
 return gpu_rgb565_surface_submit(&target,1,layers,sprites)&&gpu_display_wait();
}
static int present(void){
 if(!gpu_display_wait())return 0;
 unsigned start=(unsigned)cycles();gpu_geom_stats before=gpu_geom_read_stats();commands=0;color_crc=0;
 if(automatic)view=world_auto(frame);
 gpu_v1_context c;gpu_v1_init(&c,emit);
 if(!world_render(&c,frame,front^1,&view,&info)||!gpu_wait()||gpu_v1_rejected())return 0;
 gpu_geom_stats after=gpu_geom_read_stats();if(after.errors)return 0;
 vertex_count=after.vertices-before.vertices;triangle_count=after.triangles-before.triangles;
 clip_count=after.intersections-before.intersections;sliver_count=after.slivers-before.slivers;geometry_cycles=after.cycles-before.cycles;
 if(loading){front^=1;fx_cycles=(unsigned)cycles()-start;if(fx_cycles>fx_max)fx_max=fx_cycles;return show_loading();}
 memset(layers,0,sizeof(layers));memset(sprites,0,sizeof(sprites));
 unsigned page=8+(front^1),top=10+(front^1);last_fps=meter.fps_x10;last_cps=meter.commands_s;
 as_hud_draw(emit,page,last_fps,last_cps,0,2);
 gpu_command fill=gpu_make_command(GPU_FILL,top,0,0,0,800,32,0,0,1,0);emit(&fill);
 char title[90];snprintf(title,sizeof(title),"ASTRILLA 3D / HW OBJ %u / TRI %u / SPRITES 3D %u",info.objects,triangle_count,info.billboards);as_hud_text(emit,top,18,title);
 if(!gpu_wait())return 0;
 layers[14]=gpu_make_layer(GPU_PAGE_ADDR(top),800,800,32,0,0,800,32,0,0,1);
 layers[15]=gpu_make_layer(GPU_PAGE_ADDR(page),800,800,32,0,448,800,32,0,0,1);
 fx_cycles=(unsigned)cycles()-start;if(fx_cycles>fx_max)fx_max=fx_cycles;
 if(!gpu_rgb565_surface_submit(&c.target,1,layers,sprites)||!gpu_display_wait())return 0;
 front^=1;return 1;
}
static void status(void){
 uint64_t elapsed=cycles()-epoch;
 printf("WORLD3D frame=%u auto=%u run=%u submitted=%u elapsed_ms=%u fps_x10=%u cmds_s=%u commands=%u total_lo=%u total_hi=%u objects=%u sprites3d=%u vertices=%u triangles=%u clipped=%u slivers=%u geom_cycles=%u fx_cycles=%u fx_max=%u crc565=%08x lcd=%08x errors=%u invalid=%u rejected=%u uf=%u line=%u loading=%u\r\n",frame,automatic,run,submitted,(unsigned)(elapsed/800000),last_fps,last_cps,commands,(unsigned)total_commands,(unsigned)(total_commands>>32),info.objects,info.billboards,vertex_count,triangle_count,clip_count,sliver_count,geometry_cycles,fx_cycles,fx_max,color_crc,(unsigned)DISPLAY[0x60/4],errors,invalid,gpu_v1_rejected(),(unsigned)(DISPLAY[7]-initial_underflows),(unsigned)DISPLAY[0x64/4],loading);
}
static void restart(unsigned auto_mode){epoch=cycles();as_meter_reset(&meter,epoch);automatic=auto_mode;run=1;loading=0;submitted=0;total_commands=0;fx_max=0;}
int main(void){
 clear_csr(NDS_MSTATUS,8);write_csr(NDS_MIE,0);ae350_dcache_flush_all();ae350_icache_invalidate_all();
 __asm__ volatile("fence iorw,iorw\n.word 0x0000100f":::"memory");
 unsigned div=(80000000UL+8UL*115200)/(16UL*115200);AE350_UART2->LCR=0x83;AE350_UART2->DLL=div&255;AE350_UART2->DLM=div>>8;AE350_UART2->LCR=3;AE350_UART2->FCR=7;
 const uint32_t *stage=(const uint32_t *)0x08000000UL;ae350_dcache_invalidate_range(0x08000000UL,ASTRILLA_BYTES);
 if(stage[0]==0x41535452&&stage[1]==1&&stage[2]==ASTRILLA_BYTES&&stage[3]==ASTRILLA_CRC&&crc32((const uint8_t *)stage+1024,ASTRILLA_BYTES-1024)==ASTRILLA_CRC){memcpy((void *)ASTRILLA_BASE,stage,ASTRILLA_BYTES);gpu_publish_surface(ASTRILLA_BASE,ASTRILLA_BYTES);}
 if(crc32((const uint8_t *)(ASTRILLA_BASE+1024),ASTRILLA_BYTES-1024)!=ASTRILLA_CRC||!gpu_blit_init()||!gpu_v1_supported()||!gpu_geom_supported()){printf("WORLD3D INIT FAIL\r\n");for(;;){}}
 for(unsigned i=0;i<256;++i)DISPLAY[0x100+i]=((const uint32_t *)ASTRILLA_PALETTE)[i];
 gpu_font_write(32*16,as_hud_font,sizeof(as_hud_font));
 if(!show_loading()||!world_prepare((uint8_t *)AS3_HW_BASE,(uint8_t *)WORLD_EXTRA_BASE)){printf("WORLD3D PREPARE FAIL\r\n");for(;;){}}
 gpu_publish_surface(AS3_HW_BASE,AS3_HW_BYTES+WORLD_EXTRA_BYTES);
 gpu_v1_context c;gpu_v1_init(&c,gpu_submit);gpu_v1_invalidate(&c);if(!gpu_wait())return 1;
 initial_underflows=DISPLAY[7];DISPLAY[0x2c/4]=0;restart(1);
 printf("ASTRILLA READY R1 WORLD3D geometry=hardware core=800MHz autoplay=1\r\n");
 for(;;){
  if(AE350_UART2->LSR&1){unsigned char command=AE350_UART2->RBR;
   if(command=='?')printf("ASTRILLA R1 WORLD3D G3D1 hardware=1\r\n");
   else if(command=='P'){run=0;as_meter_reset(&meter,cycles());last_fps=last_cps=0;printf("ASTRILLA PAUSED\r\n");}
   else if(command=='L'){run=0;loading=1;as_meter_reset(&meter,cycles());last_fps=last_cps=0;if(!show_loading())++errors;printf("WORLD3D LOADING\r\n");}
   else if(command=='R'||command=='G'){restart(command=='R'?1:automatic);printf("WORLD3D AUTO\r\n");}
   else if(command=='S')status();
   else if(command=='V'){
    uint8_t packet[40];world3d_state next;uint32_t expected;
    if(get_bytes(packet,sizeof(packet))){memcpy(&next,packet,36);memcpy(&expected,packet+36,4);
     if(crc32(packet,36)==expected&&world_state_valid(&next)){view=next;automatic=0;printf("WORLD3D VIEW OK\r\n");}
     else{++invalid;printf("WORLD3D VIEW INVALID\r\n");}
    }else{++invalid;printf("WORLD3D VIEW TIMEOUT\r\n");}
   }
   else if(command=='T'){uint8_t t[2];if(get_bytes(t,2)){run=0;as_meter_reset(&meter,cycles());frame=(t[0]+(unsigned)t[1]*256)%6600;
    if(!present())++errors;
    ae350_dcache_invalidate_range(GPU_PAGE_ADDR(front),192000);color_crc=crc32((const uint8_t *)GPU_PAGE_ADDR(front),192000);status();}}
   else if(command=='E'){uint8_t n[2];if(get_bytes(n,2)){unsigned count=n[0]+(unsigned)n[1]*256;while(count--){uint8_t c;if(!get_bytes(&c,1)){++invalid;break;}put(c);}}}
  }
  if(run){frame=(unsigned)(((cycles()-epoch)*55/800000000ULL)%6600);
   if(!present()){++errors;run=0;printf("WORLD3D DISPLAY FAIL\r\n");}
   else{++submitted;as_meter_frame(&meter,cycles(),commands);}}
 }
}
