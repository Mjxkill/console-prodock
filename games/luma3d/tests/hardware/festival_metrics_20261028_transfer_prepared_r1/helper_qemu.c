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
static int invoke(const char*packed,const char*out,const char*base){pid_t p=fork();if(!p){execl("/helper","helper","patch",packed,out,"6596268","9658fe8a",base,(char*)NULL);_exit(127);}int s;if(waitpid(p,&s,0)!=p)return-1;return WIFEXITED(s)?WEXITSTATUS(s):-1;}
static int same(const char*a,const char*b,unsigned wanted){int x=open(a,O_RDONLY),y=open(b,O_RDONLY),ok=x>=0&&y>=0;unsigned total=0;char p[8192],q[8192];while(ok){ssize_t n=read(x,p,sizeof(p)),m=read(y,q,sizeof(q));if(n<0||m!=n){ok=0;break;}if(!n)break;if(memcmp(p,q,n)){ok=0;break;}total+=(unsigned)n;}if(x>=0)close(x);if(y>=0)close(y);return ok&&total==wanted;}
int main(void){
 setvbuf(stdout,NULL,_IONBF,0);mkdir("/dev",0755);mount("devtmpfs","/dev","devtmpfs",0,NULL);mkdir("/tmp",0700);mount("tmpfs","/tmp","tmpfs",0,"size=32m");
 int a=invoke("/delta","/tmp/metrics","/base");int exact=a==0&&same("/tmp/metrics","/expected",16640496);printf("EXACT_RECONSTRUCTION %d\n",exact);
 int b=invoke("/delta","/tmp/metrics","/base");int exclusive=b!=0&&same("/tmp/metrics","/expected",16640496);printf("EXCLUSIVE_OUTPUT %d\n",exclusive);
 int c=invoke("/delta","/tmp/bad-base","/delta");int badbase=c!=0&&access("/tmp/bad-base",F_OK)!=0;printf("WRONG_BASE_REJECT %d\n",badbase);
 int in=open("/delta",O_RDONLY),out=open("/tmp/bad-delta",O_WRONLY|O_CREAT|O_EXCL,0600);char buf[4096];ssize_t n;unsigned at=0;while((n=read(in,buf,sizeof(buf)))>0){if(!at)buf[100]^=1;at+=(unsigned)n;if(write(out,buf,n)!=n)return 1;}close(in);close(out);
 int d=invoke("/tmp/bad-delta","/tmp/bad-output","/base");int badpacked=d!=0&&access("/tmp/bad-output",F_OK)!=0;printf("CORRUPT_PACKED_REJECT %d\n",badpacked);
 puts(exact&&exclusive&&badbase&&badpacked?"HELPER_QEMU_PASS":"HELPER_QEMU_FAIL");sync();reboot(RB_POWER_OFF);for(;;)pause();
}
