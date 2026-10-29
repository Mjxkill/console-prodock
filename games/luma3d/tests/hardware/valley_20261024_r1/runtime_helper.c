#define _POSIX_C_SOURCE 200809L
#include "prodock-uapi.h"
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
/* Same bounded raw LZ4 block format used by LUMA2D assets. */
static int unpack(const unsigned char *s,size_t size,unsigned char *out,size_t cap) {
 size_t p=0,n=0;while(p<size) {unsigned t=s[p++];size_t lit=t>>4,match=(t&15)+4;
  if(lit==15) {unsigned b;do {if(p>=size)return 0;b=s[p++];lit+=b;if(lit>cap-n)return 0;}while(b==255);}
  if(lit>size-p||lit>cap-n)return 0;memcpy(out+n,s+p,lit);p+=lit;n+=lit;if(p==size)return n==cap;
  if(size-p<2)return 0;unsigned off=s[p]|(unsigned)s[p+1]<<8;p+=2;if(!off||off>n)return 0;
  if((t&15)==15) {unsigned b;do {if(p>=size)return 0;b=s[p++];match+=b;if(match>cap-n)return 0;}while(b==255);}
  if(match>cap-n)return 0;size_t d=off;while(match) {size_t c=match<d?match:d;memcpy(out+n,out+n-d,c);n+=c;match-=c;if(d<65536)d*=2;}
 }return n==cap;
}
static uint32_t crc(const unsigned char *p,size_t n) {uint32_t c=~0u;while(n--) {c^=*p++;for(int i=0;i<8;i++)c=(c>>1)^(0xedb88320u&-(c&1));}return ~c;}
static unsigned char *load(const char *path,unsigned bytes,unsigned checksum) {
 FILE *f=fopen(path,"rb");if(!f)return NULL;unsigned h[4];unsigned char *src=NULL,*dst=NULL;
 if(fread(h,1,16,f)!=16||h[0]!=0x4c345a4c||h[1]!=bytes||h[3]!=checksum||!bytes||bytes>(16u<<20)||!h[2]||h[2]>(16u<<20))goto bad;
 src=malloc(h[2]);dst=malloc(bytes);if(!src||!dst||fread(src,1,h[2],f)!=h[2]||fgetc(f)!=EOF||!unpack(src,h[2],dst,bytes)||crc(dst,bytes)!=checksum)goto bad;
 fclose(f);free(src);return dst;
bad: fclose(f);free(src);free(dst);return NULL;
}
int main(int argc,char **argv) {
 if(argc!=6||(strcmp(argv[1],"unpack")&&strcmp(argv[1],"pixels")))return 2;
 char *end;unsigned bytes=strtoul(argv[4],&end,0);if(*end)return 2;unsigned sum=strtoul(argv[5],&end,16);if(*end)return 2;
 unsigned char *data=load(argv[2],bytes,sum);if(!data) {fputs("LUMA3D_HELPER_REJECT\n",stderr);return 1;}
 int rc=1;
 if(!strcmp(argv[1],"unpack")) {
  if(strncmp(argv[3],"/tmp/",5)||strchr(argv[3]+5,'/'))goto done;
  int fd=open(argv[3],O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0) {perror("unpack output");goto done;}
  size_t pos=0;while(pos<bytes) {ssize_t n=write(fd,data+pos,bytes-pos);if(n<=0)break;pos+=(size_t)n;}
  int closed=close(fd);if(pos!=bytes||closed) {unlink(argv[3]);goto done;}
  printf("LUMA3D_UNPACK_OK bytes=%u crc32=%08x\n",bytes,sum);rc=0;
 } else {
  if(bytes!=400*240*2||strcmp(argv[3],"page0"))goto done;
  int fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);struct prodock_info info;
  if(fd<0)goto done;if(ioctl(fd,PRODOCK_INFO,&info)||info.width!=800||info.height!=480||info.errors||info.faulted) {close(fd);goto done;}
  unsigned char *memory=mmap(NULL,1<<20,PROT_READ,MAP_SHARED,fd,0);if(memory==MAP_FAILED) {close(fd);goto done;}
  unsigned mismatches=0;uint16_t *actual=malloc(bytes);if(!actual) {munmap(memory,1<<20);close(fd);goto done;}
  for(unsigned y=0;y<240;y++)for(unsigned x=0;x<400;x++) {
   unsigned a=*(const volatile uint16_t *)(memory+y*1600+x*2),e=((uint16_t *)data)[y*400+x];actual[y*400+x]=(uint16_t)a;
   if(a!=e) {if(mismatches<12)printf("LUMA3D_PIXEL_DIFF x=%u y=%u actual=%04x expected=%04x\n",x,y,a,e);mismatches++;}
  }
  printf("LUMA3D_PIXELS pixels=96000 mismatch=%u actual_crc=%08x expected_crc=%08x\n",mismatches,crc((unsigned char *)actual,bytes),sum);
  if(mismatches) {FILE *f=fopen("/tmp/luma3d-first.rgb565","wb");if(f) {fwrite(actual,1,bytes,f);fclose(f);}}
  free(actual);munmap(memory,1<<20);close(fd);rc=mismatches!=0;
 }
done:free(data);return rc;
}
