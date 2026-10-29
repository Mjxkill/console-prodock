// SPDX-License-Identifier: GPL-2.0-or-later
#define _DEFAULT_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/kd.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "prodock-uapi.h"
/* Independent full-screen LCD checksum from the actual Linux font, without
 * reading/reusing the GPU atlas or map generation code. */
int main(void)
{
    int denied=open("/dev/fb0",O_RDONLY|O_CLOEXEC);
    if(denied>=0) { close(denied);fputs("fb0 unexpectedly accepts pixel clients\n",stderr);return 1; }
    if(errno!=EOPNOTSUPP) { perror("fb0 guard");return 1; }
    int display=open("/dev/prodock-display",O_RDWR|O_CLOEXEC);
    int tty=open("/dev/tty1",O_RDWR|O_NOCTTY|O_CLOEXEC),rc=1;
    unsigned char font[256*32];
    struct prodock_display_geometry geometry={.width=800,.height=480};

    uint32_t passed_crc[4],sparse_crc[8]; unsigned passed=0,sparse=0;
    struct console_font_op f={.op=KD_FONT_OP_GET,.width=8,.height=32,.charcount=256,.data=font};
    struct prodock_layout mode={.mode=PRODOCK_TERMINAL};
    struct prodock_display_info initial,actual;
    if(display<0 || tty<0 || ioctl(tty,KDFONTOP,&f) || f.width!=8 || f.height!=16 ||
       ioctl(display,PRODOCK_LAYOUT,&mode) || ioctl(display,PRODOCK_DISPLAY_INFO,&initial)) goto out;
    if(ioctl(display,PRODOCK_DISPLAY_GEOMETRY,&geometry) && errno!=ENOTTY)goto out;
    unsigned columns=geometry.width/8,rows=geometry.height/16;
    for(unsigned trial=0;trial<4;++trial) {
        unsigned ch=trial==0?'A':trial==1?'g':trial==2?'W':' '; unsigned bits=0;
        for(unsigned y=0;y<16;++y) for(unsigned x=0;x<8;++x) bits+=!!(font[ch*32+y]&(128>>x));
        /* Foreground bright white, red, cyan, white; backgrounds black, blue, red, magenta. */
        static const char *sgr[]={"97;40","31;44","36;41","97;45"};
        static const uint32_t fg[]={0x3ffff,42<<12,(42<<6)|42,0x3ffff};
        static const uint32_t bg[]={0,42,42<<12,(42<<12)|42};
        uint32_t expected=columns*rows*(bits*fg[trial]+(128-bits)*bg[trial]);
        char buffer[8200],*p=buffer;
        p+=sprintf(p,"\033[?25l\033[0m\033[%sm\033[2J",sgr[trial]);
        for(unsigned y=0;y<rows;++y) {
            p+=sprintf(p,"\033[%u;1H",y+1);
            memset(p,ch,columns);p+=columns;
        }
        size_t size=p-buffer,off=0;
        while(off<size) { ssize_t n=write(tty,buffer+off,size-off);if(n<=0)goto out;off+=(size_t)n; }
        usleep(250000);
        for(unsigned sample=0;sample<3;++sample) {
            if(ioctl(display,PRODOCK_DISPLAY_INFO,&actual))goto out;
            if(actual.checksum!=expected || actual.errors || actual.faulted ||
               actual.underflows!=initial.underflows || actual.invalid_layers || actual.invalid_sprites) {
                fprintf(stderr,"TEXT_FAIL trial=%u crc=%08x expected=%08x uf=%u/%u invalid=%u/%u\n",
                  trial,actual.checksum,expected,actual.underflows,initial.underflows,actual.invalid_layers,actual.invalid_sprites);
                goto out;
            }
            usleep(25000);
        }
        /* stdout is itself mirrored to this VT. Delay logs until AFTER all
         * reference frames, otherwise the PTY daemon changes the next frame. */
        passed_crc[passed++]=expected;
    }
    /* Reuse both map banks several times, changing only two characters.
     * Comparing a new map against the wrong bank leaves stale glyphs here. */
    for(unsigned trial=0;trial<8;++trial) {
        unsigned a=(trial&1)?'g':'A',b=(trial&2)?'W':' ',bits=0;
        for(unsigned y=0;y<16;++y) for(unsigned x=0;x<8;++x) {
            bits+=!!(font[a*32+y]&(128>>x));
            bits+=!!(font[b*32+y]&(128>>x));
        }
        uint32_t bg=(42U<<12)|42,expected=geometry.width*geometry.height*bg+bits*(0x3ffff-bg);
        char text[80];int n=snprintf(text,sizeof(text),"\033[3;11H%c\033[23;74H%c",a,b);
        if(write(tty,text,(size_t)n)!=n)goto out;
        usleep(250000);
        for(unsigned sample=0;sample<3;++sample) {
            if(ioctl(display,PRODOCK_DISPLAY_INFO,&actual))goto out;
            if(actual.checksum!=expected || actual.errors || actual.faulted ||
               actual.underflows!=initial.underflows || actual.invalid_layers || actual.invalid_sprites) {
                fprintf(stderr,"TEXT_SPARSE_FAIL trial=%u crc=%08x expected=%08x\n",trial,actual.checksum,expected);
                goto out;
            }
            usleep(25000);
        }
        sparse_crc[sparse++]=expected;
    }
    rc=0;
out:
    if(rc)perror("text test");
    if(tty>=0) { const char *s="\033[0m\033[2J\033[H\033[?25h"; if(write(tty,s,strlen(s))<0)rc=1;close(tty); }
    mode.mode=PRODOCK_SPLIT;
    if(display>=0) { if(ioctl(display,PRODOCK_LAYOUT,&mode))rc=1;close(display); }
    for(unsigned i=0;i<passed;++i)printf("TEXT_CRC_OK trial=%u crc=%08x pixels=%u\n",i,passed_crc[i],geometry.width*geometry.height);
    for(unsigned i=0;i<sparse;++i)printf("TEXT_SPARSE_CRC_OK trial=%u crc=%08x\n",i,sparse_crc[i]);
    if(!rc)puts("TEXT_SPARSE_OK trials=8");
    if(!rc)printf("PRODOCK_TEXT_PIXELS_OK poses=4 pixels=%u\n",geometry.width*geometry.height*4);
    return rc;
}
