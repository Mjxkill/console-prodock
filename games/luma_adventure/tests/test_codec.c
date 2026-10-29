/* Independent liblz4 compressor verifies the bounded runtime decoder. */
#include "../src/video.c"
#include <assert.h>
#include <lz4.h>
#include <lz4hc.h>
int main(void){
 unsigned seed=0x4c554d41;unsigned char *input=malloc(131072),*output=malloc(131072);char *compressed=malloc(LZ4_compressBound(131072));assert(input&&output&&compressed);
 for(unsigned trial=0;trial<600;trial++){
  unsigned size=1+(trial*7907U)%131072,period=1+trial%127;
  for(unsigned i=0;i<size;i++){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;input[i]=(trial%4==0)?(unsigned char)seed:(trial%4==1)?42:(unsigned char)((i%period)*37);}
  int packed=trial%2?LZ4_compress_HC((const char *)input,compressed,(int)size,LZ4_compressBound((int)size),12):LZ4_compress_default((const char *)input,compressed,(int)size,LZ4_compressBound((int)size));assert(packed>0);assert(!unpack((unsigned char *)compressed,(size_t)packed,output,size));assert(!memcmp(input,output,size));
  assert(unpack((unsigned char *)compressed,(size_t)packed-1,output,size)<0);assert(unpack((unsigned char *)compressed,(size_t)packed,output,size-1)<0);
 }
 const unsigned char invalid[][4]={{0,0,0,0},{0,1,0,0},{0xf0,255,255,0}};for(unsigned i=0;i<3;i++)assert(unpack(invalid[i],4,output,32)<0);
 free(input);free(output);free(compressed);puts("LUMA_CODEC_PASS 600 independent compressed streams, truncation/capacity/offset rejection");return 0;
}
