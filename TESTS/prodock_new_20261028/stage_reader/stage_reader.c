#define _GNU_SOURCE
/* Read-only reserved-VRAM staging reader for the pinned FM4A image.
 * It sends no GPU ioctl, maps PROT_READ only, and creates only a fresh flat
 * /tmp output after BOTH packed and unpacked CRCs pass. Driver release may
 * restore the console framebuffer; no game may own the GPU during this boot. */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include "stage_identity.h"
#include "lz4_unpack.h"
#define STAGE_OFFSET 0x03800000u
#define STAGE_LIMIT 0x05600000u
static uint32_t crc32(const unsigned char *p,size_t n)
{
    uint32_t c=~0u;
    while(n--) {c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&-(c&1));}
    return ~c;
}
static uint32_t get32(const unsigned char *p)
{return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static int output_ok(const char *p)
{
    if(strncmp(p,"/tmp/",5)||!p[5]||strlen(p)>200)return 0;
    for(p+=5;*p;p++)if(!((*p>='a'&&*p<='z')||(*p>='0'&&*p<='9')||*p=='-'||*p=='_'||*p=='.'))return 0;
    return 1;
}
/* A failing decoder/CRC never creates output; a failing write removes only
 * the file this process successfully created O_EXCL. Existing files survive. */
static int extract_stage(const unsigned char *src,size_t size,const char *output)
{
    if(!output_ok(output)||size!=PACKED_BYTES||crc32(src,size)!=PACKED_CRC)return 2;
    if(size<16||get32(src)!=0x4c345a4cu||get32(src+4)!=ELF_BYTES||get32(src+8)!=size-16||get32(src+12)!=ELF_CRC)return 3;
    unsigned char *elf=malloc(ELF_BYTES);if(!elf)return 4;
    if(!unpack(src+16,size-16,elf,ELF_BYTES)||crc32(elf,ELF_BYTES)!=ELF_CRC){free(elf);return 5;}
    int fd=open(output,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0700);
    if(fd<0){free(elf);return 6;}
    size_t pos=0;
    while(pos<ELF_BYTES){ssize_t n=write(fd,elf+pos,ELF_BYTES-pos);if(n<0&&errno==EINTR)continue;if(n<=0)break;pos+=(size_t)n;}
    free(elf);int synced=pos==ELF_BYTES?fsync(fd):-1;int closed=close(fd);
    if(pos!=ELF_BYTES||synced||closed){unlink(output);return 7;}
    return 0;
}
int main(int argc,char **argv)
{
    if(argc!=2||!output_ok(argv[1]))return 2;
    size_t length=(PACKED_BYTES+4095u)&~4095u;
    if(STAGE_OFFSET>=STAGE_LIMIT||length>STAGE_LIMIT-STAGE_OFFSET)return 2;
    int fd=open("/dev/prodock-gpu",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd<0)return 8;
    const unsigned char *src=mmap(NULL,length,PROT_READ,MAP_SHARED,fd,STAGE_OFFSET);
    if(src==MAP_FAILED){close(fd);return 9;}
    int result=extract_stage(src,PACKED_BYTES,argv[1]);
    int unmapped=munmap((void *)src,length),closed=close(fd);
    if(!result&&(unmapped||closed))result=10;
    if(!result){static const char ok[]="STAGE_FM4A_OK bytes=16640496 crc=fa358bf4\n";ssize_t n=write(1,ok,sizeof ok-1);if(n!=(ssize_t)(sizeof ok-1))result=11;}
    return result;
}
