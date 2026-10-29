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
static unsigned char *patch(const unsigned char *p,unsigned size,const char *base,unsigned *bytes,unsigned *sum) {
 /* Header: magic, base size/CRC, output size/CRC, record count.
  * Record: source offset (UINT32_MAX = literal), length, optional bytes. */
 if(size<24)return NULL;uint32_t h[6];memcpy(h,p,24);
 if(h[0]!=0x3150334c||!h[1]||h[1]>(16u<<20)||!h[3]||h[3]>(16u<<20)||h[5]>(size-24)/8)return NULL;
 FILE *f=fopen(base,"rb");if(!f)return NULL;
 unsigned char *old=malloc(h[1]),*out=malloc(h[3]);int valid=old&&out&&fread(old,1,h[1],f)==h[1]&&fgetc(f)==EOF&&crc(old,h[1])==h[2];fclose(f);
 size_t at=24,n=0;
 if(valid)for(unsigned i=0;i<h[5];i++) {
  if(size-at<8) {valid=0;break;}uint32_t op[2];memcpy(op,p+at,8);at+=8;
  unsigned src=op[0],len=op[1];if(!len||len>h[3]-n) {valid=0;break;}
  if(src==UINT32_MAX) {if(len>size-at) {valid=0;break;}memcpy(out+n,p+at,len);at+=len;}
  else {if(src>h[1]||len>h[1]-src) {valid=0;break;}memcpy(out+n,old+src,len);}
  n+=len;
 }
 free(old);if(!valid||at!=size||n!=h[3]||crc(out,n)!=h[4]) {free(out);return NULL;}
 *bytes=h[3];*sum=h[4];return out;
}
int main(int argc,char **argv) {
 if(argc<2)return 2;int is_patch=!strcmp(argv[1],"patch");
 if(argc!=(is_patch?7:6)||(strcmp(argv[1],"unpack")&&strcmp(argv[1],"pixels")&&strcmp(argv[1],"verify")&&strcmp(argv[1],"hud")&&!is_patch))return 2;
 char *end;unsigned bytes=strtoul(argv[4],&end,0);if(*end)return 2;unsigned sum=strtoul(argv[5],&end,16);if(*end)return 2;
 unsigned char *data=load(argv[2],bytes,sum);if(!data) {fputs("LUMA3D_HELPER_REJECT\n",stderr);return 1;}
 if(is_patch) {unsigned char *output=patch(data,bytes,argv[6],&bytes,&sum);free(data);data=output;if(!data) {fputs("LUMA3D_PATCH_REJECT\n",stderr);return 1;}}
 int rc=1;
 if(!strcmp(argv[1],"verify")) {printf("LUMA3D_VERIFY_OK bytes=%u crc32=%08x\n",bytes,sum);rc=0;}
 else if(!strcmp(argv[1],"unpack")||is_patch) {
  if(strncmp(argv[3],"/tmp/",5)||strchr(argv[3]+5,'/'))goto done;
  int fd=open(argv[3],O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0) {perror("unpack output");goto done;}
  size_t pos=0;while(pos<bytes) {ssize_t n=write(fd,data+pos,bytes-pos);if(n<=0)break;pos+=(size_t)n;}
  int closed=close(fd);if(pos!=bytes||closed) {unlink(argv[3]);goto done;}
  printf("LUMA3D_UNPACK_OK bytes=%u crc32=%08x\n",bytes,sum);rc=0;
 } else if(!strcmp(argv[1],"hud")) {
  unsigned bank=!strcmp(argv[3],"bank20")?20:!strcmp(argv[3],"bank21")?21:0;
  if(!bank||!bytes||bytes>800*300||bytes%800)goto done;
  int fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);struct prodock_info info;
  if(fd<0)goto done;
  if(ioctl(fd,PRODOCK_INFO,&info)||info.width!=800||info.height!=480||info.errors||info.faulted) {close(fd);goto done;}
  unsigned char *memory=mmap(NULL,22U<<20,PROT_READ,MAP_SHARED,fd,0);
  if(memory==MAP_FAILED) {close(fd);goto done;}
  unsigned char *actual=malloc(bytes);unsigned mismatches=0;
  if(!actual) {munmap(memory,22U<<20);close(fd);goto done;}
  for(unsigned i=0;i<bytes/4;i++) {
   uint32_t word=*(const volatile uint32_t *)(memory+(bank<<20)+i*4);memcpy(actual+i*4,&word,4);
  }
  for(unsigned i=0;i<bytes;i++)if(actual[i]!=data[i])mismatches++;
  printf("LUMA3D_HUD bank=%u bytes=%u mismatch=%u actual_crc=%08x expected_crc=%08x\n",bank,bytes,mismatches,crc(actual,bytes),sum);
  free(actual);munmap(memory,22U<<20);close(fd);rc=mismatches!=0;
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
