// Autonomous Luma demo; downloaded in writable ILM on the unmodified R31 GPU.
#include <stdio.h>
#include "ae350.h"
#include "cache.h"
#include "luma_fx_scene.h"
#define DISPLAY ((volatile uint32_t *)0xe9000000UL)
static gpu_layer layers[16];
static gpu_sprite sprites[64];
static luma_info info;
static unsigned frame=LUMA_FX_START,run=1,submitted,errors,loops,initial_underflows,crc;
static unsigned fx_front,fx_cycles,fx_max,fx_frames,color_crc;
static uint32_t palette[256];
static unsigned long long start_cycles;
static unsigned long long cycles(void){unsigned hi,lo,again;do{__asm__ volatile("rdcycleh %0":"=r"(hi));__asm__ volatile("rdcycle %0":"=r"(lo));__asm__ volatile("rdcycleh %0":"=r"(again));}while(hi!=again);return ((unsigned long long)hi<<32)|lo;}
static void put(unsigned c){while(!(AE350_UART2->LSR&0x20U)){}AE350_UART2->THR=c;}
static int get_timeout(unsigned char *c){unsigned long long limit=cycles()+800000000ULL;while(!(AE350_UART2->LSR&1U))if(cycles()>limit)return 0;*c=AE350_UART2->RBR;return 1;}
static uint32_t crc32(const uint8_t *p,unsigned n){uint32_t c=~0U;for(unsigned i=0;i<n;++i){c^=p[i];for(unsigned bit=0;bit<8;++bit)c=(c>>1)^(0xedb88320U&(0U-(c&1)));}return ~c;}
long except_handler(long cause,long epc){const char *s="\r\nLUMA TRAP ";while(*s)put(*s++);unsigned v[3]={(unsigned)cause,(unsigned)epc,read_csr(NDS_MTVAL)};for(unsigned i=0;i<3;++i){for(int b=28;b>=0;b-=4)put("0123456789abcdef"[(v[i]>>b)&15]);put(' ');}for(;;){}}
static int present(unsigned t){
 color_crc=0;
 if(!gpu_display_wait())return 0;
 unsigned fx=t>=LUMA_FX_START;
 gpu_v1_context context;gpu_v1_init(&context,gpu_submit);
 if(fx){unsigned begin=(unsigned)cycles();
  luma_fx_layers(t-LUMA_FX_START,layers,sprites,&info);
  if(!luma_fx_render(&context,t-LUMA_FX_START,fx_front^1U)||!gpu_wait()||gpu_v1_rejected())return 0;
  fx_cycles=(unsigned)cycles()-begin;if(fx_cycles>fx_max)fx_max=fx_cycles;++fx_frames;
 }else luma_scene(t,layers,sprites,&info);
 for(unsigned i=0;i<256;++i)DISPLAY[0x100+i]=luma_color(palette[i],i,info.frame,info.light);
 if(fx){if(!gpu_rgb565_surface_submit(&context.target,1,layers,sprites)||!gpu_display_wait())return 0;fx_front^=1U;return 1;}
 return gpu_scene_submit(layers,sprites)&&gpu_display_wait();
}
static void status(void){unsigned long long elapsed=cycles()-start_cycles;unsigned fps=elapsed?(unsigned)((unsigned long long)submitted*80000000000ULL/elapsed):0;
 printf("LUMA frame=%u run=%u submitted=%u loops=%u fps_x100=%u hash=%08x lcd=%08x crc565=%08x uf=%u uf_total=%u line=%u invalid=%u badsprite=%u maxsprite=%u cache=%u errors=%u crc=%08x fx_cycles=%u fx_max=%u fx_frames=%u rejected=%u\r\n",info.frame,run,submitted,loops,fps,(unsigned)DISPLAY[8],(unsigned)DISPLAY[0x60/4],color_crc,(unsigned)(DISPLAY[7]-initial_underflows),(unsigned)DISPLAY[7],(unsigned)DISPLAY[0x64/4],(unsigned)DISPLAY[0x38/4],(unsigned)DISPLAY[0x48/4],(unsigned)DISPLAY[0x4c/4],(unsigned)DISPLAY[0x50/4],errors,crc,fx_cycles,fx_max,fx_frames,gpu_v1_rejected());
}
int main(void){
 clear_csr(NDS_MSTATUS,8);write_csr(NDS_MIE,0);
 ae350_dcache_flush_all();ae350_icache_invalidate_all();
 __asm__ volatile("fence iorw,iorw\n.word 0x0000100f":::"memory");
 const unsigned div=(80000000UL+8UL*115200)/(16UL*115200);
 AE350_UART2->LCR=0x83;AE350_UART2->DLL=div&255;AE350_UART2->DLM=div>>8;AE350_UART2->LCR=3;AE350_UART2->FCR=7;
 const uint32_t *header=(const uint32_t *)LUMA_BASE;
 crc=crc32((const uint8_t *)(LUMA_BASE+1024),LUMA_BYTES-1024);
 if(header[0]!=0x414d554c||header[1]!=1||header[2]!=LUMA_BYTES||header[3]!=LUMA_CRC||crc!=LUMA_CRC){printf("LUMA ASSETS FAIL crc=%08x expected=%08x\r\n",crc,LUMA_CRC);for(;;){}}
 for(unsigned i=0;i<256;++i)palette[i]=((const uint32_t *)LUMA_PALETTE)[i];
 gpu_v1_context context;gpu_v1_init(&context,gpu_submit);
 if(!gpu_blit_init()||!gpu_v1_supported()){printf("LUMA V1 FAIL\r\n");for(;;){}}
 gpu_v1_invalidate(&context);
 if(!luma_fx_prepare(&context)||!gpu_wait()||DISPLAY[0]!=0x47505531||!present(frame)){printf("LUMA GPU FAIL\r\n");for(;;){}}
 initial_underflows=DISPLAY[7];DISPLAY[0x2c/4]=0;start_cycles=cycles();
 printf("LUMA READY R31 ILM core=800MHz assets=%u crc=%08x autoplay=1\r\n",(unsigned)LUMA_BYTES,crc);
 for(;;){
  if(AE350_UART2->LSR&1U){unsigned char c=AE350_UART2->RBR;
   if(c=='?')printf("LUMA R2 AUTOPLAY FX R31 core=800MHz\r\n");
   else if(c=='P'){run=0;printf("LUMA PAUSED\r\n");}
   else if(c=='G'){run=1;start_cycles=cycles();submitted=0;printf("LUMA AUTO\r\n");}
   else if(c=='S')status();
   else if(c=='T'){unsigned char a,b;if(get_timeout(&a)&&get_timeout(&b)){run=0;frame=((unsigned)b*256+a)%LUMA_FRAMES;if(!present(frame))++errors;unsigned f=DISPLAY[6];while((unsigned)(DISPLAY[6]-f)<3){}if(frame>=LUMA_FX_START){unsigned long base=GPU_PAGE_ADDR(fx_front);ae350_dcache_invalidate_range(base,LUMA_FX_STRIDE*240);color_crc=crc32((const uint8_t *)base,LUMA_FX_STRIDE*240);}status();}}
   else if(c=='E'){unsigned char a,b;if(get_timeout(&a)&&get_timeout(&b)){unsigned n=(unsigned)a+(unsigned)b*256;while(n--){unsigned char v;if(!get_timeout(&v)){++errors;break;}put(v);}}}
  }
  if(run){frame=(frame+1)%LUMA_FRAMES;if(!frame)++loops;if(!present(frame)){++errors;run=0;printf("LUMA DISPLAY FAIL\r\n");}++submitted;}
 }
}
