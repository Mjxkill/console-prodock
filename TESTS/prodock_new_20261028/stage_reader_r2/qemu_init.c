#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
static int invoke(const char *path){pid_t p=fork();if(!p){execl("/reader","reader",path,(char *)NULL);_exit(127);}int s;if(waitpid(p,&s,0)!=p)return -1;return WIFEXITED(s)?WEXITSTATUS(s):-1;}
static int same(const char *a,const char *b){int x=open(a,O_RDONLY),y=open(b,O_RDONLY),ok=x>=0&&y>=0;char p[4096],q[4096];unsigned total=0;while(ok){ssize_t n=read(x,p,sizeof p),m=read(y,q,sizeof q);if(n<0||m!=n){ok=0;break;}if(!n)break;if(memcmp(p,q,n)){ok=0;break;}total+=(unsigned)n;}if(x>=0)close(x);if(y>=0)close(y);return ok&&total==16640496;}
int main(void)
{
 setvbuf(stdout,NULL,_IONBF,0);mkdir("/dev",0755);mount("devtmpfs","/dev","devtmpfs",0,NULL);mkdir("/tmp",0700);mount("tmpfs","/tmp","tmpfs",0,"size=64m");
 int source=open("/packed",O_RDONLY),fd=open("/dev/prodock-gpu",O_RDWR|O_CREAT|O_EXCL,0600);int valid=source>=0&&fd>=0;
 if(valid)valid=ftruncate(fd,0x03800000+5808128)==0&&lseek(fd,0x03800000,SEEK_SET)==0x03800000;
 char buf[8192];ssize_t n;while(valid&&(n=read(source,buf,sizeof buf))>0)valid=write(fd,buf,n)==n;
 if(source>=0)close(source);if(fd>=0)close(fd);
 int a=valid?invoke("/tmp/game"):-1;int exact=a==0&&same("/tmp/game","/expected");printf("EXACT_RV32 %d\n",exact);
 int b=invoke("/tmp/game");int exists=b==6&&same("/tmp/game","/expected");printf("EXISTING_PRESERVED %d\n",exists);
 symlink("/tmp/game","/tmp/link");int c=invoke("/tmp/link");int link=c==6&&same("/tmp/game","/expected");printf("SYMLINK_REJECTED %d\n",link);
 fd=open("/dev/prodock-gpu",O_RDWR);unsigned char byte;pread(fd,&byte,1,0x03800000+100);byte^=1;pwrite(fd,&byte,1,0x03800000+100);close(fd);
 int d=invoke("/tmp/bad");int crc=d==2&&access("/tmp/bad",F_OK)!=0;printf("BAD_CRC_REJECTED %d\n",crc);
 puts(exact&&exists&&link&&crc?"STAGE_READER_QEMU_PASS":"STAGE_READER_QEMU_FAIL");sync();reboot(RB_POWER_OFF);for(;;)pause();
}
