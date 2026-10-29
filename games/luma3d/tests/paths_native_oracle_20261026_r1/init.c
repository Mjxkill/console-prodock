#define _POSIX_C_SOURCE 200809L
/* QEMU-only extraction harness. Executes the unchanged frozen RV32 ELF. */
#include <assert.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/reboot.h>
#include <sys/wait.h>
#include <unistd.h>
static uint32_t crc(const unsigned char *p,size_t n){uint32_t c=~0u;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&-(c&1));}return ~c;}
static unsigned char *load(const char *p,size_t *n){FILE *f=fopen(p,"rb");assert(f);assert(!fseek(f,0,SEEK_END));long z=ftell(f);assert(z>=0&&z<=32*1024*1024);*n=(size_t)z;rewind(f);unsigned char *b=malloc(*n+1);assert(b);assert(fread(b,1,*n,f)==*n);assert(!fclose(f));return b;}
static void full(const char *ext){char p[80];snprintf(p,sizeof(p),"/native.%s",ext);size_t n;unsigned char *b=load(p,&n);printf("ORACLE_FILE %s %zu %08x\n",ext,n,crc(b,n));for(size_t at=0;at<n;at+=128){printf("ORACLE_HEX %s %zu ",ext,at);for(size_t i=at;i<n&&i<at+128;i++)printf("%02x",b[i]);putchar('\n');}free(b);}
int main(void){setvbuf(stdout,NULL,_IOLBF,0);puts("ORACLE_INIT");pid_t p=fork();assert(p>=0);if(!p){int fd=open("/dev/null",O_RDONLY);assert(fd>=0);assert(dup2(fd,0)==0);execl("/game","/game","--host","--frames","1","--save","/garden.save","--capture","/native",(char*)0);_exit(127);}int status;assert(waitpid(p,&status,0)==p);printf("ORACLE_EXIT %d\n",status);assert(status==0);full("commands");full("json");full("overlay.json");size_t n,m;unsigned char *b=load("/native.memory",&n),*a=load("/baseline.memory",&m);assert(n==m);printf("ORACLE_MEMORY %zu %08x %08x\n",n,crc(a,m),crc(b,n));size_t changes=0;for(size_t at=0;at<n;at++){if(a[at]==b[at])continue;size_t end=at+1;while(end<n&&end<at+128&&a[end]!=b[end])end++;printf("ORACLE_DIFF %zu ",at);for(size_t i=at;i<end;i++)printf("%02x",b[i]);putchar('\n');changes+=end-at;at=end-1;}printf("ORACLE_DONE changed=%zu\n",changes);fflush(stdout);reboot(RB_POWER_OFF);for(;;)pause();}
