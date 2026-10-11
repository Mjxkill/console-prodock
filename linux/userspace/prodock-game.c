// SPDX-License-Identifier: GPL-2.0-or-later
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#include "prodock-uapi.h"
/* Small playable integration game. All pixels are drawn by GPU CLEAR_RECT;
 * Linux performs input and physics. Each page owns 480 rows at pitch 1600,
 * even though the game renders 400x240; scanout selects native or x2. */
static volatile sig_atomic_t stopped;
static void stop(int sig) { (void)sig; stopped=1; }
static void rect(struct prodock_batch *b,unsigned color,int x,int y,int w,int h)
{
    uint32_t *c=b->commands[b->count++];
    c[0]=28U<<24; c[1]=1; c[2]=color; c[4]=((uint32_t)x<<16)|(unsigned)y;
    c[5]=((uint32_t)w<<16)|(unsigned)h;
}
static double now(void)
{
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec+t.tv_nsec/1e9;
}
int main(int argc,char **argv)
{
    unsigned frames=0,limit=0,score=0,lives=3,escape=0; int demo=0,rc=1;
    for(int i=1;i<argc;++i) {
        if(!strcmp(argv[i],"--demo")) demo=1;
        else if(!strcmp(argv[i],"--frames") && i+1<argc) {
            char *end; unsigned long v=strtoul(argv[++i],&end,10);
            if(*end || !v || v>1000000) return 2;
            limit=(unsigned)v;
        } else { fprintf(stderr,"usage: prodock-game [--demo] [--frames N]\n");return 2; }
    }
    int fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);
    if(fd<0) { perror("GPU open");return 1; }
    struct termios saved,raw; int changed=0;
    if(!demo) {
        if(tcgetattr(STDIN_FILENO,&saved)) { perror("game terminal");goto done; }
        raw=saved; raw.c_lflag &= ~(ICANON|ECHO); raw.c_cc[VMIN]=0;raw.c_cc[VTIME]=0;
        if(tcsetattr(STDIN_FILENO,TCSANOW,&raw)) goto done;
        changed=1;
    }
    signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGHUP,stop);
    printf("PRODOCK_GAME_START mode=%s - A/D ou fleches, Q pour quitter\n",demo?"demo":"jouable");
    fflush(stdout);
    float x=200,y=174,vx=115,vy=-125,paddle=165;
    unsigned char bricks[40]; memset(bricks,1,sizeof(bricks));
    double started=now(),last=started,submit_seconds=0,present_seconds=0;
    while(!stopped && (!limit || frames<limit)) {
        double current=now(),dt=current-last;last=current;
        if(dt>.05)dt=.05;
        if(dt<.001)dt=.001;
        if(demo) paddle=x-35;
        else {
            struct pollfd in={STDIN_FILENO,POLLIN,0};
            if(poll(&in,1,0)>0 && (in.revents&POLLIN)) {
                char keys[64];ssize_t n=read(STDIN_FILENO,keys,sizeof(keys));
                for(ssize_t i=0;i<n;++i) {
                    if(escape==1) { escape=(keys[i]=='['||keys[i]=='O')?2:0;continue; }
                    if(escape==2) {
                        if(keys[i]=='D')paddle-=18;
                        if(keys[i]=='C')paddle+=18;
                        escape=0;continue;
                    }
                    if(keys[i]==27) { escape=1;continue; }
                    if(keys[i]=='a'||keys[i]=='A')paddle-=18;
                    if(keys[i]=='d'||keys[i]=='D')paddle+=18;
                    if(keys[i]=='q'||keys[i]=='Q')stopped=1;
                }
            }
        }
        if(paddle<4)paddle=4;
        if(paddle>326)paddle=326;
        x+=vx*dt;y+=vy*dt;
        if(x<6){x=6;vx=-vx;} if(x>394){x=394;vx=-vx;}
        if(y<6){y=6;vy=-vy;}
        if(vy>0 && y>=213 && y<=225 && x>=paddle-4 && x<=paddle+74) {
            y=213;vy=-135;vx=(x-paddle-35)*4;
        }
        if(y>244) {
            if(lives)--lives;
            x=200;y=174;vx=115;vy=-125;
            if(!lives) { lives=3;score=0;memset(bricks,1,sizeof(bricks)); }
        }
        for(unsigned i=0;i<40;++i) if(bricks[i]) {
            int bx=10+(i%10)*38,by=26+(i/10)*17;
            if(x>=bx-3 && x<bx+37 && y>=by-3 && y<by+16) {
                bricks[i]=0;vy=-vy;++score;break;
            }
        }
        if(score==40) { score=0;memset(bricks,1,sizeof(bricks)); }
        struct prodock_batch b={0};unsigned page=frames&1;
        uint32_t *c=b.commands[b.count++];
        c[0]=22U<<24;c[1]=0x800000+page*0x100000;c[2]=0xa00000;
        c[3]=(400U<<16)|240;c[4]=(1600U<<16)|1600;
        rect(&b,0x0823,0,0,400,240);
        rect(&b,0x3a4a,0,0,4,240);rect(&b,0x3a4a,396,0,4,240);
        static const unsigned colours[4]={0xf986,0xfcc6,0x76ee,0x365e};
        for(unsigned i=0;i<40;++i) if(bricks[i]) {
            int bx=10+(i%10)*38,by=26+(i/10)*17;
            rect(&b,colours[i/10],bx,by,34,13);
        }
        rect(&b,0x6fff,(int)paddle,218,70,6);
        rect(&b,0xffff,(int)x-3,(int)y-3,6,6);
        for(unsigned i=0;i<lives;++i)rect(&b,0xf9ca,8+i*10,230,6,4);
        rect(&b,0xffee,300,230,score*2+1,4);
        double stamp=now();
        if(ioctl(fd,PRODOCK_SUBMIT,&b)) { perror("GPU submit");goto restore; }
        submit_seconds+=now()-stamp;
        struct prodock_scene scene={.base=0x800000+page*0x100000,.stride=1600,.format=7};
        stamp=now();
        if(ioctl(fd,PRODOCK_PRESENT,&scene)) { perror("GPU present");goto restore; }
        present_seconds+=now()-stamp;
        ++frames;
    }
    printf("PRODOCK_GAME_RATE frames=%u seconds=%.3f fps=%.2f\n",frames,now()-started,frames/(now()-started));
    printf("PRODOCK_GAME_TIME submit=%.3f present=%.3f\n",submit_seconds,present_seconds);
    rc=0;
restore:
    if(changed)tcsetattr(STDIN_FILENO,TCSANOW,&saved);
done:
    close(fd);
    printf("PRODOCK_GAME_DONE frames=%u score=%u status=%d\n",frames,score,rc);
    return rc;
}
