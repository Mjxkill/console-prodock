// ASTRILLA autonomous cinematic. C37, AE350 800 MHz, volatile ILM/DDR only.
#include <stdio.h>
#include "ae350.h"
#include "cache.h"
#include "astrilla_scene.h"
#include "astrilla_hud.h"
#include "astrilla_hud_font.h"
#define DISPLAY ((volatile uint32_t *)0xe9000000UL)
_Static_assert(AS_CACHE_BASE+AS_CACHE_BYTES<=0x20000000UL,"Camera cache exceeds 512 MiB DDR");
_Static_assert(0x08000000UL+ASTRILLA_BYTES<=AS_CACHE_BASE-4096,"Stage overlaps camera metadata");
_Static_assert(ASTRILLA_BASE+ASTRILLA_BYTES<=0x08000000UL,"Assets overlap upload staging");
static gpu_layer layers[16];static gpu_sprite sprites[64];static astrilla_info info;
static unsigned frame,run=1,submitted,errors,loops,initial_underflows,crc,front,fx_cycles,fx_max,color_crc,bg_cycles,loading;
static as_meter meter;
static unsigned hud_crc,frame_commands,hud_fps_x10,hud_commands_s,hud_layers,hud_sprites;
static uint64_t command_total;
#ifdef ASTRILLA_HW_GEOMETRY
static gpu_geom_stats geometry_frame;
#define AS_GPU_NAME "G3D1 geometry=hardware"
#define AS_GEOM_STATUS " geom_vertices=%u geom_triangles=%u geom_clipped=%u geom_slivers=%u geom_cycles=%u"
#define AS_GEOM_ARGS ,(unsigned)geometry_frame.vertices,(unsigned)geometry_frame.triangles,(unsigned)geometry_frame.intersections,(unsigned)geometry_frame.slivers,(unsigned)geometry_frame.cycles
#else
#define AS_GPU_NAME "C37"
#define AS_GEOM_STATUS ""
#define AS_GEOM_ARGS
#endif
static void counted_submit(const gpu_command *c){gpu_submit(c);++frame_commands;++command_total;}
static uint64_t epoch,measure;static unsigned resume_phase;
static uint64_t cycles(void){unsigned hi,lo,again;do{__asm__ volatile("rdcycleh %0":"=r"(hi));__asm__ volatile("rdcycle %0":"=r"(lo));__asm__ volatile("rdcycleh %0":"=r"(again));}while(hi!=again);return ((uint64_t)hi<<32)|lo;}
static void put(unsigned c){while(!(AE350_UART2->LSR&0x20U)){}AE350_UART2->THR=c;}
static int get_timeout(unsigned char *c){uint64_t limit=cycles()+800000000ULL;while(!(AE350_UART2->LSR&1U))if(cycles()>limit)return 0;*c=AE350_UART2->RBR;return 1;}
static uint32_t crc32(const uint8_t *p,unsigned n){uint32_t c=~0U;for(unsigned i=0;i<n;++i){c^=p[i];for(unsigned bit=0;bit<8;++bit)c=(c>>1)^(0xedb88320U&(0U-(c&1)));}return ~c;}
long except_handler(long cause,long epc){const char *s="\r\nASTRILLA TRAP ";while(*s)put(*s++);unsigned v[3]={(unsigned)cause,(unsigned)epc,read_csr(NDS_MTVAL)};for(unsigned i=0;i<3;++i){for(int b=28;b>=0;b-=4)put("0123456789abcdef"[(v[i]>>b)&15]);put(' ');}for(;;){}}
static int show_loading(unsigned done,unsigned total){
 if(!total||done>total)return 0;
 gpu_v1_context c;gpu_v1_init(&c,gpu_submit);
 gpu_target screen={GPU_PAGE_ADDR(7),GPU_PAGE_ADDR(2),400,240,800,800};
 memset(layers,0,sizeof(layers));memset(sprites,0,sizeof(sprites));
 if(!gpu_v1_target(&c,&screen)||!gpu_v1_scissor(&c,0,0,400,240)||!gpu_v1_clear(&c,1,0x0002,65535,0,0,400,240)||!gpu_wait())return 0;
 layers[13]=gpu_make_layer(ASTRILLA_LOADING,640,640,128,80,158,640,128,0,0,3);
 layers[14]=gpu_make_layer(ASTRILLA_PROGRESS,800,800,2,100,304,600,2,0,0,1);
 unsigned width=done*600U/total;
 if(width)layers[15]=gpu_make_layer(ASTRILLA_PROGRESS,800,800,2,100,298,width,2,0,0,1);
 return gpu_rgb565_surface_submit(&screen,1,layers,sprites)&&gpu_display_wait();
}
static void prepare_backgrounds(void){
 volatile uint32_t *header=(volatile uint32_t *)(AS_CACHE_BASE-4096);unsigned signature=ASTRILLA_CRC^0xabc90004U;
 for(unsigned i=0;i<AS_CACHE_FRAMES;++i){as_camera cam=as_cache_view(i);signature=(signature<<7|signature>>25)^crc32((const uint8_t *)&cam,11*4);}
 // A valid cache belongs to this exact asset pack/camera mapping. Mark invalid
 // before filling; firmware reloads can reuse a completed volatile cache.
 ae350_dcache_invalidate_range(AS_CACHE_BASE-4096,32);
 if(header[0]==0x41534348 && header[1]==signature && header[2]==AS_CACHE_FRAMES){printf("ASTRILLA BACKGROUNDS cached=%u\r\n",AS_CACHE_FRAMES);return;}
 header[0]=0;gpu_publish_surface(AS_CACHE_BASE-4096,32);
 for(unsigned i=0;i<AS_CACHE_FRAMES;++i){
  astrilla_cache(i,(uint16_t *)as_cache_addr(i),(const uint8_t *)ASTRILLA_BASE);
  gpu_publish_surface(as_cache_addr(i),as_cache_bytes(i));
  if(i%16==0&&!show_loading(i,AS_CACHE_FRAMES)){printf("ASTRILLA LOADING FAIL\r\n");for(;;){}}
  if(i%220==0)printf("ASTRILLA BACKGROUNDS %u/%u\r\n",i,AS_CACHE_FRAMES);
 }
 header[1]=signature;header[2]=AS_CACHE_FRAMES;header[0]=0x41534348;gpu_publish_surface(AS_CACHE_BASE-4096,32);
}
static int present(unsigned t){
 if(!gpu_display_wait())return 0;
 unsigned start=(unsigned)cycles();frame_commands=0;gpu_v1_context c;gpu_v1_init(&c,counted_submit);
 bg_cycles=0;
#ifdef ASTRILLA_HW_GEOMETRY
 gpu_geom_stats geometry_before=gpu_geom_read_stats();
#endif
 astrilla_layers(t,layers,sprites,&info);if(!astrilla_render(&c,t,front^1)||!gpu_wait()||gpu_v1_rejected())return 0;
#ifdef ASTRILLA_HW_GEOMETRY
 gpu_geom_stats geometry_after=gpu_geom_read_stats();
 geometry_frame=(gpu_geom_stats){geometry_after.errors,geometry_after.vertices-geometry_before.vertices,
  geometry_after.triangles-geometry_before.triangles,geometry_after.culled-geometry_before.culled,
  geometry_after.intersections-geometry_before.intersections,geometry_after.slivers-geometry_before.slivers,
  geometry_after.cycles-geometry_before.cycles};
 if(geometry_after.errors)return 0;
#endif
 color_crc=hud_crc=0;
 {
  as_hud_layers(info.chapter,8+(front^1),layers);
  hud_layers=as_hud_layer_count(layers);hud_sprites=as_hud_sprite_count(sprites);
  hud_fps_x10=meter.fps_x10;hud_commands_s=meter.commands_s;
  as_hud_draw(counted_submit,8+(front^1),hud_fps_x10,hud_commands_s,hud_sprites,hud_layers);
  if(!gpu_wait())return 0;
 }
 fx_cycles=(unsigned)cycles()-start;if(fx_cycles>fx_max)fx_max=fx_cycles;
 if(loading){front^=1;return show_loading(t,ASTRILLA_FRAMES);}
 if(!gpu_rgb565_surface_submit(&c.target,1,layers,sprites)||!gpu_display_wait())return 0;
 front^=1;return 1;
}
static void status(void){uint64_t elapsed=cycles()-measure;
 printf("ASTRILLA frame=%u chapter=%u run=%u submitted=%u loops=%u elapsed_ms=%u fps_x100=%u lcd=%08x crc565=%08x uf=%u uf_total=%u line=%u invalid=%u badsprite=%u maxsprite=%u errors=%u crc=%08x fx_cycles=%u fx_max=%u rejected=%u bg_cycles=%u loading=%u live_fps_x10=%u gpu_cmds_s=%u gpu_cmd_frame=%u gpu_cmd_total=%u gpu_cmd_hi=%u gpu_done=%u hud_crc=%08x layers=%u sprites=%u" AS_GEOM_STATUS "\r\n",
 info.frame,info.chapter,run,submitted,loops,(unsigned)(elapsed/800000),(unsigned)(elapsed?(uint64_t)submitted*80000000000ULL/elapsed:0),
 (unsigned)DISPLAY[0x60/4],color_crc,(unsigned)(DISPLAY[7]-initial_underflows),(unsigned)DISPLAY[7],(unsigned)DISPLAY[0x64/4],
 (unsigned)DISPLAY[0x38/4],(unsigned)DISPLAY[0x48/4],(unsigned)DISPLAY[0x4c/4],errors,crc,fx_cycles,fx_max,gpu_v1_rejected(),bg_cycles,loading,hud_fps_x10,hud_commands_s,frame_commands,(unsigned)command_total,(unsigned)(command_total>>32),gpu_completed(),hud_crc,hud_layers,hud_sprites AS_GEOM_ARGS);
}
static void start(unsigned phase){resume_phase=phase;epoch=measure=cycles();submitted=loops=fx_max=0;loading=0;run=1;command_total=0;as_meter_reset(&meter,epoch);}
int main(void){
 clear_csr(NDS_MSTATUS,8);write_csr(NDS_MIE,0);ae350_dcache_flush_all();ae350_icache_invalidate_all();
 __asm__ volatile("fence iorw,iorw\n.word 0x0000100f":::"memory");
 const unsigned div=(80000000UL+8UL*115200)/(16UL*115200);
 AE350_UART2->LCR=0x83;AE350_UART2->DLL=div&255;AE350_UART2->DLM=div>>8;AE350_UART2->LCR=3;AE350_UART2->FCR=7;
 const uint32_t *header=(const uint32_t *)ASTRILLA_BASE;
 // USB loads the *volatile DDR disk*, never the physical SD. Accept a staged
 // pack only after its identity/length/CRC pass. A firmware-only reload can
 // reuse the already verified resident pack.
 const uint32_t *stage=(const uint32_t *)0x08000000UL;
 ae350_dcache_invalidate_range(0x08000000UL,ASTRILLA_BYTES);
 if(stage[0]==0x41535452&&stage[1]==1&&stage[2]==ASTRILLA_BYTES&&stage[3]==ASTRILLA_CRC){
  if(crc32((const uint8_t *)stage+1024,ASTRILLA_BYTES-1024)!=ASTRILLA_CRC){printf("ASTRILLA STAGE FAIL\r\n");for(;;){}}
  memcpy((void *)ASTRILLA_BASE,stage,ASTRILLA_BYTES);gpu_publish_surface(ASTRILLA_BASE,ASTRILLA_BYTES);
 }
 crc=crc32((const uint8_t *)(ASTRILLA_BASE+1024),ASTRILLA_BYTES-1024);
 if(header[0]!=0x41535452||header[1]!=1||header[2]!=ASTRILLA_BYTES||header[3]!=ASTRILLA_CRC||crc!=ASTRILLA_CRC){printf("ASTRILLA ASSETS FAIL crc=%08x expected=%08x\r\n",crc,ASTRILLA_CRC);for(;;){}}
#ifdef ASTRILLA_HW_GEOMETRY
 if(!gpu_geom_supported()||!as3_hw_prepare((uint8_t *)AS3_HW_BASE)){printf("ASTRILLA GEOMETRY FAIL\r\n");for(;;){}}
 gpu_publish_surface(AS3_HW_BASE,AS3_HW_BYTES);
#endif
 if(!gpu_blit_init()||!gpu_v1_supported()){printf("ASTRILLA GPU FAIL\r\n");for(;;){}}
 gpu_v1_context c;gpu_v1_init(&c,gpu_submit);gpu_v1_invalidate(&c);
 if(!gpu_wait())return 1;
 gpu_font_write(32*16,as_hud_font,sizeof(as_hud_font));
 for(unsigned i=0;i<256;++i)DISPLAY[0x100+i]=((const uint32_t *)ASTRILLA_PALETTE)[i];
 if(!show_loading(0,AS_CACHE_FRAMES)){printf("ASTRILLA LOADING FAIL\r\n");for(;;){}}
 prepare_backgrounds();
 if(DISPLAY[0]!=0x47505531||!present(0)){printf("ASTRILLA DISPLAY FAIL\r\n");for(;;){}}
 initial_underflows=DISPLAY[7];DISPLAY[0x2c/4]=0;start(0);
 printf("ASTRILLA READY R1 " AS_GPU_NAME " core=800MHz duration=300 battle=30 assets=%u crc=%08x autoplay=1\r\n",(unsigned)ASTRILLA_BYTES,crc);
 for(;;){
  if(AE350_UART2->LSR&1U){unsigned char command=AE350_UART2->RBR;
   if(command=='?')printf("ASTRILLA R1 AUTOPLAY " AS_GPU_NAME " core=800MHz duration=300 battle=30\r\n");
   else if(command=='P'){run=0;as_meter_reset(&meter,cycles());if(!loading&&!present(frame))++errors;printf("ASTRILLA PAUSED\r\n");}
   else if(command=='L'){run=0;loading=1;fx_max=0;if(!show_loading(0,ASTRILLA_FRAMES))++errors;printf("ASTRILLA LOADING\r\n");}
   else if(command=='G'||command=='R'){start(command=='R'?0:frame);printf("ASTRILLA AUTO\r\n");}
   else if(command=='S')status();
   else if(command=='C')printf("ASTRILLA CACHE ctl=%08x cfg=%08x ilm=%08x dlm=%08x\r\n",(unsigned)read_csr(NDS_MCACHE_CTL),(unsigned)read_csr(NDS_MDCM_CFG),(unsigned)read_csr(NDS_MILMB),(unsigned)read_csr(NDS_MDLMB));
   else if(command=='B'){run=0;unsigned b=(unsigned)cycles(),sum=0;const volatile uint32_t *p=(const volatile uint32_t *)ASTRILLA_COSMOS;
    for(unsigned i=0;i<48000;++i)sum+=p[i];
    unsigned reads=(unsigned)cycles()-b;
    b=(unsigned)cycles();for(unsigned i=0;i<48000;++i)sum+=p[i&1023];unsigned hot=(unsigned)cycles()-b;
    b=(unsigned)cycles();for(unsigned i=0;i<48000;++i)sum+=p[0];unsigned same=(unsigned)cycles()-b;
    b=(unsigned)cycles();volatile uint32_t *dst=(volatile uint32_t *)GPU_PAGE_ADDR(7);for(unsigned i=0;i<48000;++i)dst[i]=p[i];unsigned cp=(unsigned)cycles()-b;
    b=(unsigned)cycles();gpu_publish_surface(GPU_PAGE_ADDR(7),192000);unsigned pub=(unsigned)cycles()-b;
    b=(unsigned)cycles();astrilla_background(0,(uint16_t *)AS_BG,(const uint8_t *)ASTRILLA_BASE);unsigned bg=(unsigned)cycles()-b;
    printf("ASTRILLA BENCH reads=%u hot=%u same=%u copy=%u publish=%u bg=%u sum=%08x\r\n",reads,hot,same,cp,pub,bg,sum);}
   else if(command=='T'){unsigned char a,b;if(get_timeout(&a)&&get_timeout(&b)){run=0;as_meter_reset(&meter,cycles());frame=((unsigned)b*256+a)%ASTRILLA_FRAMES;
    if(!present(frame))++errors;
    unsigned f=DISPLAY[6];uint64_t limit=cycles()+800000000ULL;
    while((unsigned)(DISPLAY[6]-f)<3){if(cycles()>limit){++errors;break;}}
    ae350_dcache_invalidate_range(GPU_PAGE_ADDR(front),192000);color_crc=crc32((const uint8_t *)GPU_PAGE_ADDR(front),192000);
    ae350_dcache_invalidate_range(GPU_PAGE_ADDR(8+front),25600);hud_crc=crc32((const uint8_t *)GPU_PAGE_ADDR(8+front),25600);status();}}
   else if(command=='E'){unsigned char a,b;if(get_timeout(&a)&&get_timeout(&b)){unsigned n=(unsigned)a+(unsigned)b*256;while(n--){unsigned char v;if(!get_timeout(&v)){++errors;break;}put(v);}}}
  }
  if(run){uint64_t ticks=(cycles()-epoch)*ASTRILLA_HZ/800000000ULL+resume_phase;loops=(unsigned)(ticks/ASTRILLA_FRAMES);frame=(unsigned)(ticks%ASTRILLA_FRAMES);
   if(!present(frame)){++errors;run=0;printf("ASTRILLA DISPLAY FAIL\r\n");}
   else{++submitted;as_meter_frame(&meter,cycles(),frame_commands);}}
 }
}
