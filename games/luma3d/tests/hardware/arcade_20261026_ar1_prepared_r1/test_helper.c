/* Pure bounds + binary codec checks, no device open. */
#define main helper_main
#include "runtime_inspect.c"
#undef main
#include <assert.h>
int main(void){
 unsigned n;assert(number("31457280",0,&n)&&n==(30u<<20));assert(!number("4326424576",0,&n));assert(!number("-1",0,&n));assert(!number("",0,&n));assert(!number("12x",0,&n));
 assert(memory_region_valid(20u<<20,240000));assert(memory_region_valid(22u<<20,384000));
 assert(memory_region_valid(23u<<20,384000));assert(memory_region_valid(28u<<20,491520));
 assert(memory_region_valid(30u<<20,65536));assert(memory_region_valid((31u<<20)-4,4));
 assert(!memory_region_valid(0,4));assert(!memory_region_valid(24u<<20,4));
 assert(!memory_region_valid(27u<<20,4));assert(!memory_region_valid(31u<<20,4));
 assert(!memory_region_valid(32u<<20,4));assert(!memory_region_valid(30u<<20,2u<<20));
 assert(!memory_region_valid((32u<<20)-4,8));assert(!memory_region_valid(UINT32_MAX-3,8));
 assert(!memory_region_valid(30u<<20,0));assert(!memory_region_valid((30u<<20)+1,4));
 assert(!memory_region_valid(30u<<20,5));
 unsigned char a[8]={0},literal[]={0x40,1,2,3,4},match[]={0x10,7,1,0};
 assert(unpack(literal,sizeof(literal),a,4)&&a[0]==1&&a[3]==4);
 assert(!unpack(literal,sizeof(literal),a,3));assert(!unpack(literal,2,a,4));
 assert(unpack(match,sizeof(match),a,5));for(unsigned i=0;i<5;i++)assert(a[i]==7);
 match[2]=0;assert(!unpack(match,sizeof(match),a,5));
 puts("HELPER_BOUNDS_CODEC_PASS");return 0;
}
