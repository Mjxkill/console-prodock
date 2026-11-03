// Autonomous Orbital demo; downloaded in writable ILM on the unmodified R31 GPU.
#include <stdio.h>
#include "ae350.h"
#include "cache.h"
#include "orbital_scene.h"
#define DISPLAY ((volatile uint32_t *)0xe9000000UL)
static gpu_layer layers[16];
static gpu_sprite sprites[64];
static orb_info info;
static unsigned frame=0,run=1,submitted,errors,loops,initial_underflows,crc;
static unsigned fx_front,fx_cycles,fx_max,fx_frames,color_crc;
static uint32_t palette[256];
static unsigned long long start_cycles;
static unsigned long long cycles(void){unsigned hi,lo,again;do{__asm__ volatile("rdcycleh %0":"=r"(hi));__asm__ volatile("rdcycle %0":"=r"(lo));__asm__ volatile("rdcycleh %0":"=r"(again));}while(hi!=again);return ((unsigned long long)hi<<32)|lo;}
static void put(unsigned c){while(!(AE350_UART2->LSR&0x20U)){}AE350_UART2->THR=c;}
static int get_timeout(unsigned char *c){unsigned long long limit=cycles()+800000000ULL;while(!(AE350_UART2->LSR&1U))if(cycles()>limit)return 0;*c=AE350_UART2->RBR;return 1;}
static uint32_t crc32(const uint8_t *p,unsigned n){uint32_t c=~0U;for(unsigned i=0;i<n;++i){c^=p[i];for(unsigned bit=0;bit<8;++bit)c=(c>>1)^(0xedb88320U&(0U-(c&1)));}return ~c;}
long except_handler(long cause,long epc){const char *s="\r\nORBITAL TRAP ";while(*s)put(*s++);unsigned v[3]={(unsigned)cause,(unsigned)epc,read_csr(NDS_MTVAL)};for(unsigned i=0;i<3;++i){for(int b=28;b>=0;b-=4)put("0123456789abcdef"[(v[i]>>b)&15]);put(' ');}for(;;){}}
static int hud_phase[2]={-1,-1};   // phase held by each HUD page, -1: zeroes
static unsigned bench_count;
static void bench_emit(const gpu_command *c){(void)c;++bench_count;}
// Time one frame into the back page without presenting it: CPU preparation alone, then CPU+GPU.
static void bench(unsigned t,unsigned mask){
 gpu_v1_context context;orb_skip=mask;bench_count=0;gpu_v1_init(&context,bench_emit);unsigned begin=(unsigned)cycles();
 int ok=orbital_render(&context,t,fx_front^1U);unsigned cpu=(unsigned)cycles()-begin;
 gpu_v1_init(&context,gpu_submit);begin=(unsigned)cycles();ok=ok&&orbital_render(&context,t,fx_front^1U)&&gpu_wait();unsigned total=(unsigned)cycles()-begin;orb_skip=0;
 printf("ORBITAL BENCH frame=%u mask=%u ok=%d commands=%u cpu=%u total=%u rejected=%u\r\n",t,mask,ok,bench_count,cpu,total,gpu_v1_rejected());
}
// Micro-bench (command M): n quads w*h with material flags, alpha a; kind 1 copy, 2 Z clear, 3 colour clear.
static void micro(unsigned kind,unsigned flags,unsigned alpha,unsigned w,unsigned h,unsigned n){
 gpu_v1_context c;gpu_v1_init(&c,gpu_submit);gpu_target dst={GPU_PAGE_ADDR(fx_front^1U),GPU_PAGE_ADDR(2),400,240,800,800},sky={ORBITAL_SKY,0,512,256,1024,1024};
 int ok=gpu_v1_target(&c,&dst)&&gpu_v1_scissor(&c,0,0,400,240)&&gpu_v1_clear(&c,2,0,65535,0,0,400,240)&&gpu_wait();
 gpu_texture_level tex=flags&256?(gpu_texture_level){ORBITAL_DRONE0,128,128,256,GPU_ARGB4444,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0}:(gpu_texture_level){ORBITAL_TEX_PANEL,128,128,256,GPU_RGB565,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};
 gpu_material m={flags&255,alpha,0x4aab,256,256,256,0,0,0};ok=ok&&gpu_v1_texture(&c,&tex)&&gpu_v1_material(&c,&m)&&gpu_wait();
 unsigned begin=(unsigned)cycles();
 for(unsigned i=0;i<n&&ok;++i){int z=60000-(int)i*100,tw=tex.width-1;
  if(kind==1)ok=gpu_v1_copy(&c,&sky,56,8,0,0,w,h);
  else if(kind==2)ok=gpu_v1_clear(&c,2,0,65535,0,0,w,h);
  else if(kind==3)ok=gpu_v1_clear(&c,1,0x1234,0,0,0,w,h);
  else if(kind==4)ok=gpu_v1_clear(&c,3,0x1234+i,40000,(int)(i%200),(int)(i%100),w,h);
  else{gpu_vertex v[4]={{0,0,0,0,z,65536,256,200,150},{(int)w,0,tw,0,z,65536,200,256,150},{(int)w,(int)h,tw,tw,z,40000,150,200,256},{0,(int)h,0,tw,z,40000,256,256,256}};ok=gpu_v1_quad(&c,v);}}
 ok=ok&&gpu_wait();unsigned total=(unsigned)cycles()-begin;
 printf("ORBITAL MICRO kind=%u flags=%u alpha=%u w=%u h=%u n=%u ok=%d total=%u rejected=%u\r\n",kind,flags,alpha,w,h,n,ok,total,gpu_v1_rejected());
}
static int present(unsigned t){
 color_crc=0;if(!gpu_display_wait())return 0;
 gpu_v1_context context;gpu_v1_init(&context,gpu_submit);unsigned begin=(unsigned)cycles();
 unsigned hud=ORB_HUD_PAGE+(fx_front^1U);orbital_layers(t,hud,layers,sprites,&info);
 // Indexed 2D commands of the HUD page share the FIFO with the 3D frame.
 if(!orbital_render(&context,t,fx_front^1U))return 0;
 orbital_hud(t,hud_phase[hud-ORB_HUD_PAGE],hud,gpu_submit);hud_phase[hud-ORB_HUD_PAGE]=(int)t;
 if(!gpu_wait()||gpu_v1_rejected())return 0;
 for(unsigned i=240;i<256;++i)DISPLAY[0x100+i]=orbital_palette(t,i,palette[i]);
 fx_cycles=(unsigned)cycles()-begin;if(fx_cycles>fx_max)fx_max=fx_cycles;++fx_frames;
 if(!gpu_rgb565_surface_submit(&context.target,1,layers,sprites)||!gpu_display_wait())return 0;
 fx_front^=1U;return 1;
}
static void status(void){unsigned long long elapsed=cycles()-start_cycles;unsigned fps=elapsed?(unsigned)((unsigned long long)submitted*80000000000ULL/elapsed):0;
 printf("ORBITAL frame=%u run=%u submitted=%u loops=%u fps_x100=%u hash=%08x lcd=%08x crc565=%08x uf=%u uf_total=%u line=%u invalid=%u badsprite=%u maxsprite=%u cache=%u errors=%u crc=%08x fx_cycles=%u fx_max=%u fx_frames=%u rejected=%u\r\n",info.frame,run,submitted,loops,fps,(unsigned)DISPLAY[8],(unsigned)DISPLAY[0x60/4],color_crc,(unsigned)(DISPLAY[7]-initial_underflows),(unsigned)DISPLAY[7],(unsigned)DISPLAY[0x64/4],(unsigned)DISPLAY[0x38/4],(unsigned)DISPLAY[0x48/4],(unsigned)DISPLAY[0x4c/4],(unsigned)DISPLAY[0x50/4],errors,crc,fx_cycles,fx_max,fx_frames,gpu_v1_rejected());
}
int main(void){
 clear_csr(NDS_MSTATUS,8);write_csr(NDS_MIE,0);
 ae350_dcache_flush_all();ae350_icache_invalidate_all();
 __asm__ volatile("fence iorw,iorw\n.word 0x0000100f":::"memory");
 const unsigned div=(80000000UL+8UL*115200)/(16UL*115200);
 AE350_UART2->LCR=0x83;AE350_UART2->DLL=div&255;AE350_UART2->DLM=div>>8;AE350_UART2->LCR=3;AE350_UART2->FCR=7;
 const uint32_t *header=(const uint32_t *)ORBITAL_BASE;
 crc=crc32((const uint8_t *)(ORBITAL_BASE+1024),ORBITAL_BYTES-1024);
 if(header[0]!=0x4f524249||header[1]!=1||header[2]!=ORBITAL_BYTES||header[3]!=ORBITAL_CRC||crc!=ORBITAL_CRC){printf("ORBITAL ASSETS FAIL crc=%08x expected=%08x\r\n",crc,ORBITAL_CRC);for(;;){}}
 for(unsigned i=0;i<256;++i)palette[i]=((const uint32_t *)ORBITAL_PALETTE)[i];
 gpu_v1_context context;gpu_v1_init(&context,gpu_submit);
 if(!gpu_blit_init()||!gpu_v1_supported()){printf("ORBITAL V1 FAIL\r\n");for(;;){}}
 gpu_v1_invalidate(&context);
 // The two HUD pages start empty: the 2D engine only redraws what changes.
 for(unsigned page=0;page<2;++page){gpu_command clear=gpu_make_command(GPU_FILL,ORB_HUD_PAGE+page,0,0,0,800,480,0,0,0,0);gpu_submit(&clear);}
 if(!gpu_wait()){printf("ORBITAL HUD FAIL\r\n");for(;;){}}
 for(unsigned i=0;i<256;++i)DISPLAY[0x100+i]=palette[i];
 if(DISPLAY[0]!=0x47505531||!present(frame)){printf("ORBITAL GPU FAIL\r\n");for(;;){}}
 initial_underflows=DISPLAY[7];DISPLAY[0x2c/4]=0;start_cycles=cycles();
 printf("ORBITAL READY R31 ILM core=800MHz assets=%u crc=%08x autoplay=1\r\n",(unsigned)ORBITAL_BYTES,crc);
 for(;;){
  if(AE350_UART2->LSR&1U){unsigned char c=AE350_UART2->RBR;
   if(c=='?')printf("ORBITAL R6 AUTOPLAY FPS R31 core=800MHz\r\n");
   else if(c=='P'){run=0;printf("ORBITAL PAUSED\r\n");}
   else if(c=='G'){run=1;start_cycles=cycles();submitted=0;printf("ORBITAL AUTO\r\n");}
   else if(c=='S')status();
   else if(c=='T'){unsigned char a,b;if(get_timeout(&a)&&get_timeout(&b)){run=0;frame=((unsigned)b*256+a)%ORBITAL_FRAMES;if(!present(frame))++errors;unsigned f=DISPLAY[6];while((unsigned)(DISPLAY[6]-f)<3){}{unsigned long base=GPU_PAGE_ADDR(fx_front);ae350_dcache_invalidate_range(base,ORBITAL_STRIDE*240);color_crc=crc32((const uint8_t *)base,ORBITAL_STRIDE*240);}status();}}
   else if(c=='B'){unsigned char a,b,m;if(get_timeout(&a)&&get_timeout(&b)&&get_timeout(&m)){run=0;bench(((unsigned)b*256+a)%ORBITAL_FRAMES,m);}}
   else if(c=='M'){unsigned char q[9];unsigned k=0;while(k<9&&get_timeout(&q[k]))++k;if(k==9){run=0;micro(q[0],q[1]|((unsigned)q[2]<<8),q[3]|((unsigned)q[4]<<8),q[5]|((unsigned)q[6]<<8),q[7],q[8]);}}
   else if(c=='E'){unsigned char a,b;if(get_timeout(&a)&&get_timeout(&b)){unsigned n=(unsigned)a+(unsigned)b*256;while(n--){unsigned char v;if(!get_timeout(&v)){++errors;break;}put(v);}}}
  }
  if(run){frame=(frame+1)%ORBITAL_FRAMES;if(!frame)++loops;if(!present(frame)){++errors;run=0;printf("ORBITAL DISPLAY FAIL\r\n");}++submitted;}
 }
}
