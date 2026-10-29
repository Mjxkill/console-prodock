// SPDX-License-Identifier: MIT
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include "prodock-uapi.h"
static int checked(int fd, unsigned long op, void *data)
{
    if (ioctl(fd, op, data)) { perror("GPU ioctl"); return -1; }
    return 0;
}
static int demo(int fd,const struct prodock_info *info)
{
    struct prodock_batch batch = {0};
    struct prodock_scene scene = { .base = 0x800000, .stride = 1600, .format = 3 };
    unsigned w=info->width==1280?640:800,h=info->height==720?360:480;
    unsigned pitch=info->width*2,page_bytes=info->width==1280?0x200000:0x100000;
    scene.stride=pitch;scene.format=info->width==1280?7:3;
    unsigned f;
    for (f = 0; f < 90; ++f) {
        unsigned page = f & 1, c = 0;
        batch.commands[c][0] = 22U << 24;
        batch.commands[c][1] = 0x800000 + page * page_bytes;
        batch.commands[c][2] = 0x800000 + 2*page_bytes;
        batch.commands[c][3] = (w << 16) | h;
        batch.commands[c++][4] = (pitch << 16) | pitch;
        batch.commands[c][0] = 28U << 24; batch.commands[c][1] = 3;
        batch.commands[c][2] = 0x0843; batch.commands[c][3] = 65535;
        batch.commands[c++][5] = (w << 16) | h;
        for (unsigned i = 0; i < 24; ++i) {
            uint32_t *word = batch.commands[c++];
            word[0] = 28U << 24; word[1] = 1;
            word[2] = ((i * 31 / 23) << 11) | ((63 - i * 63 / 23) << 5) | 20;
            word[4] = (((40U + i * 30)*w/800) << 16) | (90*h/480);
            word[5] = ((30U*w/800) << 16) | (260*h/480);
        }
        batch.commands[c][0] = 28U << 24; batch.commands[c][1] = 1;
        batch.commands[c][2] = 0xffff; batch.commands[c][4] = (((40U + f * 7)*w/800) << 16) | (385*h/480);
        batch.commands[c++][5] = ((90U*w/800) << 16) | (30*h/480);
        batch.count = c;
        if (checked(fd, PRODOCK_SUBMIT, &batch)) return 1;
        scene.base = 0x800000 + page * page_bytes;
        if (checked(fd, PRODOCK_PRESENT, &scene)) return 1;
    }
    /* Independent full-frame check through the application's mmap alias.
     * SUBMIT has completed and invalidated CPU cache before these reads. */
    const uint16_t *pixels = mmap(NULL, pitch * h, PROT_READ, MAP_SHARED, fd, page_bytes);
    if (pixels == MAP_FAILED) { perror("GPU mmap"); return 1; }
    for (unsigned y=0;y<h;++y) for(unsigned x=0;x<w;++x) {
        unsigned expected=0x0843;
        for(unsigned i=0;i<24;++i) {
            unsigned bx=(40+i*30)*w/800;
            if(y>=90*h/480 && y<(90+260)*h/480 && x>=bx && x<bx+30*w/800)
                expected=((i*31/23)<<11)|((63-i*63/23)<<5)|20;
        }
        if(y>=385*h/480 && y<385*h/480+30*h/480 && x>=663*w/800 && x<663*w/800+90*w/800)expected=0xffff;
        if(pixels[y*(pitch/2)+x]!=expected) {
            fprintf(stderr,"GPU pixel (%u,%u): %04x != %04x\n",x,y,pixels[y*(pitch/2)+x],expected);
            munmap((void *)pixels,pitch*h);return 1;
        }
    }
    munmap((void *)pixels,pitch*h);
    printf("PRODOCK_GPU_PIXELS_OK pixels=%u\n",w*h);
    puts("PRODOCK_GPU_DEMO_OK");
    return 0;
}
int main(int argc, char **argv)
{
    int fd, rc = 0;
    struct prodock_info info;
    if (argc == 3 && !strcmp(argv[1], "layout")) {
        struct prodock_layout mode = {0};
        if (!strcmp(argv[2], "split")) mode.mode = PRODOCK_SPLIT;
        else if (!strcmp(argv[2], "game")) mode.mode = PRODOCK_GAME;
        else if (!strcmp(argv[2], "console")) mode.mode = PRODOCK_TERMINAL;
        else { fprintf(stderr, "layout: split|game|console\n"); return 2; }
        fd = open("/dev/prodock-display", O_RDWR | O_CLOEXEC);
        if (fd < 0) { perror("display"); return 1; }
        rc = checked(fd, PRODOCK_LAYOUT, &mode); close(fd); return !!rc;
    }
    if (argc == 2 && !strcmp(argv[1], "geometry")) {
        struct prodock_display_geometry s;
        fd=open("/dev/prodock-display",O_RDWR|O_CLOEXEC);
        if(fd<0){perror("display");return 1;}
        rc=checked(fd,PRODOCK_DISPLAY_GEOMETRY,&s);
        if(!rc)printf("GEOMETRY board=%u width=%u height=%u pixel_hz=%u memory_hz=%u total=%ux%u line_budget=%u\n",
            s.board,s.width,s.height,s.pixel_hz,s.memory_hz,s.htotal,s.vtotal,s.line_budget);
        close(fd);return !!rc;
    }
    if (argc == 2 && !strcmp(argv[1], "display")) {
        struct prodock_display_info s;
        fd = open("/dev/prodock-display", O_RDWR | O_CLOEXEC);
        if (fd < 0) { perror("display"); return 1; }
        rc = checked(fd, PRODOCK_DISPLAY_INFO, &s);
        if (!rc) printf("DISPLAY mode=%u cols=%u rows=%u text=%u presents=%u sent=%llu frames=%u done=%u errors=%u uf=%u line=%u invalid=%u sprites=%u usb=%08x fault=%u crc=%08x feed_us=%u wait_us=%u cache_us=%u present_us=%u text_us=%u\n",
            s.mode,s.columns,s.rows,s.text_updates,s.game_presents,
            (unsigned long long)(((uint64_t)s.sent_hi<<32)|s.sent_lo),s.frames,s.done&65535,
            s.errors,s.underflows,s.line_cycles,s.invalid_layers,s.invalid_sprites,s.usb_status,s.faulted,s.checksum,
            s.feed_us,s.wait_us,s.cache_us,s.present_us,s.text_us);
        close(fd); return !!rc;
    }
    if (argc == 2 && !strcmp(argv[1], "selftest")) {
        if (sizeof(struct prodock_info) != 48 || sizeof(struct prodock_batch) != 2056 ||
            sizeof(struct prodock_scene) != 1568 || _IOC_SIZE(PRODOCK_SUBMIT) != 2056) return 1;
        puts("PRODOCK_USERSPACE_SELFTEST_OK"); return 0;
    }
    if (argc != 2 || (strcmp(argv[1], "info") && strcmp(argv[1], "demo"))) {
        fprintf(stderr, "usage: prodockctl info|demo|selftest|display|geometry|layout split|game|console\n"); return 2;
    }
    fd = open("/dev/prodock-gpu", O_RDWR | O_CLOEXEC);
    if (fd < 0) { perror("/dev/prodock-gpu"); return 1; }
    if (checked(fd, PRODOCK_INFO, &info)) { close(fd); return 1; }
    printf("GPU ABI=%u caps=%08x DDR=%08x+%u done=%u errors=%u uf=%u frames=%u crc=%08x fault=%u\n",
        info.abi, info.caps, info.memory_base, info.memory_bytes, info.done,
        info.errors, info.underflows, info.frames, info.checksum, info.faulted);
    if (!strcmp(argv[1], "demo")) rc = demo(fd,&info);
    if (close(fd)) { perror("close GPU"); rc = 1; }
    return rc;
}
